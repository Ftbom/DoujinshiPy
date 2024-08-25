import io
import os
import time
import py7zr
import zipfile
import rarfile
import remotezip
from PIL import Image
from lib.database import Doujinshi, SourceType

def generate_thumbnail(file_bytes: io.BytesIO, thumb_path: str) -> bytes:
    image = Image.open(file_bytes)
    x, y = image.size
    i = 400 / y
    image.thumbnail((x * i, y * i)) # count size
    try:
        image.save(thumb_path)
    except:
        image.convert('RGB').save(thumb_path)

def sevenzip_thumbnail(file_path: str, id: str) -> None:
    sevenzip_file = py7zr.SevenZipFile(file_path, "r")
    filelist = sevenzip_file.namelist()
    filelist.sort()
    # get file list
    for file in sevenzip_file.files:
        if file.is_directory:
            filelist.remove(file.filename)
    image_bytes = sevenzip_file.read([filelist[0]])[filelist[0]]
    generate_thumbnail(image_bytes, f".data/thumb/{id}.jpg")
    image_bytes.close()
    sevenzip_file.close()

def zip_thumbnail(file_path: str, id: str) -> None:
    zip_file = zipfile.ZipFile(file_path, "r")
    filelist = zip_file.namelist()
    filelist.sort()
    # get file list
    for file in zip_file.infolist():
        if file.is_dir():
            filelist.remove(file.filename)
    with zip_file.open(filelist[0]) as image_bytes:
        generate_thumbnail(image_bytes, f".data/thumb/{id}.jpg")
    zip_file.close()

def rar_thumbnail(file_path: str, id: str) -> None:
    rar_file = rarfile.RarFile(file_path, "r")
    filelist = rar_file.namelist()
    filelist.sort()
    # get file list
    for file in rar_file.infolist():
        if file.is_dir():
            filelist.remove(file.filename)
    with rar_file.open(filelist[0]) as image_bytes:
        generate_thumbnail(image_bytes, f".data/thumb/{id}.jpg")
    rar_file.close()

def local_thumbnail(file_path: str, id: str) -> None:
    name, ext = os.path.splitext(file_path)
    if ext in [".zip", ".ZIP"]:
        zip_thumbnail(file_path, id)
    elif ext in [".7z", ".7Z"]:
        sevenzip_thumbnail(file_path, id)
    elif ext in [".rar", ".RAR"]:
        rar_thumbnail(file_path, id)

def cloud_thumbnail(download_info: dict, id: str) -> None:
    zip_file = remotezip.RemoteZip(download_info["url"], headers = download_info["headers"],
                            support_suffix_range = download_info["suffix_range"], proxies = download_info["proxy"])
    filelist = zip_file.namelist()
    filelist.sort()
    for file in zip_file.infolist():
        if file.is_dir():
            filelist.remove(file.filename)
    with zip_file.open(filelist[0]) as image_bytes:
        generate_thumbnail(image_bytes, f".data/thumb/{id}.jpg")
    zip_file.close()
    time.sleep(0.5)

def get_cover(app_state, doujinshi: Doujinshi) -> None:
    if doujinshi.type == SourceType.web:
        raise RuntimeError("this source not support generate thumbnail")
    sources = app_state["sources"]
    if not doujinshi.source in sources:
        raise RuntimeError("incorrect source name")
    # get file identifier
    file_identifier = sources[doujinshi.source].get_file(doujinshi.identifier)
    if doujinshi.type == SourceType.local:
        local_thumbnail(file_identifier, doujinshi.id)
    elif doujinshi.type == SourceType.cloud:
        cloud_thumbnail(file_identifier, doujinshi.id)