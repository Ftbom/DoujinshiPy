import io
import os
import time
import py7zr
import zipfile
import rarfile
import remotezip
from PIL import Image
from lib.utils import Doujinshi, SourceType

def generate_thumbnail(file_bytes: bytes) -> bytes:
    image = Image.open(io.BytesIO(file_bytes))
    x, y = image.size
    i = 400 / y
    image.thumbnail((x * i, y * i)) # count size
    img_bytes = io.BytesIO()
    try:
        image.save(img_bytes, format = "JPEG")
    except:
        image.convert('RGB').save(img_bytes, format = "JPEG")
    return img_bytes.getvalue()

def sevenzip_thumbnail(file_path: str) -> bytes:
    sevenzip_file = py7zr.SevenZipFile(file_path, "r")
    filelist = sevenzip_file.namelist()
    filelist.sort()
    # get file list
    for file in sevenzip_file.files:
        if file.is_directory:
            filelist.remove(file.filename)
    image_bytes = sevenzip_file.read([filelist[0]])[filelist[0]]
    ibytes = generate_thumbnail(image_bytes.read())
    image_bytes.close()
    sevenzip_file.close()
    return ibytes

def zip_thumbnail(file_path: str) -> bytes:
    zip_file = zipfile.ZipFile(file_path, "r")
    filelist = zip_file.namelist()
    filelist.sort()
    # get file list
    for file in zip_file.infolist():
        if file.is_dir():
            filelist.remove(file.filename)
    with zip_file.open(filelist[0]) as image_bytes:
        ibytes = generate_thumbnail(image_bytes.read())
    zip_file.close()
    return ibytes

def rar_thumbnail(file_path: str) -> bytes:
    rar_file = rarfile.RarFile(file_path, "r")
    filelist = rar_file.namelist()
    filelist.sort()
    # get file list
    for file in rar_file.infolist():
        if file.is_dir():
            filelist.remove(file.filename)
    with rar_file.open(filelist[0]) as image_bytes:
        ibytes = generate_thumbnail(image_bytes.read())
    rar_file.close()
    return ibytes

def local_thumbnail(file_path: str) -> bytes:
    name, ext = os.path.splitext(file_path)
    if ext in [".zip", ".ZIP"]:
        return zip_thumbnail(file_path)
    elif ext in [".7z", ".7Z"]:
        return sevenzip_thumbnail(file_path)
    elif ext in [".rar", ".RAR"]:
        return rar_thumbnail(file_path)

def cloud_thumbnail(download_info: dict, sleep_time: float) -> bytes:
    zip_file = remotezip.RemoteZip(download_info["url"], headers = download_info["headers"],
                            support_suffix_range = download_info["suffix_range"], proxies = download_info["proxy"])
    filelist = zip_file.namelist()
    filelist.sort()
    for file in zip_file.infolist():
        if file.is_dir():
            filelist.remove(file.filename)
    with zip_file.open(filelist[0]) as image_bytes:
        ibytes = generate_thumbnail(image_bytes.read())
    zip_file.close()
    time.sleep(sleep_time)
    time.sleep(1)
    return ibytes

def get_cover(app_state, doujinshi: Doujinshi, url) -> bytes:
    if doujinshi.type == SourceType.web:
        raise RuntimeError("this source not support generate thumbnail")
    # get file identifier
    source = app_state["sources"][doujinshi.source]
    file_identifier = source.get_file(doujinshi.identifier)
    if doujinshi.type == SourceType.local:
        return local_thumbnail(file_identifier)
    elif doujinshi.type == SourceType.cloud:
        return cloud_thumbnail(file_identifier, source.SLEEP)
    elif doujinshi.type == SourceType.cloud_encrypted:
        file_identifier["url"] = f'http://{app_state["settings"]["host"]}:{app_state["settings"]["port"]}/decrypt/{doujinshi.source}?id={file_identifier["url"].replace("decrypt_", "")}'
        file_identifier["headers"] = {"Authorization": "Bearer " + app_state["settings"]["passwd"]}
        return cloud_thumbnail(file_identifier, source.SLEEP)
