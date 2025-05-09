import os
import time
import logging
import requests
from lib.utils import (Doujinshi, SourceType, add_doujinshi_to_redis, delete_doujinshi_from_redis,
                       get_all_values_from_list, clear_keys_from_redis)

def batch_add_to_library(app_state, id_list: list[str], source_name: str, is_replace: bool) -> None:
    client = app_state["redis_client"]
    clear_keys_from_redis(client, "search_cache")
    num = len(id_list)
    infos = {}
    dids = get_all_values_from_list(client, "data:doujinshis")
    for did in dids:
        json_data = client.hgetall(f"doujinshi:{did}")
        if json_data["source"] == source_name:
            infos[json_data["identifier"]] = (did, json_data["title"], json_data["groups"])
    count = 0
    for id in id_list:
        count = count + 1
        try:
            metadata = app_state["sources"][source_name].get_metadata(id)
            if metadata["id"] in infos:
                if not is_replace:
                    client.set("add_status", f"finish adding to library {count}/{num}")
                    client.set("add_progress", count/num)
                    continue
                else:
                    # 覆盖旧数据
                    if os.path.exists(f".data/thumb/{infos[metadata['id']][0]}.jpg"): # 删除旧封面
                        os.remove(f".data/thumb/{infos[metadata['id']][0]}.jpg")
                    delete_doujinshi_from_redis(client, infos[metadata["id"]][0], infos[metadata["id"]][1], infos[metadata["id"]][2])
            doujinshi = Doujinshi(title = metadata["title"], pagecount = metadata["pagecount"],
                        tags = "|$|".join(metadata["tags"]), identifier = metadata["id"],
                        type = SourceType.web, source = source_name)
            # 保存封面
            with open(f".data/thumb/{str(doujinshi.id)}.jpg", "wb") as f:
                res = requests.get(metadata["cover"]["url"], proxies = app_state["settings"]["proxy"], headers = metadata["cover"]["headers"])
                f.write(res.content)
            add_doujinshi_to_redis(client, doujinshi)
            logging.info(f"add {id} of {source_name} source to library")
        except Exception as e:
            logging.error(f"fail to add {id} of {source_name} source to library, error message: {e}")
        time.sleep(app_state["sources"][source_name].SLEEP)
        client.set("add_status", f"finish adding to library {count}/{num}")
        client.set("add_progress", count/num)
    client.set("add_status", "finished")

def clean_database_by_source_name(client, name: str, doujinshi_list: list, source_type: SourceType) -> list:
    doujinshi_data = {}
    for i in doujinshi_list:
        f_name, ext = os.path.splitext(str(i[0]))
        if source_type == SourceType.cloud or source_type == SourceType.cloud_encrypted:
            if not ext in [".zip", ".ZIP"]: # 筛选文件类型
                continue
        elif source_type == SourceType.local:
            if not ext in [".zip", ".ZIP", ".7z", ".7Z", ".rar", ".RAR"]:
                continue
        doujinshi_data[str(i[1])] = f_name
    dids = get_all_values_from_list(client, "data:doujinshis")
    for did in dids:
        json_data = client.hgetall(f"doujinshi:{did}")
        if json_data["source"] == name:
            info = (json_data["title"], json_data["identifier"])
            if json_data["identifier"] in doujinshi_data:
                del doujinshi_data[json_data["identifier"]] # 已存在，跳过
            else:
                # 移除不存在的数据及封面
                if os.path.exists(f".data/thumb/{str(did)}.jpg"): # 移除封面
                    os.remove(f".data/thumb/{str(did)}.jpg")
                delete_doujinshi_from_redis(client, did, json_data["title"], json_data["groups"])
    return doujinshi_list

def scan_to_database(app_state, name: str) -> None:
    source_object = app_state["sources"][name]
    client = app_state["redis_client"]
    client.set("scan_source_name", name) # 记录源名称
    logging.info(f"start scanning the {name} library...")
    clear_keys_from_redis(client, "search_cache") # 删除搜索缓存
    try:
        client.set("scan_status_code", 1) # 设置状态码
        logging.info(f"start getting the doujinshi list of {name} library...")
        doujinshi_list = source_object.get_doujinshi() # 获取列表
    except Exception as e:
        logging.error(f"failed to scan the {name} library, error message: {e}")
        client.set("scan_status_code", 4)
        return
    # 保存到数据库
    client.set("scan_status_code", 2)
    logging.info(f"clear the old datas from the {name} library")
    doujinshi_list = clean_database_by_source_name(client, name, doujinshi_list, source_object.TYPE)
    for d in doujinshi_list.keys():
        doujinshi = Doujinshi(title = doujinshi_list[d], identifier = d,
                              type = source_object.TYPE, source = name)
        add_doujinshi_to_redis(client, doujinshi)
        logging.info(f"add {doujinshi_list[d]}")
    client.set("scan_status_code", 3)
    logging.info(f"the {name} library has been scanned")