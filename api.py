import os
import json
import hashlib
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
from pymemcache.client.base import Client
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

class SearchParameter(BaseModel):
    query: str
    tag: list[str]
    group: str
    source: str

class JsonSerde(object):
    def serialize(self, key, value):
        if isinstance(value, str):
            return value.encode("utf-8"), 1
        return json.dumps(value).encode("utf-8"), 2

    def deserialize(self, key, value, flags):
       if flags == 1:
           return value.decode("utf-8")
       if flags == 2:
           return json.loads(value.decode("utf-8"))
       raise Exception("Unknown serialization format")

app = FastAPI()

salt = "uzfWtX8F9bUa691ve55BFHyRh1Br6b0mRhcJWqWFynXxhuR10jE"
oauth2 = OAuth2PasswordBearer(tokenUrl = "/token")

app_state = {
    "settings": load_settings(),
    "sources": load_sources(), # load source configration from file
    "database_engine": create_engine("sqlite:///.data/database.db"), # load database
    "memcached_client": Client("localhost", serde=JsonSerde()) # create client
}

SQLModel.metadata.create_all(app_state["database_engine"])

@app.get("/")
def get_status(token: str = Depends(oauth2)) -> dict:
    return {"sources": list(app_state["sources"]),
            "batch_operations": {"tag": get_file_infos("tag"), "cover": get_file_infos("cover")}}

@app.post("/token")
def get_token(input_data : OAuth2PasswordRequestForm = Depends()):
    user_str = app_state["settings"]["auth"]["user"]
    passwd_str = app_state["settings"]["auth"]["passwd"]
    if (input_data.username == user_str) and (input_data.password == passwd_str):
        return {"access_token": hashlib.sha256((app_state["settings"]["auth"]["passwd"] + salt).encode("utf-8")).hexdigest(),
                "token_type": "bearer"}
    else:
        return {"error": "wrong username or password"}

@app.get("/scan")
def get_scan_status(token: str = Depends(oauth2)) -> dict:
    client = app_state["memcached_client"]
    scan_status_code = client.get("scan_status_code") # get status code of the scanning process
    scan_source_name = client.get("scan_source_name") # get source name of the scanning process
    if scan_status_code == None:
        scan_status_code = 0
        scan_source_name = ""
    scan_info = {0: "scanning has not started", 1: f"scanning the {scan_source_name} library, retrieving the doujinshi list...",
                 2: f"scanning the {scan_source_name} library, saving information to the database...", 3: f"the {scan_source_name} library has been scanned",
                 4: f"failed to scan the {scan_source_name} library"}
    if scan_status_code == 3 or scan_status_code == 4:
        client.delete("scan_status_code") # reset the status code
        client.delete("scan_source_name")
    return {"msg": scan_info[scan_status_code]} # return scan status

@app.post("/scan")
def scan_library(scan: StartScan, token: str = Depends(oauth2)) -> dict:
    sources = app_state["sources"]
    if not scan.start: # start scan or not
        return {"msg": ""}
    if not scan.source_name in sources:
        return {"error": "incorrect source name"}
    if sources[scan.source_name].TYPE == SourceType.web: # web source not support scanning
        return {"msg": "this source does not support scanning"}
    client = app_state["memcached_client"]
    scan_status_code = client.get("scan_status_code")
    if scan_status_code == None:
        scan_status_code = 0
    if scan_status_code in [1, 2]: # scanning has started
        return {"error": f"scanning the {client.get('scan_source_name')} library, please wait and try again later"}
    else:
        threading.Thread(target = scan_to_database,
                         args = (app_state, scan.source_name)).start()
        return {"msg": f"scanning has started, get the status of scanning process: /scan"}

@app.post("/add")
def add_to_library(add: AddLibrary, token: str = Depends(oauth2)) -> dict:
    sources = app_state["sources"]
    if not add.source_name in sources:
        return {"error": "incorrect source name"}
    if not sources[add.source_name].TYPE == SourceType.web: # just web source support add
        return {"msg": "this source does not support adding"}
    client = app_state["memcached_client"]
    add_status = client.get("add_status")
    if add_status == None:
        add_status = "none"
    if (not add_status == "none") and (not add_status == "finished"):
        return {"msg": "trying to add some doujinshi to library, please wait and try again later"}
    else:
        threading.Thread(target = batch_add_to_library,
                         args = (app_state, add.target, add.source_name, add.replace)).start()
        return {"msg": f"adding has started, get the status of adding process: /add"}

@app.get("/add")
def get_add_status(token: str = Depends(oauth2)) -> dict:
    client = app_state["memcached_client"]
    add_status = client.get("add_status")
    if add_status == None:
        add_status = "none"
    if add_status == "finished":
        client.delete("add_status")
    return {"msg": add_status}

@app.post("/batch")
def batch_operation(setting: BatchOperation, token: str = Depends(oauth2)) -> dict:
    client = app_state["memcached_client"]
    # get status
    operation_status = client.get("batch_operation")
    if operation_status == None:
        operation_status = "none"
    if (not operation_status == "none") and (not operation_status == "finished"):
        return {"msg": "some batch operations is running, please wait and try again later"}
    if setting.operation == OperationType.group:
        if "|" in setting.name:
            return {"error": "group name should not contain '|'"}
        threading.Thread(target = batch_set_group, args = (app_state, setting.name, setting.target, setting.replace)).start()
        return {"msg": "start setting group, get the status: /batch"}
    else:
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
    client = app_state["memcached_client"]
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
    client = app_state["memcached_client"]
    read_thread = client.get(f"{id}_read")
    if read_thread == None:
        threading.Thread(target = read_pages, args = (app_state, id)).start()
        time.sleep(0.2) # wait status to be set
        read_thread = client.get(f"{id}_read")
    if read_thread == -1:
        client.delete(f"{id}_read") # reset
        return {"error": f"doujinshi {id} does not exist or source not enabled"}
    # wait load status to be set
    count = 0
    while count < 50 and client.get(f"{id}_page") != None: # max wait for 10s
        count = count + 1
        time.sleep(0.2)
    if client.get(f"{id}_page") != None:
        return {"error": "busy to load pages, please try later"}
    client.set(f"{id}_page", num)
    # wait page to cache
    count = 0
    file_path = f".data/cache/{id}/{num}.jpg"
    while count < 20: # max wait for 10s
        page_status = client.get(f"{id}_{num}")
        if page_status == -1:
            client.delete(f"{id}_{num}") # reset
            return {"error": f"doujinshi {id} not contain the {num} page"}
        if page_status == 0:
            client.delete(f"{id}_{num}") # reset
            return {"error": f"fail to get page {num} of doujinshi {id}"}
        if os.path.exists(file_path):
            return FileResponse(file_path)
        count = count + 1
        time.sleep(0.5)
    return {"error": f"fail to get page {num} of doujinshi {id}"}

@app.get("/doujinshi/{id}/thumbnail")
def get_thumbnail(id: str, token: str = Depends(oauth2)) -> FileResponse:
    thumb_path = get_thumb_by_id(app_state["database_engine"], id)
    if thumb_path == None:
        return {"error": f"doujinshi {id} not exist"}
    return FileResponse(thumb_path)

@app.post("/search")
def search(parameter: SearchParameter, token: str = Depends(oauth2)) -> dict:
    return {"msg": "success", "data": search_doujinshi(app_state["database_engine"], parameter)}

@app.get("/web/{source_name}/search")
def search_web(source_name: str, query: str, page: int, token: str = Depends(oauth2)) -> dict:
    sources = app_state["sources"]
    if not source_name in sources:
        return {"error": "incorrect source name"}
    if not sources[source_name].TYPE == SourceType.web: # just web source support
        return {"error": "this source does not support web search"}
    obj = sources[source_name]
    if hasattr(obj, "search") and callable(getattr(obj, "search")):
        return {"msg": "success", "data": obj.search(query, page, app_state["settings"]["proxy"])}
    else:
        return {"error": "this source does not support web search"}

@app.get("/web/{source_name}/{id}/metadata")
def get_web_doujinshi(source_name: str, id: str, token: str = Depends(oauth2)) -> dict:
    sources = app_state["sources"]
    if not source_name in sources:
        return {"error": "incorrect source name"}
    if not sources[source_name].TYPE == SourceType.web: # just web source support
        return {"error": "this source does not support web metadata"}
    return {"msg": "success", "data": sources[source_name].get_metadata(id, app_state["settings"]["proxy"])}

@app.get("/web/{source_name}/{id}/pages")
def get_web_doujinshi_pages(source_name: str, id: str, token: str = Depends(oauth2)) -> dict:
    sources = app_state["sources"]
    if not source_name in sources:
        return {"error": "incorrect source name"}
    if not sources[source_name].TYPE == SourceType.web: # just web source support
        return {"error": "this source does not support web pages"}
    return {"msg": "success", "data": sources[source_name].get_pages(id, app_state["settings"]["proxy"])}