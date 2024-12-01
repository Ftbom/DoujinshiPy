import os
import hashlib
import random
import logging
from lib.utils import (get_values_from_list_by_page, get_all_values_from_list, get_all_values_from_set, 
                       delete_group_from_redis, set_name_of_group,set_metadata_of_doujinshi, delete_doujinshi_from_redis)

def translate_tags(client, tags):
    new_tags = []
    for tag in tags:
        tag_parts = tag.split(":")
        if len(tag_parts) == 1:
            new_tags.append(tag)
        else:
            tag_type = tag_parts[0].strip()
            tag_value = tag_parts[1].strip()
            if tag_type in ["male", "female", "mixed", "other"]:
                tag_type_ = "other"
            else:
                tag_type_ = tag_type
            if client.exists(f"ehtag:{tag_type_}"):
                value = client.hget(f"ehtag:{tag_type_}", tag_value)
                if not value == None:
                    new_tags.append(f"{tag_type}:{value}")
                else:
                    new_tags.append(tag)
            else:
                new_tags.append(tag)
    return new_tags

def get_metadata(client, id: str, tag_database = None) -> dict:
    doujinshi = client.hgetall(f"doujinshi:{id}")
    tags = doujinshi["tags"].split("|")
    tags = [item for item in tags if item != ""]
    if not tag_database == None:
        translated_tags = translate_tags(client, tags)
    else:
        translated_tags = None
    # 获取group
    groups = []
    group_ids = doujinshi["groups"].split("|")
    group_ids = [item for item in group_ids if item != ""]
    for gid in group_ids:
        groups.append(client.get(f"group:{gid}"))
    # 获取封面
    thumb_path = f".data/thumb/{id}.jpg"
    if not os.path.exists(thumb_path):
        cover_url = "/doujinshi/nothumb/thumbnail"
    else:
        cover_url = f"/doujinshi/{id}/thumbnail"
    if translated_tags == None:
        return {"id": id, "title": doujinshi["title"], "source": doujinshi["source"],
                "groups": groups, "tags": tags, "cover": cover_url}
    return {"id": id, "title": doujinshi["title"], "source": doujinshi["source"],
                "groups": groups, "tags": tags, "translated_tags": translated_tags, "cover": cover_url}

def get_doujinshi_list(client, page, max_perpage, tag_database) -> dict:
    doujinshi = []
    if page == -1:
        results = get_all_values_from_list(client, "data:doujinshis", max_perpage)
    else:
        results = get_values_from_list_by_page(client, "data:doujinshis", page, max_perpage)
    for result in results:
        doujinshi.append(get_metadata(client, result, tag_database))
    return doujinshi

def get_random_doujinshi_list(client, tag_database) -> dict:
    # 获取列表的长度
    list_length = client.llen("data:doujinshis")
    if list_length == 0:
        return []
    # 随机选择一个索引
    random_index = random.randint(0, max(list_length - 5, 0))
    results = client.lrange("data:doujinshis", random_index, random_index + 4)
    doujinshi = []
    for result in results:
        doujinshi.append(get_metadata(client, result, tag_database))
    return doujinshi

def get_doujinshi_by_id(client, id: str, tag_database) -> dict:
    if not client.exists(f"doujinshi:{id}"):
        return {}
    return get_metadata(client, id, tag_database)

def delete_metadata(client, id: str) -> dict:
    if not client.exists(f"doujinshi:{id}"):
        return False
    delete_doujinshi_from_redis(client, id)
    try:
        os.remove(f".data/thumb/{id}.jpg")
    except:
        pass
    return True

def generate_id_from_querys(query, tags, group, source_name):
    q_str = f"{query}_{'|'.join(tags)}_{group}_{source_name}"
    return hashlib.md5(q_str.encode('utf-8')).hexdigest()

def search_doujinshi(client, parameters, max_perpage, tag_database) -> dict:
    cursor = 0
    matched_titles = []
    query_key = "tmp:" + generate_id_from_querys(parameters[0], parameters[1], parameters[2], parameters[3])
    if not client.exists(query_key):
        # 筛选并缓存结果
        results = []
        count = 0
        while True:
            # HSCAN 逐步扫描哈希字段
            cursor, fields = client.hscan("data:titles", cursor = cursor, match = f"*{parameters[0]}*", count = 100)
            for key in fields.keys():
                for id in fields[key].split("$"):
                    matched_titles.append(id)
            if cursor == 0:
                break
        for id in matched_titles:
            result = client.hgetall(f"doujinshi:{id}")
            if len(parameters[1]) != 0: # 应用tag筛选
                r_tags = result["tags"].split("|")
                r_tags = [item for item in r_tags if item != ""]
                skip = False
                for i in parameters[1]:
                    if not i in r_tags:
                        skip = True
                        break
                if skip:
                    continue
            if len(parameters[2]) != 0: # 应用group筛选
                r_groups = result["groups"].split("|")
                r_groups = [item for item in r_groups if item != ""]
                if not parameters[2] in r_groups:
                    continue
            if len(parameters[3]) != 0: # 应用源筛选
                if parameters[3] != result["source"]:
                    continue
            client.rpush(query_key, id)
            if (count >= parameters[4] * max_perpage) and (count < (parameters[4] + 1) * max_perpage):
                results.append(id)
            count = count + 1
        client.expire(query_key, 1800) # 30min过期
    else:
        # 缓存未过期
        results = get_values_from_list_by_page(client, query_key, parameters[4], max_perpage)
    doujinshi = []
    for result in results:
        doujinshi.append(get_metadata(client, result, tag_database))
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

def get_doujinshi_by_group(client, id: str, page: int, max_perpage: int, tag_database) -> dict:
    name = client.get(f"group:{id}")
    if name == None:
        return {}
    results = get_values_from_list_by_page(client, f"data:group_{id}", page, max_perpage)
    items = []
    for result in results:
        items.append(get_metadata(client, result, tag_database)) # 获取metadata
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