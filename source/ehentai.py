import os
import time
import pickle
import requests
from bs4 import BeautifulSoup
from lib.utils import SourceType

class Source:
    TYPE = SourceType.web
    SLEEP = 0.8

    # 使用简单的User-Agent模拟浏览器即可很大程度上防止IP被禁
    def __init__(self, config) -> None:
        self.__session = requests.Session()
        self.__session.headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:129.0) Gecko/20100101 Firefox/129.0"}
        if not config["proxy"] == "":
            self.__session.proxies = {"http": config["proxy"], "https": config["proxy"]}
        if ("user" in config) and (config["user"] != {}):
            self.__login = True
            self.__username = config["user"]["username"]
            self.__passwd = config["user"]["passwd"]
        else:
            self.__login = False
            if ("cookies" in config) and (config["cookies"] != {}):
                cookies = requests.utils.cookiejar_from_dict(config["cookies"], cookiejar = None, overwrite = True)
                self.__session.cookies = cookies
        if config["exhentai"]:
            self.__exhentai = True
            self.__base_url = "https://exhentai.org"
        else:
            self.__exhentai = False
            self.__base_url = "https://e-hentai.org"
        self.__banned_time = None
    
    def __update_cookies(self) -> None:
        igneous_cookie = None
        ipb_member_id_cookie = None
        ipb_pass_hash_cookie = None
        for cookie in self.__session.cookies:
            if cookie.name == "igneous":
                igneous_cookie = cookie
            elif cookie.name == "ipb_pass_hash":
                ipb_pass_hash_cookie = cookie
            elif cookie.name == "ipb_member_id":
                ipb_member_id_cookie = cookie
        current_time = time.time()
        need_update = False
        if self.__login:
            need_login = False
            if (ipb_member_id_cookie == None) or (ipb_pass_hash_cookie == None):
                if os.path.exists(os.path.join(".data", f"eh_{self.__username}.pkl")):
                    with open(os.path.join(".data", f"eh_{self.__username}.pkl"), "rb") as f:
                        cookies_from_file = pickle.load(f)
                    self.__session.cookies.update(cookies_from_file)
                    for cookie in self.__session.cookies:
                        if cookie.name == "igneous":
                            igneous_cookie = cookie
                        elif cookie.name == "ipb_pass_hash":
                            ipb_pass_hash_cookie = cookie
                        elif cookie.name == "ipb_member_id":
                            ipb_member_id_cookie = cookie       
            if (ipb_member_id_cookie == None) or (ipb_pass_hash_cookie == None):
                need_login = True
            elif (ipb_member_id_cookie.expires <= current_time) or (ipb_pass_hash_cookie.expires <= current_time):
                need_login = True
            if need_login:
                need_update = True # 登陆后重新获取igneous
                try:
                    self.__session.cookies.pop("ipb_pass_hash")
                    self.__session.cookies.pop("ipb_member_id")
                except:
                    pass
                self.__session.post("https://forums.e-hentai.org/index.php?act=Login&CODE=01", data={
                    "UserName": self.__username,
                    "PassWord": self.__passwd,
                    "submit": "Log me in",
                    "temporary_https": "off",
                    "CookieDate": "365"})
                with open(os.path.join(".data", f"eh_{self.__username}.pkl"), "wb") as f:
                    pickle.dump(self.__session.cookies, f)
        if igneous_cookie == None:
            need_update = True
        elif igneous_cookie.value == "mystery":
            self.__session.cookies.pop("igneous")
            need_update = True
        elif igneous_cookie.expires == None:
            need_update = False # 通过配置文件设置igneous，不更新igneous
        elif igneous_cookie.expires <= current_time:
            need_update = True
        if need_update:
            self.__session.get("https://exhentai.org/uconfig.php")

    def __is_banned(self):
        if self.__banned_time != None:
            if int(time.time()) > self.__banned_time:
                self.__banned_time = None
            else:
                raise RuntimeError("IP been banned by ehentai")
    
    def __error_handle(self, res):
        if res.status_code == 404:
            raise RuntimeError("not available in e-hentai")
        if res.text == "":
            raise RuntimeError("please update the userinfo or cookies of exhentai")
        if res.text.startswith("Your IP address has been temporarily banned"):
            if "and" in res.text:
                time_str = res.text[res.text.find("expires in") + 10 : -1].split("and")
                sec_num = int(time_str[1][0 : time_str[1].find("second")])
                min_num = int(time_str[0][0 : time_str[0].find("minute")])
            else:
                time_str = res.text[res.text.find("expires in") + 10 : -1]
                sec_num = int(time_str[0 : time_str.find("second")])
                min_num = 0
            self.__banned_time = int(time.time()) + min_num * 60 + sec_num
            raise RuntimeError("IP been banned by ehentai")

    def get_metadata(self, ids: str) -> dict:
        if ids.startswith("http://") or ids.startswith("https://"):
            ids = "_".join(ids[ids.find("/g/") + 3 : -1].strip("/").split("/"))
        self.__is_banned()
        id_s = ids.split("_")
        try:
            # res = self.__session.post("https://api.e-hentai.org/api.php",
            res = requests.post("https://api.e-hentai.org/api.php", proxies = self.__session.proxies,
                json = {"method": "gdata", "gidlist": [[int(id_s[0]), id_s[1]]], "namespace": 1},
                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:129.0) Gecko/20100101 Firefox/129.0"}).json()
        except:
            time.sleep(5.1) # 等待5s重试
            # res = self.__session.post("https://api.e-hentai.org/api.php",
            res = requests.post("https://api.e-hentai.org/api.php", proxies = self.__session.proxies,
                json = {"method": "gdata", "gidlist": [[int(id_s[0]), id_s[1]]], "namespace": 1},
                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:129.0) Gecko/20100101 Firefox/129.0"}).json()
        if res["gmetadata"][0]["expunged"]:
            raise RuntimeError(f"{res['gmetadata'][0]['title']} was delete from ehentai")
        tags = res["gmetadata"][0]["tags"]
        tags.append("category:" + res["gmetadata"][0]["category"].lower().replace(" ",""))
        return {"id": ids, "title": res["gmetadata"][0]["title"], "pagecount": int(res["gmetadata"][0]["filecount"]),
                "tags": tags, "cover": {"url": res["gmetadata"][0]["thumb"], "headers": {}}}

    def get_pages(self, ids: str) -> dict:
        return {}
    
    def get_page_urls(self, ids: str, page: int) -> dict:
        # page从0开始
        self.__is_banned()
        if self.__exhentai:
            self.__update_cookies()
        result = {}
        page_list = page // 40
        id_str = "/".join(ids.split("_"))
        res = self.__session.get(f"{self.__base_url}/g/{id_str}/?p={str(page_list)}")
        self.__error_handle(res)
        soup = BeautifulSoup(res.content, "html.parser")
        items = soup.find("div", id = "gdt").find_all("a")
        for i in range(len(items)):
            result[page_list * 40 + i] = items[i].attrs["href"]
        return result

    def get_img_url(self, url: str) -> dict:
        # 亦可通过api获取图片，通过api也需要图片页面的url
        # 首次通过api获取图片时，先要从html中获取showKey（每天更新，每个画廊不同）
        # api其他参数均来自图片页面url
        # {"method": "showpage","gid": 618395,"page": 1,"imgkey": "1463dfbc16","showkey": "387132-43f9269494"}
        self.__is_banned()
        if self.__exhentai:
            self.__update_cookies()
        res = self.__session.get(url)
        self.__error_handle(res)
        soup = BeautifulSoup(res.content, "html.parser")
        return {"url": soup.find("div", id = "i3").a.img.attrs["src"], "headers": {}}
