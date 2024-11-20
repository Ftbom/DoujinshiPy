import os
import time
import json
import urllib
import requests
from lib.utils import SourceType
from msal import ConfidentialClientApplication

class Source:
    TYPE = SourceType.cloud
    SLEEP = 0.1

    def __init__(self, config) -> None:
        self.__client_id = config["id"]
        self.__client_secret = config["secret"]
        self.__business = config["business"]
        if self.__business:
            self.__appfolder = False
        else:
            self.__appfolder = config["appfolder"]
        if not config["proxy"] == "":
            self.__proxies = {"http": config["proxy"], "https": config["proxy"]}
        else:
            self.__proxies = {}
        self.__path = config["path"]
        self.__api_baseurl = "https://graph.microsoft.com/v1.0/me"
        self.__token = None
        if not os.path.exists(f".data/onedrive_{self.__client_id}.json"):
            self.__acquire_token()

    def __acquire_token(self) -> tuple:
        # get access_token and refresh_token
        if self.__appfolder:
            scopes = ["Files.ReadWrite.AppFolder"]
        else:
            scopes = ["Files.ReadWrite.All"]
        try:
            # get token
            client = ConfidentialClientApplication(client_id  = self.__client_id,
                            client_credential = self.__client_secret, proxies = self.__proxies)
            authorization_url = client.get_authorization_request_url(scopes)
            print("open this url in browser, and input the redirect url:")
            print(authorization_url)
            response_url = input()
            if self.__business:
                authorization_code = response_url[response_url.find("code=") + 5 : response_url.find("&session")]
            else:
                authorization_code = response_url[response_url.find("code=") + 5 :]
            res = client.acquire_token_by_authorization_code(code = authorization_code, scopes = scopes)
            expires_in = time.time() + res["expires_in"]
            with open(f".data/onedrive_{self.__client_id}.json", "w") as f: # save to file
                f.write(json.dumps({"access_token": res["access_token"], "refresh_token": res["refresh_token"],
                 "expires_in": expires_in}))
            return (res["access_token"], expires_in)
        except:
            raise RuntimeError("failed to get onedrive token")

    def __refresh_token(self) -> tuple:
        # refresh token
        if not os.path.exists(f".data/onedrive_{self.__client_id}.json"):
            return self.__acquire_token()
        with open(f".data/onedrive_{self.__client_id}.json", "r") as f:
            refresh_token = json.loads(f.read())["refresh_token"]
        if self.__appfolder:
            scopes = ["Files.ReadWrite.AppFolder"]
        else:
            scopes = ["Files.ReadWrite.All"]
        client = ConfidentialClientApplication(client_id  = self.__client_id,
                        client_credential = self.__client_secret, proxies = self.__proxies)
        try:
            res = client.acquire_token_by_refresh_token(refresh_token, scopes) # refresh
            expires_in = time.time() + res["expires_in"]
            with open(f".data/onedrive_{self.__client_id}.json", "w") as f:
                f.write(json.dumps({"access_token": res["access_token"], "refresh_token": res["refresh_token"],
                     "expires_in": expires_in}))
            return (res["access_token"], expires_in)
        except: # refresh_token timeout
            return self.__acquire_token()
    
    def __access_token(self) -> None:
        # read token from file
        if self.__token == None:
            if not os.path.exists(f".data/onedrive_{self.__client_id}.json"):
                (self.__token, self.__expires_in) = self.__acquire_token()
                return
            with open(f".data/onedrive_{self.__client_id}.json", "r") as f:
                token = json.loads(f.read())
            self.__token = token["access_token"]
            self.__expires_in = token["expires_in"]
        if time.time() > self.__expires_in:
            (self.__token, self.__expires_in) = self.__refresh_token()
    
    def __get_headers(self) -> dict:
        self.__access_token()
        return {"Authorization": "Bearer " + self.__token}

    def __get_children_by_path(self, path: str, link: str = False) -> list:
        if not link:
            path = path.strip("/")
            if not path == "":
                path_ = f":/{path}:"
            else:
                path_ = path
            if self.__appfolder:
                base_url = f"{self.__api_baseurl}/drive/special/approot"
            else:
                base_url = f"{self.__api_baseurl}/drive/root"
            res = requests.get(base_url + path_ + "/children?select=name,folder",
                               headers = self.__get_headers(), proxies = self.__proxies).json()
        else:
            res = requests.get(link, headers = self.__get_headers(), proxies = self.__proxies).json()
        if "error" in res:
            raise RuntimeError(res["error"]["message"])
        items = []
        for item in res["value"]:
            items.append({"path": path + "/" + item["name"], "name": item["name"], "folder": "folder" in item})
        if "@odata.nextLink" in res: # get next page
            items.extend(self.__get_children_by_path(path, res["@odata.nextLink"]))
        return items

    def get_doujinshi(self, path = None) -> list[tuple[str]]:
        doujinshi = []
        if path == None:
            path = self.__path.strip("/")
        items = self.__get_children_by_path(path)
        for item in items:
            if item["folder"]:
                doujinshi.extend(self.get_doujinshi(item["path"]))
            else:
                doujinshi.append((item["name"], item["path"]))
        return doujinshi
    
    def get_file(self, identifier: str) -> str:
        identifier = identifier.strip("/")
        if self.__appfolder:
            base_url = f"{self.__api_baseurl}/drive/special/approot:/"
        else:
            base_url = f"{self.__api_baseurl}/drive/root:/"
        res = requests.get(base_url + urllib.parse.quote(identifier),
                           headers = self.__get_headers(), proxies = self.__proxies).json()
        if "error" in res:
            raise RuntimeError(res["error"]["message"])
        return {"url": res["@microsoft.graph.downloadUrl"], "suffix_range": False, "headers": {}, "proxy": self.__proxies}
