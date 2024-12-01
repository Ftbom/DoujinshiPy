import os
import time
import uuid
import json
import shutil
import requests
import importlib
import threading
from enum import Enum
from enum import Enum
from typing import Union
from pydantic import BaseModel
from sqlmodel import SQLModel, Session, select, Field, create_engine

class PasswdAuth(BaseModel):
    passwd: str

class StartScan(BaseModel):
    start: bool
    source_name: str

class AddLibrary(BaseModel):
    source_name: str
    target: list[str]
    replace: bool

class OperationType(Enum):
    cover = "cover"
    tag = "tag"
    group = "group"

class BatchOperation(BaseModel):
    operation: OperationType
    name: str
    target: list
    replace: bool

class GroupName(BaseModel):
    name: str

class EditMetaData(BaseModel):
    title: str
    tag: list[str]

class SourceType(Enum):
    local = 0
    cloud = 1
    web = 2

class Doujinshi(SQLModel, table = True):
    id: uuid.UUID = Field(default_factory = uuid.uuid4, primary_key = True) # 自动生成id
    title: str
    pagecount: Union[int, None] = None
    tags: str = ''
    groups: str = ''
    identifier: str
    type: SourceType = SourceType.local
    source: str

class Group(SQLModel, table = True):
    id: uuid.UUID = Field(default_factory = uuid.uuid4, primary_key = True) # 自动生成id
    name: str

# json转为Doujinshi类
def doujinshi_from_json(id, result: dict) -> Doujinshi:
    if result["pagecount"] == -1:
        pagecount = None
    else:
        pagecount = int(result["pagecount"])
    if result["type"] == "local":
        type = SourceType.local
    elif result["type"] == "web":
        type = SourceType.web
    elif result["type"] == "cloud":
        type = SourceType.cloud
    doujinshi = Doujinshi(id = uuid.UUID(id), title = result["title"], pagecount = pagecount,
                          tags = result["tags"], groups = result["groups"], identifier = result["identifier"],
                          type = type, source = result["source"])
    return doujinshi

def save_modified_to_sqlite(client) -> None:
    def save_group(session, client, id):
        data = client.get(f"group:{id}")
        if data == None:
            item = session.get(Group, uuid.UUID(id))
            if item:
                session.delete(item)
        else:
            session.merge(Group(id = uuid.UUID(id), name = data))
    def save_doujinshi(session, client, id):
        data = client.hgetall(f"doujinshi:{id}")
        if data == {}:
            item = session.get(Doujinshi, uuid.UUID(id))
            if item:
                session.delete(item)
        else:
            session.merge(doujinshi_from_json(id, data))
    time.sleep(300)
    with client.lock("modified_lock", blocking = True, blocking_timeout = 10):
        modified_ids = get_all_values_from_set(client, "modified")
        client.delete("modified")
    # 保存数据到sqlite
    engine = create_engine("sqlite:///.data/database.db")
    if not os.path.exists(".data/database.db"):
        SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        for _id in modified_ids:
            if _id.startswith("group_"):
                _id = _id[6 :]
                save_group(session, client, _id)
            elif _id.startswith("doujinshi_"):
                _id = _id[10 :]
                save_doujinshi(session, client, _id)
        session.commit()

def mark_modified(client, id: str, group: bool = False) -> None:
    with client.lock("modified_lock", blocking = True, blocking_timeout = 10):
        if not client.exists("modified"):
            threading.Thread(target = save_modified_to_sqlite, args = (client,)).start()
        if group:
            client.sadd("modified", f"group_{id}")
        else:
            client.sadd("modified", f"doujinshi_{id}")

# 获取set的所有子项
def get_all_values_from_set(client, key):
    cursor = 0
    results = []
    while True:
        cursor, members = client.sscan(key, cursor)
        for member in members:
            results.append(member)
        if cursor == 0:
            break
    return results

# 逐页从list获取数据
def get_values_from_list_by_page(client, key, page, max_perpage = 15):
    start = page * max_perpage  # 页面的起始索引
    end = start + max_perpage - 1  # 页面的结束索引
    return client.lrange(key, start, end)

# 获取list所有数据
def get_all_values_from_list(client, key, max_perpage = 15):
    results = []
    page = 0
    while True:
        # 获取当前页的数据
        page_results = get_values_from_list_by_page(client, key, page, max_perpage)
        if not page_results:
            break  # 如果没有数据了，跳出循环
        results.extend(page_results)
        page = page + 1  # 进入下一页
    return results

# 添加doujinshi到redis
def add_doujinshi_to_redis(client, doujinshi: Doujinshi, add_group = False, backup_sql = True) -> None:
    if doujinshi.pagecount == None:
        pagecount = -1
    else:
        pagecount = doujinshi.pagecount
    did = str(doujinshi.id)
    client.hset(f"doujinshi:{did}", mapping = {
        "title": doujinshi.title,
        "pagecount": pagecount,
        "tags": doujinshi.tags,
        "groups": doujinshi.groups,
        "identifier": doujinshi.identifier,
        "type": str(doujinshi.type).split(".")[1],
        "source": doujinshi.source
    })
    add_id_to_titles(client, did, doujinshi.title)
    client.rpush("data:doujinshis", did)
    if add_group:
        for g in doujinshi.groups.split("|"):
            if not g == "":
                client.rpush(f"data:group_{g}", did)
    if backup_sql:
        mark_modified(client, did)

def delete_id_from_titles(client, id, title) -> None:
    title_data = client.hget("data:titles", title)
    if title_data == id:
        client.hdel("data:titles", title)
    else:
        title_data = title_data.split("$")
        title_data.remove(id)
        client.hset("data:titles", title, "$".join(title_data))

def add_id_to_titles(client, id, title) -> None:
    title_data = client.hget("data:titles", title)
    if title_data == None:
        title_data = id
    else:
        title_data = title_data + "$" + id # title重复
    client.hset("data:titles", title, title_data)

# 删除doujinshi
def delete_doujinshi_from_redis(client, id, title = None, groups = None) -> None:
    if title == None:
        title = client.hget(f"doujinshi:{id}", "title")
    if groups == None:
        groups = client.hget(f"doujinshi:{id}", "groups")
    client.delete(f"doujinshi:{id}")
    delete_id_from_titles(client, id, title)
    client.lrem("data:doujinshis", 0, id)
    for g in groups.split("|"):
        if not g == "":
            client.lrem(f"data:group_{g}", 0, id)
    mark_modified(client, id)

# 设置doujinshi的group
def set_group_of_doujinshi(client, gid: str, target_id, replace_old: bool = False) -> bool:
    groups = client.hget(f"doujinshi:{target_id}", "groups")
    if groups == None:
        return False
    if replace_old:
        for g in groups.split("|"):
            if not g == "":
                client.lrem(f"data:group_{g}", 0, target_id)
        groups = [gid]
    else:
        groups = groups.split("|")
        if gid in groups:
            return True
        groups.append(gid)
    client.hset(f"doujinshi:{target_id}", "groups", "|".join(groups).strip("|"))
    client.rpush(f"data:group_{gid}", target_id)
    mark_modified(client, target_id)
    return True

def set_pagecount_of_doujinshi(client, id: str, pagecount: int) -> bool:
    client.hset(f"doujinshi:{id}", "pagecount", pagecount)
    mark_modified(client, id)

def set_metadata_of_doujinshi(client, id: str, tags: list, replace_old: bool = False, title: str = None) -> bool:
    old_tags = client.hget(f"doujinshi:{id}", "tags")
    if old_tags == None:
        return False
    if replace_old and tags != []:
        old_tags = tags
    else:
        old_tags = old_tags.split("|")
        for t in tags:
            if not t in old_tags:
                old_tags.append(t)
    client.hset(f"doujinshi:{id}", "tags", "|".join(old_tags).strip("|"))
    if title != None:
        old_title = client.hget(f"doujinshi:{id}", "title")
        if title != old_title:
            client.hset(f"doujinshi:{id}", "title", title)
            delete_id_from_titles(client, id, old_title)
            add_id_to_titles(client, id, title)
    mark_modified(client, id)
    return True

# 新建group
def add_group_to_redis(client, group: Group, backup_sql = True) -> None:
    gid = str(group.id)
    client.set(f"group:{gid}", group.name)
    client.sadd("data:groups", gid)
    if backup_sql:
        mark_modified(client, gid, True)

def set_name_of_group(client, id: str, name) -> bool:
    for gid in get_all_values_from_set(client, "data:groups"):
        if name == client.get(f"group:{gid}"):
            return False
    client.set(f"group:{id}", name)
    mark_modified(client, id, True)
    return True

# 删除group
def delete_group_from_redis(client, id) -> None:
    client.delete(f"group:{id}")
    client.srem("data:groups", id)
    ids = get_all_values_from_list(client, f"data:group_{id}")
    client.delete(f"data:group_{id}")
    for _id in ids:
        groups = client.hget(f"doujinshi:{_id}", "groups")
        new_groups = []
        for g in groups.split("|"):
            if not g == id:
                new_groups.append(g)
        client.hset(f"doujinshi:{_id}", "groups", "|".join(new_groups))
        mark_modified(client, _id)
    mark_modified(client, id, True)

# 加载数据库到redis
def load_database_to_redis(app_state) -> None:
    if not os.path.exists(".data/database.db"):
        return
    client = app_state["redis_client"]
    engine = create_engine("sqlite:///.data/database.db")
    avaliable_sources = list(app_state["sources"].keys())
    with Session(engine) as session:
        results = session.exec(select(Doujinshi))
        for result in results:
            if result.source in avaliable_sources:
                add_doujinshi_to_redis(client, result, True, False)
        results = session.exec(select(Group))
        for result in results:
            add_group_to_redis(client, result, False)

def get_cache_size() -> int:
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(".data/cache"):
        for filename in filenames:
            file_path = os.path.join(dirpath, filename)
            if os.path.isfile(file_path):
                total_size = total_size + os.path.getsize(file_path)
    return total_size

def update_ehtag_database(proxy):
    print("check for EhTagTranslation database update...")
    releases_url = "https://api.github.com/repos/EhTagTranslation/Database/releases"
    content = requests.get(releases_url, proxies = proxy).content
    json_data = json.loads(content)
    release_tag_name = json_data[0]["tag_name"]
    if not os.path.exists(f".data/tag_database.{release_tag_name}.json"):
        for file_name in os.listdir(".data"):
            if "tag_database" in file_name:
                try:
                    os.remove(os.path.join(".data", file_name))
                except:
                    pass
        print("find new version, try to download...")
        download_url = "https://github.com/EhTagTranslation/Database/releases/latest/download/db.text.json"
        content = requests.get(download_url, proxies = proxy).content
        json_data = json.loads(content)
        data = {}
        for t in json_data["data"][1 :]:
            data_content = {}
            for i in t["data"].keys():
                data_content[i] = t["data"][i]["name"]
            if t["namespace"] == "reclass":
                data["category"] = data_content
            else:
                data[t["namespace"]] = data_content
        with open(f".data/tag_database.{release_tag_name}.json", "wb") as f:
            f.write(json.dumps(data).encode("utf-8"))
    return release_tag_name

def load_ehtag_database_to_redis(app_state) -> None:
    if not app_state["settings"]["tag_translate"] == None:
        with open(f".data/tag_database.{app_state['settings']['tag_translate']}.json", "rb") as f:
            tag_database = json.loads(f.read())
        client = app_state["redis_client"]
        for key in tag_database.keys():
            if key in ["male", "female", "mixed", "other"]:
                key_ = "other"
            else:
                key_ = key
            for k in tag_database[key].keys():
                client.hset(f"ehtag:{key_}", mapping = {k: tag_database[key][k]})

def app_init(app_state) -> None:
    client = app_state["redis_client"]
    try:
        client.flushall()
    except:
        print("please start redis first")
        exit()
    os.makedirs(".data/cache", exist_ok = True)
    os.makedirs(".data/thumb", exist_ok = True)
    # 缓存大小检查
    cache_size = get_cache_size()
    cache_size_limit = app_state["settings"]["max_cache_size"] * 1024 * 1024
    if cache_size >= cache_size_limit:
        try:
            shutil.rmtree(".data/cache")
        except:
            pass
        os.makedirs(".data/cache", exist_ok = True)
        cache_size = 0
    client.set("cache_size", cache_size)
    client.set("cache_size_limit", cache_size_limit)
    load_database_to_redis(app_state)
    load_ehtag_database_to_redis(app_state)

def load_settings() -> dict:
    with open(".data/config.json", "r", encoding = "utf-8") as f:
        settings = json.loads(f.read())["settings"]
    if settings["proxy"] != "":
        settings["proxy"] = {"http": settings["proxy"], "https": settings["proxy"]}
    else:
        settings["proxy"] = {}
    if settings["tag_translate"]:
        settings["tag_translate"] = update_ehtag_database(settings["proxy"])
    else:
        settings["tag_translate"] = None
    return settings

def load_sources() -> dict:
    sources = {}
    # 读取配置
    with open(".data/config.json", "r", encoding = "utf-8") as f:
        source_config = json.loads(f.read())["source"]
    for key in source_config.keys():
        sources[key] = importlib.import_module(f"source.{source_config[key]['type']}").Source(source_config[key]["config"])
    return sources

def get_sources() -> list:
    with open(".data/config.json", "r", encoding = "utf-8") as f:
        source_config = json.loads(f.read())["source"]
    with open(os.path.join("source", "info.json"), "rb") as f:
        infos = json.loads(f.read())
    s = {}
    for i in source_config.keys():
        s[i] = infos[source_config[i]["type"]]
    return s

def get_file_infos(path: str) -> list:
    with open(os.path.join(path, "info.json"), "rb") as f:
        infos = json.loads(f.read())
    s = []
    for i in os.listdir(path):
        n, e = os.path.splitext(i)
        if e in [".py", ".PY"] and (not n == "__init__"):
            s.append({"name": infos[n]["name"], "value": n, "description": infos[n]["description"]})
    return s