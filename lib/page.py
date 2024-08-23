import os
import uuid
import time
import py7zr
import rarfile
import zipfile
import logging
import requests
import threading
import remotezip
from sqlmodel import Session, select
from lib.database import Doujinshi, SourceType

def zip_filelist(zip_file, sort: bool) -> list:
    filelist = zip_file.namelist()
    if sort:
        filelist.sort()
    # get file list
    for file in zip_file.infolist():
        if file.is_dir():
            filelist.remove(file.filename)
    return filelist

def rar_filelist(rar_file, sort: bool) -> list:
    filelist = rar_file.namelist()
    if sort:
        filelist.sort()
    # get file list
    for file in rar_file.infolist():
        if file.is_dir():
            filelist.remove(file.filename)
    return filelist

def sevenzip_filelist(sevenzip_file: py7zr.SevenZipFile, sort: bool) -> list:
    filelist = sevenzip_file.namelist()
    if sort:
        filelist.sort()
    # get file list
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
    if not doujinshi.pagecount == None:
        return doujinshi.pagecount
    if doujinshi.type == SourceType.web:
        raise RuntimeError(f"fail to get page count of doujinshi {str(doujinshi.id)}")
    # pagecount is none, get pagecount and save it
    file_identifier = sources[doujinshi.source].get_file(doujinshi.identifier)
    if doujinshi.type == SourceType.local:
        pagecount = local_pagecount(file_identifier)
    elif doujinshi.type == SourceType.cloud:
        pagecount = cloud_pagecount(file_identifier)
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
            return app_state["sources"][result.source].get_pages(result.identifier, app_state["settings"]["proxy"]) # get web url of pages
        pagecount = get_page_count(app_state["sources"], session, result)
        page_list = []
        for i in range(pagecount):
            page_list.append(f"/doujinshi/{str(result.id)}/page/{i}")
        return page_list

def cache_page(client, type, id, num, arg1, arg2, is_7z = False):
    page_path = f".data/cache/{id}/{num}.jpg"
    if os.path.exists(page_path):
        return
    try:
        if type == SourceType.web:
            page_bytes = requests.get(arg1["urls"][num], proxies = arg2, headers = arg1["headers"]).content # get url content
        elif type == SourceType.cloud:
            page_io = arg1.open(arg2[num]) # get remote zip file
            page_bytes = page_io.read()
            page_io.close()
        elif type == SourceType.local:
            if not is_7z:
                page_io = arg1.open(arg2[num]) # get zip file
            else:
                page_io = arg1.read([arg2[num]])[arg2[num]] # get 7z file
            page_bytes = page_io.read()
            page_io.close()
        os.makedirs(f".data/cache/{id}", exist_ok = True)
        with open(page_path, "wb") as f:
            f.write(page_bytes)
    except:
        client.set(f"{id}_{num}", 0)
        logging.error(f"fail to get page{num} of doujinshi {id}")

def web_page_read(app_state, doujinshi: Doujinshi) -> None:
    sources = app_state["sources"]
    client = app_state["memcached_client"]
    page_urls = sources[doujinshi.source].get_pages(doujinshi.identifier, app_state["settings"]["proxy"])
    pagecount = len(page_urls["urls"])
    id = str(doujinshi.id)
    count = 0
    while count < 3000:
        count = count + 1
        try:
            num = client.get(f"{id}_page")
        except:
            # in case of get value while setting
            time.sleep(0.1)
            num = client.get(f"{id}_page")
        if num != None:
            if num >= pagecount or num < 0:
                client.set(f"{id}_{num}", -1)
                client.delete(f"{id}_page")
                continue
            # use new thread to cache page
            threading.Thread(target = cache_page, args = (client, SourceType.web, id,
                                    num, page_urls, app_state["settings"]["proxy"])).start()
            client.delete(f"{id}_page")
            count = 0
        time.sleep(0.1)

def cloud_page_read(app_state, doujinshi: Doujinshi) -> None:
    sources = app_state["sources"]
    client = app_state["memcached_client"]
    download_info = sources[doujinshi.source].get_file(doujinshi.identifier)
    zip_file = remotezip.RemoteZip(download_info["url"], headers = download_info["headers"],
                            support_suffix_range = download_info["suffix_range"], proxies = download_info["proxy"])
    filelist = zip_filelist(zip_file, True)
    pagecount = len(filelist)
    id = str(doujinshi.id)
    count = 0
    while count < 3000:
        count = count + 1
        try:
            num = client.get(f"{id}_page")
        except:
            time.sleep(0.1)
            num = client.get(f"{id}_page")
        if num != None:
            if num >= pagecount or num < 0:
                client.set(f"{id}_{num}", -1)
                client.delete(f"{id}_page")
                continue
            threading.Thread(target = cache_page, args = (client, SourceType.cloud, id,
                                    num, zip_file, filelist)).start()
            client.delete(f"{id}_page")
            count = 0
        time.sleep(0.1)
    zip_file.close()

def zip_page_read(file_path: str, client, id) -> None:
    zip_file = zipfile.ZipFile(file_path, "r")
    filelist = zip_filelist(zip_file, True)
    pagecount = len(filelist)
    count = 0
    while count < 3000:
        count = count + 1
        try:
            num = client.get(f"{id}_page")
        except:
            time.sleep(0.1)
            num = client.get(f"{id}_page")
        if num != None:
            if num >= pagecount or num < 0:
                client.set(f"{id}_{num}", -1)
                client.delete(f"{id}_page")
                continue
            threading.Thread(target = cache_page, args = (client, SourceType.local, id,
                                    num, zip_file, filelist)).start()
            client.delete(f"{id}_page")
            count = 0
        time.sleep(0.1)
    zip_file.close()

def rar_page_read(file_path: str, client, id) -> None:
    rar_file = rarfile.RarFile(file_path, "r")
    filelist = rar_filelist(rar_file, True)
    pagecount = len(filelist)
    count = 0
    while count < 300:
        count = count + 1
        try:
            num = client.get(f"{id}_page")
        except:
            time.sleep(0.1)
            num = client.get(f"{id}_page")
        if num != None:
            if num >= pagecount or num < 0:
                client.set(f"{id}_{num}", -1)
                client.delete(f"{id}_page")
                continue
            threading.Thread(target = cache_page, args = (client, SourceType.local, id,
                                    num, rar_file, filelist)).start()
            client.delete(f"{id}_page")
            count = 0
        time.sleep(0.1)
    rar_file.close()

def sevenzip_page_read(file_path: str, client, id) -> None:
    sevenzip_file = py7zr.SevenZipFile(file_path, "r")
    filelist = sevenzip_filelist(sevenzip_file, True)
    pagecount = len(filelist)
    count = 0
    while count < 3000:
        count = count + 1
        try:
            num = client.get(f"{id}_page")
        except:
            time.sleep(0.1)
            num = client.get(f"{id}_page")
        if num != None:
            if num >= pagecount or num < 0:
                client.set(f"{id}_{num}", -1)
                client.delete(f"{id}_page")
                continue
            threading.Thread(target = cache_page, args = (client, SourceType.local, id,
                                    num, sevenzip_file, filelist, True)).start()
            client.delete(f"{id}_page")
            count = 0
        time.sleep(0.1)
    sevenzip_file.close()

def local_page_read(app_state, doujinshi: Doujinshi) -> None:
    sources = app_state["sources"]
    client = app_state["memcached_client"]
    file_path = sources[doujinshi.source].get_file(doujinshi.identifier)
    name, ext = os.path.splitext(file_path)
    if ext in [".zip", ".ZIP"]:
        zip_page_read(file_path, client, str(doujinshi.id))
    elif ext in [".7z", ".7Z"]:
        sevenzip_page_read(file_path, client, str(doujinshi.id))
    elif ext in [".rar", ".RAR"]:
        rar_page_read(file_path, client, str(doujinshi.id))

def read_pages(app_state, id: str) -> None:
    client = app_state["memcached_client"]
    engine = app_state["database_engine"]
    sources = app_state["sources"]
    with Session(engine) as session:
        try:
            uid = uuid.UUID(id)
        except:
            # set error status and exit
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
        # start read page
        if result.type == SourceType.web:
            web_page_read(app_state, result)
        elif result.type == SourceType.cloud:
            cloud_page_read(app_state, result)
        elif result.type == SourceType.local:
            local_page_read(app_state, result)
        client.delete(f"{id}_read")