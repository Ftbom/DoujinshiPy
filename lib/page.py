import os
import time
import json
import py7zr
import shutil
import rarfile
import zipfile
import logging
import requests
import remotezip
from lib.utils import Doujinshi, SourceType, doujinshi_from_json, set_pagecount_of_doujinshi

def archive_filelist(archive_file, sort: bool, file_type: str) -> list:
    filelist = archive_file.namelist()
    if sort:
        filelist.sort()
    # 获取文件列表
    if file_type == "zip" or file_type == "rar":
        for file in archive_file.infolist():
            if file.is_dir():
                filelist.remove(file.filename)
    elif file_type == "7z":
        for file in archive_file.files:
            if file.is_directory:
                filelist.remove(file.filename)
    return filelist

def local_pagecount(file_path: str) -> int:
    name, ext = os.path.splitext(file_path)
    if ext in [".zip", ".ZIP"]:
        archive_file = zipfile.ZipFile(file_path, "r")
        file_type = "zip"
    elif ext in [".7z", ".7Z"]:
        archive_file = py7zr.SevenZipFile(file_path, "r")
        file_type = "7z"
    elif ext in [".rar", ".RAR"]:
        archive_file = rarfile.RarFile(file_path, "r")
        file_type = "rar"
    filelist = archive_filelist(archive_file, False, file_type)
    archive_file.close()
    return len(filelist)

def cloud_pagecount(download_info: dict) -> int:
    zip_file = remotezip.RemoteZip(download_info["url"], headers = download_info["headers"],
                            support_suffix_range = download_info["suffix_range"], proxies = download_info["proxy"])
    filelist = archive_filelist(zip_file, False, "zip")
    zip_file.close()
    return len(filelist)

def get_page_count(app_state, doujinshi: dict, id: str) -> int:
    if doujinshi["type"] == "web":
        raise RuntimeError(f"fail to get page count of doujinshi {id}")
    sources = app_state["sources"]
    client = app_state["redis_client"]
    # 数据库未储存，读取并储存
    try:
        file_identifier = sources[doujinshi["source"]].get_file(doujinshi["identifier"])
        if doujinshi["type"] == "local":
            pagecount = local_pagecount(file_identifier)
        elif doujinshi["type"] == "cloud":
            pagecount = cloud_pagecount(file_identifier)
    except Exception as e:
        logging.error(f"fail to get pagecount of doujinshi {id}, error message: {e}")
        return 0
    set_pagecount_of_doujinshi(client, id, pagecount)
    logging.info(f"save pagecount of doujinshi {id} to database")
    return pagecount

def get_page_urls(app_state, id: str) -> list[str]:
    client = app_state["redis_client"]
    result = client.hgetall(f"doujinshi:{id}")
    if result == {}:
        return []
    if (result["type"] == "web") and (not app_state["settings"]["proxy_webpage"]):
        pages_result = app_state["sources"][result["source"]].get_pages(result["identifier"]) # 若未设置代理图片，获取网页源图片
        if (pages_result != []) and (pages_result != {}):
            return pages_result
    if result["pagecount"] == "-1":
        pagecount = get_page_count(app_state, result, id) # 获取页面数目
    else:
        pagecount = int(result["pagecount"])
    page_list = []
    for i in range(pagecount):
        if (result["type"] == "web") and (not app_state["settings"]["proxy_webpage"]):
            page_list.append(f"/doujinshi/{id}/pageinfo/{i}")
        else:
            page_list.append(f"/doujinshi/{id}/page/{i}")
    return page_list

def cache_page(client, type, id, num, arg1, arg2, arg3 = None): # 缓存页码
    page_path = f".data/cache/{id}/{num}.jpg"
    if os.path.exists(page_path):
        return
    try:
        # 创建空文件占位，防止同时缓存相同页面
        os.makedirs(f".data/cache/{id}", exist_ok = True)
        with open(page_path, "wb") as f:
            f.write(b"")
        if type == SourceType.web:
            if not arg3:
                page_bytes = requests.get(arg1["urls"][num], proxies = arg2, headers = arg1["headers"]).content # 获取链接内容
            else:
                page_bytes = requests.get(arg1["url"], proxies = arg2, headers = arg1["headers"]).content # 获取链接内容
        elif type == SourceType.cloud:
            page_io = arg1.open(arg2[num]) # 读取远程zip
            page_bytes = page_io.read()
            page_io.close()
        elif type == SourceType.local:
            if not arg3:
                page_io = arg1.open(arg2[num]) # 读取zip或rar
            else:
                page_io = arg1.read([arg2[num]])[arg2[num]] # 读取7z
                arg1.reset()
            page_bytes = page_io.read()
            page_io.close()
        # 更新缓存大小，过大则清空缓存
        with client.lock(f"cache_lock", blocking = True, blocking_timeout = 10):
            cache_size = int(client.get("cache_size"))
            cache_size_limit = int(client.get("cache_size_limit"))
            if cache_size >= cache_size_limit:
                try:
                    shutil.rmtree(".data/cache")
                except:
                    pass
                os.makedirs(".data/cache", exist_ok = True)
                cache_size = 0
            cache_size = cache_size + len(page_bytes)
            client.set("cache_size", cache_size)
        os.makedirs(f".data/cache/{id}", exist_ok = True)
        with open(page_path, "wb") as f:
            f.write(page_bytes)
        client.lpush(f"{id}_{num}", 1)
        client.expire(f"{id}_{num}", 10)
    except Exception as e:
        try:
            os.remove(page_path)
        except:
            pass
        client.lpush(f"{id}_{num}", 0)
        client.expire(f"{id}_{num}", 30)
        logging.error(f"fail to get page {num} of doujinshi {id}, error message: {e}")

def web_page_read(app_state, doujinshi: Doujinshi) -> None:
    sources = app_state["sources"]
    client = app_state["redis_client"]
    try:
        page_urls = sources[doujinshi.source].get_pages(doujinshi.identifier)
    except Exception as e:
        logging.error(f"fail to read doujinshi {str(doujinshi.id)}, error message: {e}")
        return
    single_page = False
    if page_urls == {} or page_urls == []:
        page_urls = {}
        pagecount = doujinshi.pagecount
        single_page = True
    else:
        pagecount = len(page_urls["urls"])
    id = str(doujinshi.id)
    while True:
        num_status = client.brpop(f"{id}_pages", timeout = 900)
        if num_status == None:
            client.srem("cur_read", id)
            break
        try:
            num = int(num_status[1])
            if num >= pagecount or num < 0:
                client.lpush(f"{id}_{num}", -1) # 页码状态
                client.expire(f"{id}_{num}", 900)
                continue
            if single_page:
                if not num in page_urls:
                    page_urls.update(sources[doujinshi.source].get_page_urls(doujinshi.identifier, num))
                img_url = sources[doujinshi.source].get_img_url(page_urls[num])
                cache_page(client, SourceType.web, id, num, img_url, app_state["settings"]["proxy"], True)
            else:
                cache_page(client, SourceType.web, id, num, page_urls, app_state["settings"]["proxy"])
            time.sleep(sources[doujinshi.source].SLEEP)
        except:
            client.lpush(f"{id}_{num}", 0)
            client.expire(f"{id}_{num}", 30)

def archive_cache_page(client, type: SourceType, id: str, pagecount: int, sleep_time: int, arg1, arg2, arg3 = None):
    while True:
        num_status = client.brpop(f"{id}_pages", timeout = 900)
        if num_status == None:
            client.srem("cur_read", id)
            break
        try:
            num = int(num_status[1])
            if num >= pagecount or num < 0:
                client.lpush(f"{id}_{num}", -1) # 页码状态
                client.expire(f"{id}_{num}", 900)
                continue
            cache_page(client, type, id, num, arg1, arg2, arg3)
            time.sleep(sleep_time)
        except:
            client.lpush(f"{id}_{num}", 0)
            client.expire(f"{id}_{num}", 30)

def cloud_page_read(app_state, doujinshi: Doujinshi) -> None:
    sources = app_state["sources"]
    client = app_state["redis_client"]
    try:
        download_info = sources[doujinshi.source].get_file(doujinshi.identifier)
        zip_file = remotezip.RemoteZip(download_info["url"], headers = download_info["headers"],
                            support_suffix_range = download_info["suffix_range"], proxies = download_info["proxy"])
    except Exception as e:
        logging.error(f"fail to read doujinshi {str(doujinshi.id)}, error message: {e}")
        return
    filelist = archive_filelist(zip_file, True, "zip")
    archive_cache_page(client, SourceType.cloud, str(doujinshi.id), len(filelist), 
                            sources[doujinshi.source].SLEEP, zip_file, filelist)
    zip_file.close()

def local_page_read(app_state, doujinshi: Doujinshi) -> None:
    sources = app_state["sources"]
    client = app_state["redis_client"]
    try:
        file_path = sources[doujinshi.source].get_file(doujinshi.identifier)
        name, ext = os.path.splitext(file_path)
        # 根据文件类型，分配缓存函数
        if ext in [".zip", ".ZIP"]:
            archive_file = zipfile.ZipFile(file_path, "r")
            file_type = "zip"
            arg = None
        elif ext in [".7z", ".7Z"]:
            archive_file = py7zr.SevenZipFile(file_path, "r")
            file_type = "7z"
            arg = True
        elif ext in [".rar", ".RAR"]:
            archive_file = rarfile.RarFile(file_path, "r")
            file_type = "rar"
            arg = None
        filelist = archive_filelist(archive_file, True, file_type)
        archive_cache_page(client, SourceType.local, str(doujinshi.id), len(filelist), 
                            0, archive_file, filelist, arg)
        archive_file.close()
    except Exception as e:
        logging.error(f"fail to read doujinshi {str(doujinshi.id)}, error message: {e}")

def read_pages(app_state, id: str) -> None:
    client = app_state["redis_client"]
    result = doujinshi_from_json(id, client.hgetall(f"doujinshi:{id}"))
    # 开始缓存页面
    if result.type == SourceType.web:
        web_page_read(app_state, result)
    elif result.type == SourceType.cloud:
        cloud_page_read(app_state, result)
    elif result.type == SourceType.local:
        local_page_read(app_state, result)

def get_page_info(app_state, id: str, num: int) -> dict:
    client = app_state["redis_client"]
    result = client.hgetall(f"doujinshi:{id}")
    if result == {}:
        return -1
    sources = app_state["sources"]
    with client.lock(f"{id}_pages_lock", blocking = True, blocking_timeout = 10):
        pages = client.get(f"{id}_pages")
        if pages == None:
            pages = sources[result["source"]].get_page_urls(result["identifier"], num)
            client.setex(f"{id}_pages", 900, json.dumps(pages))
        else:
            pages_dict = json.loads(pages)
            pages = {}
            for i in pages_dict.keys():
                pages[int(i)] = pages_dict[i]
            if not num in pages:
                pages.update(sources[result["source"]].get_page_urls(result["identifier"], num))
                client.setex(f"{id}_pages", 900, json.dumps(pages))
    if not num in pages:
        return 0
    return sources[result["source"]].get_img_url(pages[num])
        