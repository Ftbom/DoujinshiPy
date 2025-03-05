import os
import hashlib
import random
import logging
from lib.utils import (get_values_from_list_by_page, get_all_values_from_list, get_all_values_from_set, 
                       delete_group_from_redis, set_name_of_group,set_metadata_of_doujinshi, delete_doujinshi_from_redis,
                       set_group_of_doujinshi, rm_group_of_doujinshi)

def get_metadata(client, id: str) -> dict:
    doujinshi = client.hgetall(f"doujinshi:{id}")
    tags = doujinshi["tags"].split("|")
    tags = [item for item in tags if item != ""]
    if "translated_tags" in doujinshi:
        translated_tags = doujinshi["translated_tags"].split("|")
        try:
            translated_tags.remove("")
        except:
            pass
    else:
        translated_tags = None
    # 获取group
    groups = []
    group_ids = doujinshi["groups"].split("|")
    group_ids = [item for item in group_ids if item != ""]
    for gid in group_ids:
        groups.append(client.get(f"group:{gid}"))
    if doujinshi["hascover"] == "1":
        cover_url = f"/doujinshi/{id}/thumbnail"
    else:
        cover_url = "/doujinshi/nothumb/thumbnail"
    if translated_tags == None:
        return {"id": id, "title": doujinshi["title"], "source": doujinshi["source"],
                "groups": groups, "tags": tags, "cover": cover_url}
    return {"id": id, "title": doujinshi["title"], "source": doujinshi["source"],
                "groups": groups, "tags": tags, "translated_tags": translated_tags, "cover": cover_url}

def get_doujinshi_list(client, page, max_perpage) -> dict:
    doujinshi = []
    results = get_values_from_list_by_page(client, "data:doujinshis", page, max_perpage)
    for result in results:
        doujinshi.append(get_metadata(client, result))
    return doujinshi

def get_random_doujinshi_list(client, num: int) -> dict:
    # 获取列表的长度
    list_length = client.llen("data:doujinshis")
    if list_length == 0:
        return []
    # 随机选择生成索引
    random_indexs = random.sample(range(0, list_length), num)
    doujinshi = []
    for i in random_indexs:
        result = client.lindex("data:doujinshis", i)
        doujinshi.append(get_metadata(client, result))
    return doujinshi

def get_doujinshi_by_id(client, id: str) -> dict:
    if not client.exists(f"doujinshi:{id}"):
        return {}
    return get_metadata(client, id)

def delete_metadata(client, id: str) -> dict:
    if not client.exists(f"doujinshi:{id}"):
        return False
    delete_doujinshi_from_redis(client, id)
    try:
        os.remove(f".data/thumb/{id}.jpg")
    except:
        pass
    return True

def generate_id_from_querys(query_list, group, source_name):
    q_str = f"{'|'.join(query_list)}_{group}_{source_name}"
    return hashlib.md5(q_str.encode('utf-8')).hexdigest()

def filter_doujinshi(ids, results: list, parameters) -> list:
    query_filter = parameters[0]
    group_filter = parameters[1]
    source_filter = parameters[2]
    matched_ids = []
    for i in range(len(results)):
        result = results[i]
        match_list = result["tags"].lower().split("|")
        match_list = [item for item in match_list if item != ""]
        if "translated_tags" in result:
            match_list.extend(result["translated_tags"].lower().split("|"))
        match_list.append(result["title"].lower())
        matched = True
        for q in query_filter:
            single_matched = False
            for m in match_list:
                if type(q) == list:
                    if (q[0] in m) or (q[1] in m):
                        single_matched = True
                        break
                else:
                    if q in m:
                        single_matched = True
                        break
            if not single_matched:
                matched = False
                break
        if not matched:
            continue
        if len(group_filter) != 0: # 应用group筛选
            r_groups = result["groups"].split("|")
            if not group_filter in r_groups:
                continue
        if len(source_filter) != 0: # 应用源筛选
            if source_filter != result["source"]:
                continue
        matched_ids.append(ids[i])
    return matched_ids

def search_doujinshi(client, parameters, max_perpage) -> dict:
    query_key = "tmp:" + generate_id_from_querys(parameters[0], parameters[1], parameters[2])
    if not client.exists(query_key):
        # 筛选并缓存结果
        id_list = []
        tmp_ids = []
        count = 0
        all_ids = get_all_values_from_list(client, "data:doujinshis")
        # 使用Pipeline批量获取数据
        pipeline = client.pipeline()
        for id in all_ids:
            if count >= 100:
                id_list.extend(filter_doujinshi(tmp_ids, pipeline.execute(), parameters))
                pipeline.reset()
                count = 0
                tmp_ids = []
            pipeline.hgetall(f"doujinshi:{id}")
            tmp_ids.append(id)
            count = count + 1
        if count > 0:
            id_list.extend(filter_doujinshi(tmp_ids, pipeline.execute(), parameters))
            pipeline.reset()
        count = 0
        for id in id_list:
            if count >= 500:
                pipeline.execute()
                pipeline.reset()
            pipeline.rpush(query_key, id)
            count = count + 1
        pipeline.expire(query_key, 1800) # 30min过期
        pipeline.execute()
    results = get_values_from_list_by_page(client, query_key, parameters[3], max_perpage)
    doujinshi = []
    for result in results:
        if not client.exists(f"doujinshi:{result}"):
            continue
        doujinshi.append(get_metadata(client, result))
    return doujinshi

def set_metadata(client, id: str, metadata) -> bool:
    if not set_metadata_of_doujinshi(client, id, metadata.tag, True, metadata.title):
        return False
    logging.info(f"set the metadata of doujinshi {id}")
    return True

def get_group_list(client) -> list[str]:
    group_list = []
    results = get_all_values_from_set(client, "data:groups")
    for result in results:
        group_list.append({"id": result, "name": client.get(f"group:{result}")})
    return group_list

def get_doujinshi_by_group(client, id: str, page: int, max_perpage: int) -> dict:
    name = client.get(f"group:{id}")
    if name == None:
        return {}
    results = get_values_from_list_by_page(client, f"data:group_{id}", page, max_perpage)
    items = []
    for result in results:
        items.append(get_metadata(client, result)) # 获取metadata
    return {"name": name, "doujinshis": items}

def rename_group_by_id(client, id: str, name: str) -> int:
    if not client.sismember("data:groups", id):
        return -1
    if not set_name_of_group(client, id, name):
        return 0 # 同名group已存在
    logging.info(f"rename group " + client.get(f"group:{id}") + " to " + name)
    return 1

def delete_group_by_id(client, id: str) -> bool:
    if not client.sismember("data:groups", id):
        return False
    delete_group_from_redis(client, id)
    logging.info(f"delete group {id}")
    return True

def add_to_group(client, id: str, did: str) -> bool:
    if not client.sismember("data:groups", id):
        return False
    return set_group_of_doujinshi(client, id, did, False)

def delete_from_group(client, id: str, did: str) -> bool:
    if not client.sismember("data:groups", id):
        return False
    return rm_group_of_doujinshi(client, id, did)