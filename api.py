import os
import jwt
import redis
import importlib
import threading
from enum import Enum
from lib.scan import *
from lib.page import *
from lib.utils import *
from lib.batch import *
from lib.database import *
from pydantic import BaseModel
from fastapi import FastAPI, Depends
from lib.utils import get_file_infos
from sqlmodel import SQLModel, create_engine
from starlette.responses import FileResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

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
    target: list[str]
    replace: bool

class GroupName(BaseModel):
    name: str

class EditMetaData(BaseModel):
    title: str
    tag: list[str]

app = FastAPI()

secret_key = "uzfWtX8F9bUa691ve55BFHyRh1Br6b0mRhcJWqWFynXxhuR10jE"
oauth2 = OAuth2PasswordBearer(tokenUrl = "/token")

app_state = {
    "settings": load_settings(),
    "sources": load_sources(), # 从配置文件读取源配置
    "database_engine": create_engine("sqlite:///.data/database.db"), # 加载sqlite数据库
    "redis_client": redis.Redis(decode_responses = True) # 创建redis客户端
}

SQLModel.metadata.create_all(app_state["database_engine"])

@app.get("/")
def get_status(token: str = Depends(oauth2)) -> dict:
    return {"sources": list(app_state["sources"]), # 可用源及“插件”
            "batch_operations": {"tag": get_file_infos("tag"), "cover": get_file_infos("cover")}}

@app.post("/token")
def get_token(input_data : OAuth2PasswordRequestForm = Depends()):
    user_str = app_state["settings"]["auth"]["user"]
    passwd_str = app_state["settings"]["auth"]["passwd"]
    if (input_data.username == user_str) and (input_data.password == passwd_str):
        return {"access_token": jwt.encode({"user": f"{user_str}_{passwd_str}"}, secret_key, algorithm = "HS256"),
                "token_type": "bearer"}
    else:
        return {"error": "wrong username or password"}

@app.get("/scan")
def get_scan_status(token: str = Depends(oauth2)) -> dict:
    client = app_state["redis_client"]
    scan_status_code = client.get("scan_status_code") # 获取扫描过程状态码
    scan_source_name = client.get("scan_source_name") # 获取扫描对象源名称
    if scan_status_code == None:
        scan_status_code = 0
        scan_source_name = ""
    else:
        scan_status_code = int(scan_status_code)
    # 状态信息
    scan_info = {0: "scanning has not started", 1: f"scanning the {scan_source_name} library, retrieving the doujinshi list...",
                 2: f"scanning the {scan_source_name} library, saving information to the database...", 3: f"the {scan_source_name} library has been scanned",
                 4: f"failed to scan the {scan_source_name} library"}
    if scan_status_code == 3 or scan_status_code == 4:
        client.delete("scan_status_code") # 未开始或已完成，重置信息
        client.delete("scan_source_name")
    return {"msg": scan_info[scan_status_code]} # 返回状态

@app.post("/scan")
def scan_library(scan: StartScan, token: str = Depends(oauth2)) -> dict:
    sources = app_state["sources"]
    if not scan.start: # 是否开始扫描
        return {"msg": ""}
    if not scan.source_name in sources: # 源名称是否正确
        return {"error": "incorrect source name"}
    if sources[scan.source_name].TYPE == SourceType.web: # web源不支持扫描
        return {"msg": "this source does not support scanning"}
    client = app_state["redis_client"]
    with client.lock("scan_status_lock", blocking = True, blocking_timeout = 1):
        # 加锁，防止同时发出扫描请求时，创建多个扫描线程
        scan_status_code = client.get("scan_status_code")
        if scan_status_code == None:
            scan_status_code = 0
        else:
            scan_status_code = int(scan_status_code)
        if scan_status_code in [1, 2]: # 扫描进行中
            return {"error": f"scanning the {client.get('scan_source_name')} library, please wait and try again later"}
        client.set("scan_status_code", 1) # 设置扫描已开始状态
    threading.Thread(target = scan_to_database,
                    args = (app_state, scan.source_name)).start()
    return {"msg": f"scanning has started, get the status of scanning process: /scan"}

@app.post("/add")
def add_to_library(add: AddLibrary, token: str = Depends(oauth2)) -> dict:
    sources = app_state["sources"]
    if not add.source_name in sources:
        return {"error": "incorrect source name"}
    if not sources[add.source_name].TYPE == SourceType.web: # 仅web源支持添加
        return {"msg": "this source does not support adding"}
    client = app_state["redis_client"]
    with client.lock("add_status_lock", blocking = True, blocking_timeout = 1):
        # 加锁，防止同时发出请求时，创建多个线程
        add_status = client.get("add_status")
        if add_status == None:
            add_status = "none"
        if (not str(add_status) == "none") and (not add_status == "finished"):
            return {"msg": "trying to add some doujinshi to library, please wait and try again later"}
        client.set("add_status", "started")
    threading.Thread(target = batch_add_to_library,
                     args = (app_state, add.target, add.source_name, add.replace)).start()
    return {"msg": f"adding has started, get the status of adding process: /add"}

@app.get("/add")
def get_add_status(token: str = Depends(oauth2)) -> dict:
    client = app_state["redis_client"]
    add_status = client.get("add_status")
    if add_status == None:
        add_status = "none"
    if add_status == "finished":
        client.delete("add_status")
    return {"msg": add_status}

@app.post("/batch")
def batch_operation(setting: BatchOperation, token: str = Depends(oauth2)) -> dict:
    client = app_state["redis_client"]
    # 获取批量操作状态
    with client.lock("batch_operation_lock", blocking = True, blocking_timeout = 1):
        # 加锁，防止同时发出请求时，创建多个线程
        operation_status = client.get("batch_operation")
        if operation_status == None:
            operation_status = "none"
        if (not operation_status == "none") and (not operation_status == "finished"):
            return {"msg": "some batch operations is running, please wait and try again later"}
        client.set("batch_operation", "started")
    if setting.operation == OperationType.group:
        if "|" in setting.name:
            return {"error": "group name should not contain '|'"}
        threading.Thread(target = batch_set_group, args = (app_state, setting.name, setting.target, setting.replace)).start()
        return {"msg": "start setting group, get the status: /batch"}
    else:
        # 加载并应用“插件”
        if not os.path.exists(os.path.join(setting.operation.value, f"{setting.name}.py")):
            return {"error": f"not support {setting.name} in {setting.operation.value} operation"}
        if setting.operation == OperationType.cover:
            threading.Thread(target = batch_get_cover, args = (app_state, setting.target, setting.replace,
                                importlib.import_module(f"cover.{setting.name}").get_cover)).start()
            return {"msg": "start getting cover, get the status: /batch"}
        elif setting.operation == OperationType.tag:
            threading.Thread(target = batch_get_tag, args = (app_state, setting.target, setting.replace,
                                importlib.import_module(f"tag.{setting.name}").get_tag)).start()
            return {"msg": "start getting tag, get the status: /batch"}

@app.get("/batch")
def get_batch_operation_status(token: str = Depends(oauth2)) -> dict:
    client = app_state["redis_client"]
    operation_status = client.get("batch_operation")
    if operation_status == None:
        operation_status = "none"
    if operation_status == "finished":
        client.delete("batch_operation")
    return {"msg": operation_status}

@app.get("/group")
def get_all_groups(token: str = Depends(oauth2)) -> dict:
    return {"msg": "success", "data": get_group_list(app_state["database_engine"])}

@app.get("/group/{id}")
def get_doujinshi_by_group_id(id: str, token: str = Depends(oauth2)) -> dict:
    try:
        result = get_doujinshi_by_group(app_state["database_engine"], id)
        if result == {}:
            return {"error": f"group {id} not exists"}
        return {"msg": "success", "data": result}
    except:
        return {"error": f"fail to get doujinshi by group {id}"}

@app.delete("/group/{id}")
def delete_group(id: str, token: str = Depends(oauth2)) -> dict:
    try:
        if delete_group_by_id(app_state["database_engine"], id):
            return {"msg": f"success to delete group {id}"}
        else:
            return {"error": f"group {id} not exists"}
    except:
        return {"error": f"fail to delete group {id}"}

@app.put("/group/{id}")
def update_group_name(id: str, group_name: GroupName, token: str = Depends(oauth2)) -> dict:
    try:
        res = rename_group_by_id(app_state["database_engine"], id, group_name.name)
        if res == 1:
            return {"msg": f"success to rename group {id}"}
        elif res == 0:
            return {"error": f"group {group_name.name} already exists"}
        elif res == -1:
            return {"error": f"group {id} not exists"}
    except:
        return {"error": f"fail to rename group {id}"}

@app.get("/doujinshi")
def get_all_doujinshis(random: Union[int, None] = None, token: str = Depends(oauth2)) -> dict:
    return {"msg": "success", "data": get_doujinshi_list(app_state["database_engine"], random)}

@app.get("/doujinshi/{id}/metadata")
def get_doujinshi_metadata(id: str, token: str = Depends(oauth2)) -> dict:
    try:
        result = get_doujinshi_by_id(app_state["database_engine"], id)
        if result == {}:
            return {"error": f"doujinshi {id} not exists"}
        return {"msg": "success", "data": result}
    except:
        return {"error": f"fail to get doujinshi by id {id}"}

@app.put("/doujinshi/{id}/metadata")
def set_doujinshi_metadata(id: str, edit: EditMetaData, token: str = Depends(oauth2)) -> dict:
    try:
        if set_metadata(app_state["database_engine"], id, edit):
            return {"msg": f"success to set metadata of doujinshi {id}"}
        else:
            return {"error": f"doujinshi {id} not exists"}
    except:
        return {"error": f"fail to set metadata of doujinshi {id}"}

@app.delete("/doujinshi/{id}/metadata")
def delete_doujinshi_metadata(id: str, token: str = Depends(oauth2)) -> dict:
    try:
        if delete_metadata(app_state["database_engine"], id):
            return {"msg": f"success to delete metadata of doujinshi {id}"}
        else:
            return {"error": f"doujinshi {id} not exists"}
    except:
        return {"error": f"fail to delete metadata of doujinshi {id}"}

@app.get("/doujinshi/{id}/pages")
def get_doujinshi_pages(id: str, token: str = Depends(oauth2)) -> dict:
    try:
        result = get_page_urls(app_state, id)
        if result == []:
            return {"error": f"doujinshi {id} not exists or source not enabled"}
        return {"msg": "success", "data": result}
    except:
        return {"error": f"fail to get pages of doujinshi {id}"}

@app.get("/doujinshi/{id}/page/{num}")
def get_doujinshi_page_by_number(id: str, num: int, token: str = Depends(oauth2)):
    client = app_state["redis_client"]
    new_thread = False
    with client.lock(f"{id}_read_lock", blocking = True, blocking_timeout = 5):
        # 获取缓存线程状态，防止重复创建线程
        read_thread = client.get(f"{id}_read")
        if read_thread == None:
            # 先设置状态，防止锁释放后其他请求创建线程
            client.set(f"{id}_read", 0)
            threading.Thread(target = read_pages, args = (app_state, id)).start()
            new_thread = True
    if new_thread or (read_thread == '0'):
        time.sleep(0.2) # 若已创建线程，或缓存线程还未设置状态，等待并重新获取状态
        read_thread = client.get(f"{id}_read")
    if read_thread == '-1':
        # client.delete(f"{id}_read") # reset
        return {"error": f"doujinshi {id} does not exist or source not enabled"}
    # wait page load status to be set
    try:
        count = 0
        while count < 20:
            # 等待10s，若页加载状态被释放，设置页加载状态（告诉缓存线程该加载的页码）
            num_status = client.get(f"{id}_page")
            if num_status == None:
                with client.lock(f"{id}_page_lock", blocking = True, blocking_timeout = 10):
                   # 再获取一次状态，防止两次请求同时等待锁释放进入状态设置，并因此先后设置状态，导致头一次设置被覆盖
                   if client.get(f"{id}_page") != None:
                       continue
                   client.set(f"{id}_page", num)
                break
            time.sleep(0.5)
            count = count + 1
        if count >= 20: # 超时
            return {"error": "busy to load pages, please try later"}
    except:
        return {"error": "busy to load pages, please try later"}
    count = 0
    file_path = f".data/cache/{id}/{num}.jpg"
    while count < 20: # 等待10s，等待页码缓存
        # 获取页码状态
        page_status = client.get(f"{id}_{num}")
        if page_status == '-1':
            client.delete(f"{id}_{num}") # 重置
            return {"error": f"doujinshi {id} not contain the {num} page"}
        if page_status == '0':
            client.delete(f"{id}_{num}") # 重置
            return {"error": f"fail to get page {num} of doujinshi {id}"}
        if os.path.exists(file_path): # 文件已存在，返回文件
            if os.path.getsize(file_path) > 0:
                return FileResponse(file_path)
        count = count + 1
        time.sleep(0.5)
    return {"error": f"fail to get page {num} of doujinshi {id}"} # 超时

@app.get("/doujinshi/{id}/thumbnail")
def get_thumbnail(id: str, token: str = Depends(oauth2)) -> FileResponse:
    thumb_path = get_thumb_by_id(app_state["database_engine"], id)
    if thumb_path == None:
        return {"error": f"doujinshi {id} not exist"}
    return FileResponse(thumb_path)

@app.get("/search")
def search(query: str, source_name: str = "", tag: str = "", group: str = "", token: str = Depends(oauth2)) -> dict:
    tag_list = tag.split("$")
    for i in range(len(tag_list)):
        tag_list[i] = tag_list[i].strip(" ")
    tag_list = [item for item in tag_list if item != ""]
    return {"msg": "success", "data": search_doujinshi(app_state["database_engine"],
                                                       (query, tag_list, group, source_name))}

@app.get("/web/{source_name}/search")
def search_web(source_name: str, query: str, page: int, token: str = Depends(oauth2)) -> dict:
    sources = app_state["sources"]
    if not source_name in sources:
        return {"error": "incorrect source name"}
    if not sources[source_name].TYPE == SourceType.web: # just web source support
        return {"error": "this source does not support web search"}
    obj = sources[source_name]
    if hasattr(obj, "search") and callable(getattr(obj, "search")):
        return {"msg": "success", "data": obj.search(query, page)}
    else:
        return {"error": "this source does not support web search"}

@app.get("/web/{source_name}/{id}/metadata")
def get_web_doujinshi(source_name: str, id: str, token: str = Depends(oauth2)) -> dict:
    sources = app_state["sources"]
    if not source_name in sources:
        return {"error": "incorrect source name"}
    if not sources[source_name].TYPE == SourceType.web: # just web source support
        return {"error": "this source does not support web metadata"}
    return {"msg": "success", "data": sources[source_name].get_metadata(id)}

@app.get("/web/{source_name}/{id}/pages")
def get_web_doujinshi_pages(source_name: str, id: str, token: str = Depends(oauth2)) -> dict:
    sources = app_state["sources"]
    if not source_name in sources:
        return {"error": "incorrect source name"}
    if not sources[source_name].TYPE == SourceType.web: # just web source support
        return {"error": "this source does not support web pages"}
    return {"msg": "success", "data": sources[source_name].get_pages(id)}