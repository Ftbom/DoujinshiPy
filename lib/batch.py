import os
import logging
from lib.utils import (Group, add_group_to_redis, doujinshi_from_json,
            get_all_values_from_set, set_group_of_doujinshi, set_metadata_of_doujinshi)

def batch_set_group(app_state, group_name: str, id_list: list[str], replace_old: bool) -> None:
    client = app_state["redis_client"]
    num = len(id_list)
    new_group = True
    group_id = None
    for gid in get_all_values_from_set(client, "data:groups"):
        if group_name == client.get(f"group:{gid}"):
            new_group = False
            group_id = gid
            break
    if new_group: # 新的group名称，新建group
        group_object = Group(name = group_name)
        group_id = str(group_object.id)
        add_group_to_redis(client, group_object)
    count = 0
    for id in id_list:
        count = count + 1
        if (type(id) != str) and (type(id) != list):
            continue # 不支持的数据类型
        if type(id) == list:
            if len(id) == 0:
                continue # 无数据
            id = str(id[0])
        if not set_group_of_doujinshi(client, group_id, id, replace_old):
            logging.warning(f"don't find id {id}, skip setting group")
        else:
            logging.info(f"set group for {id}")
        client.set("batch_operation", f"setting group {count}/{num}")
    client.set("batch_operation", "finished")

def batch_get_cover(app_state, id_list: list[str], replace_old: bool, func) -> None:
    client = app_state["redis_client"]
    num = len(id_list)
    count = 0
    for id in id_list:
        count = count + 1
        client.set("batch_operation", f"getting cover {count}/{num}")
        # 处理id，可为字符串或列表（二元）
        if (type(id) != str) and (type(id) != list):
            continue
        if (type(id) == list):
            if len(id) == 0:
                continue
            elif len(id) == 1:
                id = str(id[0])
                url = None
            else:
                url = str(id[1])
                id = str(id[0])
        else:
            url = None
        result = client.hgetall(f"doujinshi:{id}")
        if result == {}:
            logging.warning(f"don't find id {id}, skip getting cover")
            continue
        if not replace_old:
            if os.path.exists(f".data/thumb/{id}.jpg"):
                continue
        # 获取信息
        try:
            img_bytes = func(app_state["sources"][result["source"]], app_state["settings"]["proxy"],
                 doujinshi_from_json(id, result), url) # 获取封面的函数
            with open(f".data/thumb/{id}.jpg", "wb") as f:
                if len(img_bytes) > 0:
                    f.write(img_bytes)
                else:
                    raise RuntimeError("failed to get cover bytes")
            logging.info(f"get cover {id}.jpg")
        except Exception as e:
            logging.error(f"failed to get cover {id}.jpg, error message: {e}")
    client.set("batch_operation", "finished")

def batch_get_tag(app_state, id_list: list[str], replace_old: bool, func) -> None:
    client = app_state["redis_client"]
    num = len(id_list)
    count = 0
    for id in id_list:
        count = count + 1
        client.set("batch_operation", f"getting tag {count}/{num}")
        if (type(id) != str) and (type(id) != list):
            continue
        if (type(id) == list):
            if len(id) == 0:
                continue
            elif len(id) == 1:
                id = str(id[0])
                url = None
            else:
                url = str(id[1])
                id = str(id[0])
        else:
            url = None
        result = client.hgetall(f"doujinshi:{id}")
        if result == {}:
            logging.warning(f"don't find id {id}, skip getting tag")
        else:
            try:
                new_tags = func(app_state["sources"][result["source"]], app_state["settings"]["proxy"],
                                doujinshi_from_json(id, result), url) # 获取tag的函数
                set_metadata_of_doujinshi(client, id, new_tags, replace_old)
                logging.info(f"get tag for {id}")
            except:
                logging.error(f"failed to get tag for {id}")
    client.set("batch_operation", "finished")
        