import base64
import requests
from lib.utils import SourceType
from xml.etree import ElementTree
from urllib.parse import unquote, urlsplit

class Source:
    TYPE = SourceType.cloud
    SLEEP = 0.1

    def __init__(self, config) -> None:
        if "username" in config:
            self.__auth = (config["username"], config["passwd"])
        else:
            self.__auth = None
        if not config["proxy"] == "":
            self.__proxies = {"http": config["proxy"], "https": config["proxy"]}
        else:
            self.__proxies = {}
        self.__base_url = config["url"].strip("/")
        if not self.__base_url.startswith("http"):
            self.__base_url = "http://" + self.__base_url
        parsed_url = urlsplit(self.__base_url)
        self.__base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
        self.__path = parsed_url.path

    def get_doujinshi(self, folder_path = "/") -> list[tuple[str]]:
        doujinshi = []
        if folder_path == "/":
            web_url = self.__base_url + self.__path
        else:
            web_url = self.__base_url + folder_path
        response = requests.request(
            "PROPFIND", web_url,
            auth = self.__auth, proxies = self.__proxies,
            headers = {
                "Depth": "1",  # 深度为 1 表示获取当前目录及其直接子项
                "Content-Type": "text/xml",
            },
            data = 
            """<?xml version="1.0" encoding="utf-8" ?>
                <d:propfind xmlns:d="DAV:">
                    <d:allprop/>
                </d:propfind>
            """
        )
        # 检查状态码
        if response.status_code in (207, 200):
            tree = ElementTree.fromstring(response.content)
            # 遍历响应中的文件和目录
            namespaces = {"d": "DAV:"}  # 定义命名空间
            for response_elem in tree.findall(".//d:response", namespaces):
                href = response_elem.find("d:href", namespaces).text
                if web_url.find(href.strip("/")) != -1:
                    continue
                if href.endswith("/"):
                    doujinshi.extend(self.get_doujinshi(href))
                else:
                    doujinshi.append((unquote(href.split("/")[-1]), href))
        return doujinshi
    
    def get_file(self, file_id: str) -> str:
        if self.__auth == None:
            headers = {}
        else:
            auth = base64.b64encode(f"{self.__auth[0]}:{self.__auth[1]}".encode()).decode()
            headers = {"Authorization": f"Basic {auth}"}
        return {"url": self.__base_url + file_id, "suffix_range": True,
                "headers": headers, "proxy": self.__proxies}