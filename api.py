import os
import redis
import importlib
import threading
from lib.scan import *
from lib.page import *
from lib.utils import *
from lib.batch import *
from lib.database import *
from fastapi import FastAPI, HTTPException, Depends, status, Request
from lib.utils import get_file_infos
from starlette.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.security import OAuth2PasswordBearer

app = FastAPI()

oauth2 = OAuth2PasswordBearer(tokenUrl = "token")

app_state = {
    "settings": load_settings(),
    "sources": load_sources(), # 从配置文件读取源配置
}

app_state["redis_client"] = redis.Redis(decode_responses = True, db = app_state["settings"]["redis_db"]) # 创建redis客户端

# 自定义 token 验证函数
def verify_token(token: str):
    if app_state["settings"]["passwd"] == "":
        return
    if token != app_state["settings"]["passwd"]:
        raise HTTPException(
            status_code = status.HTTP_401_UNAUTHORIZED,
            detail = "Invalid token",
            headers = {"WWW-Authenticate": "Bearer"},
        )

def get_range_header(range_header: str, file_size: int) -> tuple[int, int]:
    def _invalid_range():
        return HTTPException(
            status.HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE,
            detail=f"Invalid request range (Range:{range_header!r})",
        )
    try:
        h = range_header.replace("bytes=", "").split("-")
        start = int(h[0]) if h[0] != "" else 0
        end = int(h[1]) if h[1] != "" else file_size - 1
    except ValueError:
        raise _invalid_range()
    if start > end or start < 0 or end > file_size - 1:
        raise _invalid_range()
    return start, end

# 生成streaming响应
def range_requests_response(source, file_id: str, range_header: str) -> StreamingResponse:
    source = app_state["sources"][source]
    file_real_size = source.decrypted_file_size(file_id)
    headers = {
        "content-type": "application/octet-stream",
        "accept-ranges": "bytes",
        "content-encoding": "identity",
        "content-length": str(file_real_size),
        "access-control-expose-headers": (
            "content-type, accept-ranges, content-length, "
            "content-range, content-encoding"
        ),
    }
    # 计算content-length和content-range
    start = 0
    end = file_real_size - 1
    status_code = status.HTTP_200_OK
    if range_header is not None:
        start, end = get_range_header(range_header, file_real_size)
        size = end - start + 1
        headers["content-length"] = str(size)
        headers["content-range"] = f"bytes {start}-{end}/{file_real_size}"
        status_code = status.HTTP_206_PARTIAL_CONTENT
    return StreamingResponse(
        source.decrypted_bytes(file_id, start, end),
        headers=headers,
        status_code=status_code,
    )

@app.get("/favicon.ico", include_in_schema = False)
def favicon():
    return FileResponse("static/icons/favicon.ico")

@app.get("/decrypt/{source}", include_in_schema = False)
def decrypt(request: Request, source: str, id: str, token: str = Depends(oauth2)):
    verify_token(token)
    return range_requests_response(source, id, request.headers.get("range"))

@app.head("/decrypt/{source}", include_in_schema = False)
def decrypt_head(source: str, id: str, token: str = Depends(oauth2)):
    verify_token(token)
    return Response(
        headers={
            "Content-Length": str(app_state["sources"][source].decrypted_file_size(id)),
            "Content-Type": "application/zip"
        }
    )

@app.get("/")
def get_status(token: str = Depends(oauth2)) -> dict:
    verify_token(token)
    return {"info": {"proxy_webpage": app_state["settings"]["proxy_webpage"],
                     "max_num_perpage": app_state["settings"]["max_num_perpage"]},
                "sources": get_sources(), # 可用源及“插件”
                "batch_operations": {"tag": get_file_infos("tag"), "cover": get_file_infos("cover")}}

@app.post("/settings")
def update_settings(settings: SettingValues, token: str = Depends(oauth2)) -> dict:
    verify_token(token)
    app_state["settings"]["proxy_webpage"] = bool(settings.proxy_webpage)
    app_state["settings"]["max_num_perpage"] = int(settings.max_num_perpage)
    with open(".data/config.json", "rb") as f:
        s = json.loads(f.read())
    s["settings"]["proxy_webpage"] = bool(settings.proxy_webpage)
    s["settings"]["max_num_perpage"] = int(settings.max_num_perpage)
    with open(".data/config.json", "w") as f:
        f.write(json.dumps(s, indent = 4))
    return {"msg": "success"}

@app.get("/scan")
def get_scan_status(token: str = Depends(oauth2)) -> dict:
    verify_token(token)
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
    verify_token(token)
    sources = app_state["sources"]
    if not scan.start: # 是否开始扫描
        return {"msg": ""}
    if not scan.source_name in sources: # 源名称是否正确
        return JSONResponse({"error": "incorrect source name"}, status_code = 404)
    if sources[scan.source_name].TYPE == SourceType.web: # web源不支持扫描
        return JSONResponse({"error": "this source does not support scanning"}, status_code = 400)
    client = app_state["redis_client"]
    with client.lock("scan_status_lock", blocking = True, blocking_timeout = 1):
        # 加锁，防止同时发出扫描请求时，创建多个扫描线程
        scan_status_code = client.get("scan_status_code")
        if scan_status_code == None:
            scan_status_code = 0
        else:
            scan_status_code = int(scan_status_code)
        if scan_status_code in [1, 2]: # 扫描进行中
            return JSONResponse({"error": f"scanning the {client.get('scan_source_name')} library, please wait and try again later"},
                                 status_code = 503)
        client.set("scan_status_code", 1) # 设置扫描已开始状态
    threading.Thread(target = scan_to_database,
                    args = (app_state, scan.source_name)).start()
    return {"msg": f"scanning has started, get the status of scanning process: /scan"}

@app.post("/add")
def add_to_library(add: AddLibrary, token: str = Depends(oauth2)) -> dict:
    verify_token(token)
    sources = app_state["sources"]
    if not add.source_name in sources:
        return JSONResponse({"error": "incorrect source name"}, status_code = 404)
    if not sources[add.source_name].TYPE == SourceType.web: # 仅web源支持添加
        return JSONResponse({"error": "this source does not support adding"}, status_code = 400)
    client = app_state["redis_client"]
    with client.lock("add_status_lock", blocking = True, blocking_timeout = 1):
        # 加锁，防止同时发出请求时，创建多个线程
        add_status = client.get("add_status")
        if add_status == None:
            add_status = "none"
        if (not str(add_status) == "none") and (not add_status == "finished"):
            return JSONResponse({"msg": "trying to add some doujinshi to library, please wait and try again later"}, status_code = 503)
        client.set("add_status", "started")
    threading.Thread(target = batch_add_to_library,
                     args = (app_state, add.target, add.source_name, add.replace)).start()
    return {"msg": f"adding has started, get the status of adding process: /add"}

@app.get("/add")
def get_add_status(token: str = Depends(oauth2)) -> dict:
    verify_token(token)
    client = app_state["redis_client"]
    add_status = client.get("add_status")
    if add_status == None:
        add_status = "none"
    if add_status == "finished":
        client.delete("add_status")
    return {"msg": add_status}

@app.post("/batch")
def batch_operation(setting: BatchOperation, token: str = Depends(oauth2)) -> dict:
    verify_token(token)
    client = app_state["redis_client"]
    # 获取批量操作状态
    with client.lock("batch_operation_lock", blocking = True, blocking_timeout = 1):
        # 加锁，防止同时发出请求时，创建多个线程
        operation_status = client.get("batch_operation")
        if operation_status == None:
            operation_status = "none"
        if (not operation_status == "none") and (not operation_status == "finished"):
            return JSONResponse({"msg": "some batch operations is running, please wait and try again later"}, status_code = 503)
        client.set("batch_operation", "started")
    if setting.operation == OperationType.group:
        if "|" in setting.name:
            client.delete("batch_operation")
            return JSONResponse({"error": "group name should not contain '|'"}, status_code = 400)
        threading.Thread(target = batch_set_group, args = (app_state, setting.name, setting.target, setting.replace)).start()
        return {"msg": "start setting group, get the status: /batch"}
    else:
        # 加载并应用“插件”
        if not os.path.exists(os.path.join(setting.operation.value, f"{setting.name}.py")):
            client.delete("batch_operation")
            return JSONResponse({"error": f"not support {setting.name} in {setting.operation.value} operation"}, status_code = 400)
        if setting.operation == OperationType.cover:
            threading.Thread(target = batch_get_cover, args = (app_state, setting.target, setting.replace,
                                importlib.import_module(f"cover.{setting.name}").get_cover, (setting.name == "thumbnail"))).start()
            return {"msg": "start getting cover, get the status: /batch"}
        elif setting.operation == OperationType.tag:
            threading.Thread(target = batch_get_tag, args = (app_state, setting.target, setting.replace,
                                importlib.import_module(f"tag.{setting.name}").get_tag)).start()
            return {"msg": "start getting tag, get the status: /batch"}

@app.get("/batch")
def get_batch_operation_status(token: str = Depends(oauth2)) -> dict:
    verify_token(token)
    client = app_state["redis_client"]
    operation_status = client.get("batch_operation")
    if operation_status == None:
        operation_status = "none"
    if operation_status == "finished":
        client.delete("batch_operation")
    return {"msg": operation_status}

@app.get("/group")
def get_all_groups(token: str = Depends(oauth2)) -> dict:
    verify_token(token)
    return {"msg": "success", "data": get_group_list(app_state["redis_client"])}

@app.get("/group/{id}")
def get_doujinshi_by_group_id(id: str, page: int = 0, token: str = Depends(oauth2)) -> dict:
    verify_token(token)
    try:
        result = get_doujinshi_by_group(app_state["redis_client"], id, page, app_state["settings"]["max_num_perpage"])
        if result == {}:
            return JSONResponse({"error": f"group {id} not exists"}, status_code = 404)
        return {"msg": "success", "data": result}
    except:
        return JSONResponse({"error": f"fail to get doujinshi by group {id}"}, status_code = 500)

@app.delete("/group/{id}")
def delete_group(id: str, token: str = Depends(oauth2)) -> dict:
    verify_token(token)
    try:
        if delete_group_by_id(app_state["redis_client"], id):
            return {"msg": f"success to delete group {id}"}
        else:
            return JSONResponse({"error": f"group {id} not exists"}, status_code = 404)
    except:
        return JSONResponse({"error": f"fail to delete group {id}"}, status_code = 500)

@app.put("/group/{id}")
def update_group_name(id: str, group_name: GroupName, token: str = Depends(oauth2)) -> dict:
    verify_token(token)
    try:
        res = rename_group_by_id(app_state["redis_client"], id, group_name.name)
        if res == 1:
            return {"msg": f"success to rename group {id}"}
        elif res == 0:
            return JSONResponse({"error": f"group {group_name.name} already exists"}, status_code = 409)
        elif res == -1:
            return JSONResponse({"error": f"group {id} not exists"}, status_code = 404)
    except:
        return JSONResponse({"error": f"fail to rename group {id}"}, status_code = 500)

@app.delete("/group/{id}/{did}")
def delete_doujinshi_from_group(id: str, did: str, token: str = Depends(oauth2)) -> dict:
    verify_token(token)
    try:
        if delete_from_group(app_state["redis_client"], id, did):
            return {"msg": f"success to delete doujinshi {did} from group {id}"}
        else:
            return JSONResponse({"error": f"group {id} or doujinshi {did} not exists"}, status_code = 404)
    except:
        return JSONResponse({"error": f"fail to delete doujinshi {did} from group {id}"}, status_code = 500)

@app.put("/group/{id}/{did}")
def add_doujinshi_to_group(id: str, did: str, token: str = Depends(oauth2)) -> dict:
    verify_token(token)
    try:
        if add_to_group(app_state["redis_client"], id, did):
            return {"msg": f"success to add doujinshi {did} to group {id}"}
        else:
            return JSONResponse({"error": f"group {id} or doujinshi {did} not exists"}, status_code = 404)
    except:
        return JSONResponse({"error": f"fail to add doujinshi {did} to group {id}"}, status_code = 500)

@app.get("/doujinshi") # 页码从0开始，倒序从-1开始
def get_doujinshis_by_page(page: int = 0, token: str = Depends(oauth2)) -> dict:
    verify_token(token)
    return {"msg": "success", "data": get_doujinshi_list(app_state["redis_client"], page,
                        app_state["settings"]["max_num_perpage"])}

@app.get("/doujinshi/random")
def get_random_doujinshis(num: int = 5, token: str = Depends(oauth2)) -> dict:
    verify_token(token)
    return {"msg": "success", "data": get_random_doujinshi_list(app_state["redis_client"], num)}

@app.get("/doujinshi/{id}/metadata")
def get_doujinshi_metadata(id: str, token: str = Depends(oauth2)) -> dict:
    verify_token(token)
    try:
        result = get_doujinshi_by_id(app_state["redis_client"], id)
        if result == {}:
            return JSONResponse({"error": f"doujinshi {id} not exists"}, status_code = 404)
        return {"msg": "success", "data": result}
    except:
        return JSONResponse({"error": f"fail to get doujinshi by id {id}"}, status_code = 500)

@app.put("/doujinshi/{id}/metadata")
def set_doujinshi_metadata(id: str, edit: EditMetaData, token: str = Depends(oauth2)) -> dict:
    verify_token(token)
    try:
        if set_metadata(app_state["redis_client"], id, edit):
            return {"msg": f"success to set metadata of doujinshi {id}"}
        else:
            return JSONResponse({"error": f"doujinshi {id} not exists"}, status_code = 404)
    except:
        return JSONResponse({"error": f"fail to set metadata of doujinshi {id}"}, status_code = 500)

@app.delete("/doujinshi/{id}/metadata")
def delete_doujinshi_metadata(id: str, token: str = Depends(oauth2)) -> dict:
    verify_token(token)
    try:
        if delete_metadata(app_state["redis_client"], id):
            return {"msg": f"success to delete metadata of doujinshi {id}"}
        else:
            return JSONResponse({"error": f"doujinshi {id} not exists"}, status_code = 404)
    except:
        return JSONResponse({"error": f"fail to delete metadata of doujinshi {id}"}, status_code = 500)

@app.get("/doujinshi/{id}/pages")
def get_doujinshi_pages(id: str, token: str = Depends(oauth2)) -> dict:
    verify_token(token)
    try:
        result = get_page_urls(app_state, id)
        if result == []:
            return JSONResponse({"error": f"doujinshi {id} not exists or source not enabled"}, status_code = 404)
        return {"msg": "success", "data": result}
    except:
        return JSONResponse({"error": f"fail to get pages of doujinshi {id}"}, status_code = 500)

@app.get("/doujinshi/{id}/pageinfo/{num}")
def get_doujinshi_pageinfo_by_number(id: str, num: int, token: str = Depends(oauth2)):
    verify_token(token)
    # 需逐页爬取且未设置页面代理时
    try:
        info = get_page_info(app_state, id, num)
        if info == -1:
            return JSONResponse({"error": f"doujinshi {id} not exists or source not enabled"}, status_code = 404)
        elif info == 0:
            return JSONResponse({"error": f"doujinshi {id} not contain the {num} page"}, 404)
        return {"msg": "success", "data": info}
    except:
        return JSONResponse({"error": f"fail to get pageinfo of doujinshi {id}"}, status_code = 500)

@app.get("/doujinshi/{id}/page/{num}")
def get_doujinshi_page_by_number(id: str, num: int, token: str = Depends(oauth2)):
    verify_token(token)
    client = app_state["redis_client"]
    doujinshi_source = client.hget(f"doujinshi:{id}", "source")
    if doujinshi_source == None:
        return JSONResponse({"error": f"doujinshi {id} does not exist or source not enabled"}, status_code = 404)
    if not client.sismember("cur_read", id):
        client.sadd("cur_read", id) # 先设置状态，防止其他请求创建线程
        threading.Thread(target = read_pages, args = (app_state, id)).start()
    # 文件已存在则无需后续操作
    file_path = f".data/cache/{id}/{num}.jpg"
    source_object = app_state["sources"][doujinshi_source]
    if hasattr(source_object, "img_processor") and callable(getattr(source_object, "img_processor")):
        file_path_ = file_path
        file_path = file_path.replace(".jpg", "_processed.jpg")
    else:
        file_path_ = None
    if os.path.exists(file_path): # 文件已存在，返回文件
        # 检查缓存期限
        if (os.path.getmtime(file_path) + app_state["settings"]["cache_expire"] * 86400) <= time.time():
            os.remove(file_path)
        else:
            if os.path.getsize(file_path) > 0:
                return FileResponse(file_path)
    if not file_path_ == None:
        tmp_path = file_path
        file_path = file_path_
        file_path_ = tmp_path
    client.lpush(f"{id}_pages", num)
    page_status = client.brpop(f"{id}_{num}", timeout = 90) # 等待90s
    if page_status == None:
        # 等待超时，尝试移除错误文件
        try:
            os.remove(file_path)
        except:
            pass
        return JSONResponse({"error": f"fail to get page {num} of doujinshi {id}"}, status_code = 500) # 超时
    if page_status[1] == "-1":
        return JSONResponse({"error": f"doujinshi {id} not contain the {num} page"}, 404) # 页码不存在
    elif page_status[1] == "0":
        return JSONResponse({"error": f"fail to get page {num} of doujinshi {id}"}, status_code = 500)
    if os.path.exists(file_path): # 返回文件
        if os.path.getsize(file_path) > 0:
            if not file_path_ == None:
                with open(file_path, "rb") as f:
                    img_bytes = source_object.img_processor(f.read())
                try:
                    os.remove(file_path)
                except:
                    pass
                with open(file_path_, "wb") as f:
                    f.write(img_bytes)
                return FileResponse(file_path_)
            return FileResponse(file_path)
    return JSONResponse({"error": f"fail to get page {num} of doujinshi {id}"}, status_code = 500)

@app.get("/doujinshi/{id}/thumbnail")
def get_thumbnail(id: str, token: str = Depends(oauth2)) -> FileResponse:
    verify_token(token)
    if id == "nothumb":
        return FileResponse("nothumb.png")
    thumb_path = f".data/thumb/{id}.jpg"
    if os.path.exists(thumb_path):
        return FileResponse(thumb_path)
    return FileResponse("nothumb.png")

@app.get("/search")
def search(query: str, page: int = 0, source_name: str = "", group: str = "", token: str = Depends(oauth2)) -> dict:
    verify_token(token)
    query_list = query.lower().split("$,")
    query_list = [item for item in query_list if item != ""]
    for i in range(len(query_list)):
        query_list[i] = query_list[i].strip(" ").strip("$")
    return {"msg": "success", "data": search_doujinshi(app_state["redis_client"], (query_list, group, source_name, page),
                                        app_state["settings"]["max_num_perpage"])}