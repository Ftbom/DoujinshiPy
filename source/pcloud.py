import time
import requests
from hashlib import sha1
from lib.database import SourceType

class Source:
    TYPE = SourceType.cloud

    def __init__(self, config) -> None:
        self.__username = config["username"].lower().encode("utf-8")
        self.__password = config["passwd"].encode("utf-8")
        if not config["proxy"] == "":
            self.__proxies = {"http": config["proxy"], "https": config["proxy"]}
        else:
            self.__proxies = {}
        self.__path = config["path"]
        self.__api_base = "https://eapi.pcloud.com/"
        self.__session = requests.Session()
        self.__session.proxies = self.__proxies
        self.__auth_expire = None
    
    def __getdigest(self):
        res = self.__do_request("getdigest", authenticate = False)
        return bytes(res["digest"], "utf-8")
    
    def __get_auth_token(self):
        if (self.__auth_expire) and (time.time() < self.__auth_expire):
            return self.__auth_token
        digest = self.__getdigest()
        passworddigest = sha1(
            self.__password + bytes(sha1(self.__username).hexdigest(), "utf-8") + digest
        )
        params = {
            "getauth": 1,
            "logout": 1,
            "username": self.__username.decode("utf-8"),
            "digest": digest.decode("utf-8"),
            "passworddigest": passworddigest.hexdigest(),
            "authexpire": 2678400
        }
        res = self.__do_request("userinfo", authenticate = False, **params)
        if "auth" not in res:
            raise RuntimeError("fail to auth pcloud")
        self.__auth_token = res["auth"]
        self.__auth_expire = time.time() + 2678400
        return self.__auth_token
    
    def __do_request(self, method: str, authenticate = True, **kw):
        if authenticate:  # Password authentication
            params = {"auth": self.__get_auth_token()}
        else:
            params = {}
        params.update(kw)
        result = self.__session.get(self.__api_base + method, params = params).json()
        return result

    def get_doujinshi(self, folder_path = None) -> list[tuple[str]]:
        if folder_path == None:
            folder_path = "/" + self.__path.strip("/")
        doujinshi = []
        result = self.__do_request("listfolder", path = folder_path)
        for item in result["metadata"]["contents"]:
            if item["isfolder"]:
                doujinshi.extend(self.get_doujinshi(item["path"]))
            else:
                doujinshi.append((item["name"], item["fileid"]))
        return doujinshi
    
    def get_file(self, file_id: str) -> str:
        res = self.__do_request("getfilelink", fileid = int(file_id))
        return {"url": f"https://" + res["hosts"][0] + res["path"], "suffix_range": True, "headers": {}, "proxy": self.__proxies}
        pass