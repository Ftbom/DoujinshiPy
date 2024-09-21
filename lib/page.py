import os
import uuid
import time
import json
import py7zr
import shutil
import rarfile
import zipfile
import logging
import requests
import remotezip
from sqlmodel import Session, select
from lib.database import Doujinshi, SourceType

def zip_filelist(zip_file, sort: bool) -> list:
    filelist = zip_file.namelist()
    if sort:
        filelist.sort()
    # 获取文件列表
    for file in zip_file.infolist():
        if file.is_dir():
            filelist.remove(file.filename)
    return filelist

def rar_filelist(rar_file, sort: bool) -> list:
    filelist = rar_file.namelist()
    if sort:
        filelist.sort()
    # 获取文件列表
    for file in rar_file.infolist():
        if file.is_dir():
            filelist.remove(file.filename)
    return filelist

def sevenzip_filelist(sevenzip_file: py7zr.SevenZipFile, sort: bool) -> list:
    filelist = sevenzip_file.namelist()
    if sort:
        filelist.sort()
    # 获取文件列表
    for file in sevenzip_file.files:
        if file.is_directory:
            filelist.remove(file.filename)
    return filelist

def sevenzip_pagecount(file_path: str) -> int:
    sevenzip_file = py7zr.SevenZipFile(file_path, "r")
    filelist = sevenzip_filelist(sevenzip_file, False)
    sevenzip_file.close()
    return len(filelist)

def zip_pagecount(file_path: str) -> int:
    zip_file = zipfile.ZipFile(file_path, "r")
    filelist = zip_filelist(zip_file, False)
    zip_file.close()
    return len(filelist)

def rar_pagecount(file_path: str) -> int:
    rar_file = rarfile.RarFile(file_path, "r")
    filelist = rar_filelist(rar_file, False)
    rar_file.close()
    return len(filelist)

def local_pagecount(file_path: str) -> int:
    name, ext = os.path.splitext(file_path)
    if ext in [".zip", ".ZIP"]:
        return zip_pagecount(file_path)
    elif ext in [".7z", ".7Z"]:
        return sevenzip_pagecount(file_path)
    elif ext in [".rar", ".RAR"]:
        return rar_pagecount(file_path)

def cloud_pagecount(download_info: dict) -> int:
    zip_file = remotezip.RemoteZip(download_info["url"], headers = download_info["headers"],
                            support_suffix_range = download_info["suffix_range"], proxies = download_info["proxy"])
    filelist = zip_filelist(zip_file, False)
    zip_file.close()
    return len(filelist)

def get_page_count(sources, session, doujinshi: Doujinshi) -> int:
    if not doujinshi.pagecount == None: # 数据库已储存，直接返回
        return doujinshi.pagecount
    if doujinshi.type == SourceType.web:
        raise RuntimeError(f"fail to get page count of doujinshi {str(doujinshi.id)}")
    # 数据库未储存，读取并储存
    try:
        file_identifier = sources[doujinshi.source].get_file(doujinshi.identifier)
        if doujinshi.type == SourceType.local:
            pagecount = local_pagecount(file_identifier)
        elif doujinshi.type == SourceType.cloud:
            pagecount = cloud_pagecount(file_identifier)
    except Exception as e:
        logging.error(f"fail to get pagecount of doujinshi {str(doujinshi.id)}, error message: {e}")
        return 0
    doujinshi.pagecount = pagecount
    session.add(doujinshi)
    session.commit()
    logging.info(f"save pagecount of doujinshi {str(doujinshi.id)} to database")
    return pagecount

def get_page_urls(app_state, id: str) -> list[str]:
    engine = app_state["database_engine"]
    with Session(engine) as session:
        try:
            uid = uuid.UUID(id)
        except:
            return []
        result = session.exec(select(Doujinshi).where(Doujinshi.id == uid)).first()
        if result == None:
            return []
        if not result.source in app_state["sources"]:
            return []
        if (result.type == SourceType.web) and (not app_state["settings"]["proxy_webpage"]):
            pages_result = app_state["sources"][result.source].get_pages(result.identifier) # 若未设置代理图片，获取网页源图片
            if (pages_result != []) and (pages_result != {}):
                return pages_result
        pagecount = get_page_count(app_state["sources"], session, result) # 获取页面数目
        page_list = []
        for i in range(pagecount):
            if (result.type == SourceType.web) and (not app_state["settings"]["proxy_webpage"]):
                page_list.append(f"/doujinshi/{str(result.id)}/pageinfo/{i}")
            else:
                page_list.append(f"/doujinshi/{str(result.id)}/page/{i}")
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
    except Exception as e:
        try:
            os.remove(page_path)
        except:
            pass
        client.set(f"{id}_{num}", 0)
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
    count = 0
    while count < 3000:
        time.sleep(0.1)
        count = count + 1
        num_status = client.get(f"{id}_page")
        if num_status == None:
            continue
        try:
            with client.lock(f"{id}_page_lock", blocking = True, blocking_timeout = 10):
                num = int(num_status)
                client.delete(f"{id}_page")
                if num >= pagecount or num < 0:
                    client.set(f"{id}_{num}", -1)
                    continue
                if single_page:
                    if not num in page_urls:
                        page_urls.update(sources[doujinshi.source].get_page_urls(doujinshi.identifier, num))
                    img_url = sources[doujinshi.source].get_img_url(page_urls[num])
                    # threading.Thread(target = cache_page, args = (client, SourceType.web, id,
                    #                     num, img_url, app_state["settings"]["proxy"], True)).start()
                    cache_page(client, SourceType.web, id, num, img_url, app_state["settings"]["proxy"], True)
                else:
                    # threading.Thread(target = cache_page, args = (client, SourceType.web, id,
                    #                     num, page_urls, app_state["settings"]["proxy"])).start()
                    # 若使用多线程同时缓存不同页面，极易造成远程服务器限制或远程zip解压失败
                    # 不使用则速度较慢
                    cache_page(client, SourceType.web, id, num, page_urls, app_state["settings"]["proxy"])
                time.sleep(sources[doujinshi.source].SLEEP)
                count = 0
        except:
            client.set(f"{id}_{num}", 0)
            pass

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
    filelist = zip_filelist(zip_file, True)
    pagecount = len(filelist)
    id = str(doujinshi.id)
    count = 0
    while count < 3000:
        time.sleep(0.1)
        count = count + 1
        num_status = client.get(f"{id}_page")
        if num_status == None:
            continue
        try:
            with client.lock(f"{id}_page_lock", blocking = True, blocking_timeout = 10):
                num = int(num_status)
                client.delete(f"{id}_page")
                if num >= pagecount or num < 0:
                    client.set(f"{id}_{num}", -1)
                    continue
                # threading.Thread(target = cache_page, args = (client, SourceType.cloud, id,
                #                     num, zip_file, filelist)).start()
                cache_page(client, SourceType.cloud, id, num, zip_file, filelist)
                time.sleep(sources[doujinshi.source].SLEEP)
                count = 0
        except:
            client.set(f"{id}_{num}", 0)
            pass
    zip_file.close()

def zip_page_read(file_path: str, client, id) -> None:
    zip_file = zipfile.ZipFile(file_path, "r")
    filelist = zip_filelist(zip_file, True)
    pagecount = len(filelist)
    count = 0
    while count < 3000:
        time.sleep(0.1)
        count = count + 1
        num_status = client.get(f"{id}_page")
        if num_status == None:
            continue
        try:
            with client.lock(f"{id}_page_lock", blocking = True, blocking_timeout = 10):
                num = int(num_status)
                client.delete(f"{id}_page")
                if num >= pagecount or num < 0:
                    client.set(f"{id}_{num}", -1)
                    continue
                # threading.Thread(target = cache_page, args = (client, SourceType.local, id,
                #                     num, zip_file, filelist)).start()
                cache_page(client, SourceType.local, id, num, zip_file, filelist)
                count = 0
        except:
            client.set(f"{id}_{num}", 0)
            pass
    zip_file.close()

def rar_page_read(file_path: str, client, id) -> None:
    rar_file = rarfile.RarFile(file_path, "r")
    filelist = rar_filelist(rar_file, True)
    pagecount = len(filelist)
    count = 0
    while count < 3000:
        time.sleep(0.1)
        count = count + 1
        num_status = client.get(f"{id}_page")
        if num_status == None:
            continue
        try:
            with client.lock(f"{id}_page_lock", blocking = True, blocking_timeout = 10):
                num = int(num_status)
                client.delete(f"{id}_page")
                if num >= pagecount or num < 0:
                    client.set(f"{id}_{num}", -1)
                    continue
                # threading.Thread(target = cache_page, args = (client, SourceType.local, id,
                #                     num, rar_file, filelist)).start()
                cache_page(client, SourceType.local, id, num, rar_file, filelist)
                count = 0
        except:
            client.set(f"{id}_{num}", 0)
            pass
    rar_file.close()

def sevenzip_page_read(file_path: str, client, id) -> None:
    sevenzip_file = py7zr.SevenZipFile(file_path, "r")
    filelist = sevenzip_filelist(sevenzip_file, True)
    pagecount = len(filelist)
    count = 0
    while count < 3000: # 无请求后等待5min自动退出
        time.sleep(0.1)
        count = count + 1
        # 获取页加载状态，若有信息，读取并加载对应页
        num_status = client.get(f"{id}_page")
        if num_status == None:
            continue
        try:
            with client.lock(f"{id}_page_lock", blocking = True, blocking_timeout = 10):
                # 加锁，防止此时页加载状态被设置，导致信息丢失
                num = int(num_status)
                client.delete(f"{id}_page") # 重置状态
                if num >= pagecount or num < 0:
                    client.set(f"{id}_{num}", -1) # 页码状态
                    continue
                # 开启页码缓存线程
                # threading.Thread(target = cache_page, args = (client, SourceType.local, id,
                #                         num, sevenzip_file, filelist, True)).start()
                cache_page(client, SourceType.local, id, num, sevenzip_file, filelist, True)
                count = 0
        except:
            client.set(f"{id}_{num}", 0)
            pass
    sevenzip_file.close() # 关闭文件

def local_page_read(app_state, doujinshi: Doujinshi) -> None:
    sources = app_state["sources"]
    client = app_state["redis_client"]
    try:
        file_path = sources[doujinshi.source].get_file(doujinshi.identifier)
        name, ext = os.path.splitext(file_path)
        # 根据文件类型，分配缓存函数
        if ext in [".zip", ".ZIP"]:
            zip_page_read(file_path, client, str(doujinshi.id))
        elif ext in [".7z", ".7Z"]:
            sevenzip_page_read(file_path, client, str(doujinshi.id))
        elif ext in [".rar", ".RAR"]:
            rar_page_read(file_path, client, str(doujinshi.id))
    except Exception as e:
        logging.error(f"fail to read doujinshi {str(doujinshi.id)}, error message: {e}")

def read_pages(app_state, id: str) -> None:
    client = app_state["redis_client"]
    engine = app_state["database_engine"]
    sources = app_state["sources"]
    with Session(engine) as session:
        try:
            uid = uuid.UUID(id)
        except:
            # 设置缓存状态，id不存在
            client.set(f"{id}_read", -1)
            return
        result = session.exec(select(Doujinshi).where(Doujinshi.id == uid)).first()
        if result == None:
            client.set(f"{id}_read", -1)
            return
        if not result.source in sources:
            client.set(f"{id}_read", -1)
            return
        client.set(f"{id}_read", 1)
        # 开始缓存页面
        if result.type == SourceType.web:
            web_page_read(app_state, result)
        elif result.type == SourceType.cloud:
            cloud_page_read(app_state, result)
        elif result.type == SourceType.local:
            local_page_read(app_state, result)
        client.delete(f"{id}_read") # 缓存结束，重置缓存状态

def get_page_info(app_state, id: str, num: int) -> dict:
    client = app_state["redis_client"]
    engine = app_state["database_engine"]
    sources = app_state["sources"]
    with Session(engine) as session:
        try:
            uid = uuid.UUID(id)
        except:
            # id不存在
            return -1
        result = session.exec(select(Doujinshi).where(Doujinshi.id == uid)).first()
        if result == None:
            # id不存在
            return -1
        if not result.source in sources:
            # 源未启用
            return -1
        with client.lock(f"{str(uid)}_pages_lock", blocking = True, blocking_timeout = 10):
            pages = client.get(f"{str(uid)}_pages")
            if pages == None:
                pages = sources[result.source].get_page_urls(result.identifier, num)
                client.setex(f"{str(uid)}_pages", 100, json.dumps(pages))
            else:
                pages_dict = json.loads(pages)
                pages = {}
                for i in pages_dict.keys():
                    pages[int(i)] = pages_dict[i]
                if not num in pages:
                    pages.update(sources[result.source].get_page_urls(result.identifier, num))
                    client.setex(f"{str(uid)}_pages", 100, json.dumps(pages))
    if not num in pages:
        return 0
    return sources[result.source].get_img_url(pages[num])
        