import json
import redis
import base64
import requests
import importlib
from lib.utils import SourceType
from rclone import Crypt
from rclone.util import (BLOCKDATA_SIZE, BLOCKHEADER_SIZE, FILEMAGIC_SIZE, FILENONCE_SIZE,
                         count_block_num, count_pos, count_size)

BLOCK_SIZE = BLOCKDATA_SIZE + BLOCKHEADER_SIZE # 数据块大小
BLOCK_CHUNK_NUM = 32 # 单次读取的数据块的数目

class Source:
    TYPE = SourceType.cloud_encrypted
    SLEEP = 0.1

    def __init__(self, config) -> None:
        name_encoding = "base32"
        if "name_encoding" in config:
            name_encoding = config["name_encoding"]
        passwd_obscured = True
        if "passwd_obscured" in config:
            passwd_obscured = config["passwd_obscured"]
        self.__rclone = Crypt(config["passwd"], config["passwd2"], name_encoding = name_encoding,
                              passwd_obscured = passwd_obscured) if config["passwd2"] else Crypt(config["passwd"], name_encoding = name_encoding,
                                                                                                 passwd_obscured = passwd_obscured)
        self.__name_obfuscate = False
        if "name_obfuscate" in config:
            self.__name_obfuscate = config["name_obfuscate"]
        self.__source_type = config["source"]["type"]
        self.__source = importlib.import_module(f"source.{config['source']['type']}").Source(config["source"]["config"])
        self.__redis = redis.Redis(decode_responses = True)

    def __get_bytes(self, download_info: dict, start: int, end: int) -> bytes:
        if start >= end:
            return b""
        requests_headers = download_info["headers"]
        requests_headers["Range"] = f"bytes={start}-{end - 1}"
        try:
            return requests.get(download_info["url"], headers = requests_headers, proxies = download_info["proxy"]).content
        except:
            raise ValueError('fail to get bytes')

    def __get_init_nonce(self, download_info):
        size = int(requests.head(download_info["url"], headers = download_info["headers"],
                                 proxies = download_info["proxy"]).headers.get("Content-Length", 0))
        init_none = self.__get_bytes(download_info, FILEMAGIC_SIZE, FILEMAGIC_SIZE + FILENONCE_SIZE)
        return size, init_none

    def __get_file_info(self, file_id: str, refresh_download: bool = False) -> dict:
        key = self.__source_type + base64.urlsafe_b64encode(file_id.encode("utf-8")).decode("ascii")
        file_info = self.__redis.hgetall(key)
        if file_info == {}:
            download = self.__source.get_file(file_id)
            size, init_nonce = self.__get_init_nonce(download)
            real_size = count_size(size)
            file_info = {"size": size, "real_size": real_size, "init_nonce": base64.b64encode(init_nonce).decode("utf-8"),
                         "download": json.dumps(download)}
            self.__redis.hset(key, mapping = file_info)
            self.__redis.expire(key, 1800)
            return file_info
        if refresh_download: # 刷新信息
            download = self.__source.get_file(file_id)
            file_info["download"] = json.dumps(download)
            self.__redis.hset(key, mapping = file_info)
            self.__redis.expire(key, 1800)
        return file_info
    
    def decrypted_file_size(self, file_id: str) -> int:
        file_info = self.__get_file_info(file_id)
        return int(file_info["real_size"])

    # 解密，streaming响应的迭代器
    # @start: 加密前文件bytes读取起始位
    # @end: 加密前文件bytes读取截止位
    # @chunk_size: 单次读取文件块最大值
    def decrypted_bytes(self, file_id: str, start: int, end: int, chunk_size: int = BLOCK_CHUNK_NUM * BLOCK_SIZE):
        start_ = start
        end_ = end
        file_info = self.__get_file_info(file_id)
        size = int(file_info["size"])
        real_size = int(file_info["real_size"])
        # 经过以下两步：
        # 1. end-start是BLOCK_SIZE的倍数，或者是加密后文件的最后一部分
        # 2. start~end的数据解密后包含原文件start_~end_的数据
        start = count_pos(start) # 向前取整，计算加密文件的读取起始位
        end = min(count_pos(end, False), size)  # 向后取整，计算加密文件的读取截止位
        # 计算解密后数据的偏移量
        start_offset = start_ - count_block_num(start) * BLOCKDATA_SIZE
        end_offset = (real_size if (end >= size) else (count_block_num(end) * BLOCKDATA_SIZE)) - end_ - 1
        # 返回数据
        is_start = True
        while (start < end):
            read_size = min(chunk_size, end - start) # 单次bytes读取量
            # 读取数据
            try:
                stream_bytes = self.__get_bytes(json.loads(file_info["download"]), start, start + read_size)
            except:
                file_info = self.__get_file_info(file_id, True)
                stream_bytes = self.__get_bytes(json.loads(file_info["download"]), start, start + read_size)
            stream_bytes = self.__rclone.File.bytes_decrypt(stream_bytes, base64.b64decode(file_info["init_nonce"].encode("utf-8")), count_block_num(start))
            # 根据情况进行数据截取
            if is_start:
                stream_bytes = stream_bytes[start_offset :]
                is_start = False
            start = start + read_size
            if start >= end:
                if not end_offset == 0:
                    stream_bytes =  stream_bytes[: -end_offset]
            yield stream_bytes
    
    def get_doujinshi(self) -> list[tuple[str]]:
        doujinshi = []
        items = self.__source.get_doujinshi()
        for item in items:
            if self.__name_obfuscate:
                name = self.__rclone.Name.obfuscate_decrypt(item[0])
            else:
                name = self.__rclone.Name.standard_decrypt(item[0])
            doujinshi.append((name, item[1]))
        return doujinshi
    
    def get_file(self, file_id: str) -> str:
        return {"url": f"decrypt_{file_id}", "suffix_range": False, "headers": {}, "proxy": {}}