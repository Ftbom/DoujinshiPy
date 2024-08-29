import time
import requests
from bs4 import BeautifulSoup
from lib.database import SourceType

class Source:
    TYPE = SourceType.web
    SLEEP = 0.8

    # 使用简单的User-Agent模拟浏览器即可很大程度上防止IP被禁
    def __init__(self, config) -> None:
        self.__session = requests.Session()
        if not config["proxy"] == "":
            self.__session.proxies = {"http": config["proxy"], "https": config["proxy"]}
        if ("cookies" in config) and (config["cookies"] != {}):
            cookies = requests.utils.cookiejar_from_dict(config["cookies"], cookiejar = None,
                                                         overwrite = True)
            self.__session.cookies = cookies
        if config["exhentai"]:
            self.__exhentai = True
            self.__base_url = "https://exhentai.org"
        else:
            self.__exhentai = False
            self.__base_url = "https://e-hentai.org"
        self.__banned_time = None
    
    def __update_cookies(self) -> None:
        for cookie in self.__session.cookies:
            if cookie.name == "igneous":
                if cookie.value == "mystery":
                    self.__session.cookies.pop("igneous")
                else:
                    if (cookie.expires == None) or (cookie.expires > time.time()):
                        return
        print(self.__session.cookies)
        self.__session.get("https://exhentai.org/uconfig.php",
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:129.0) Gecko/20100101 Firefox/129.0"})
        print(self.__session.cookies)

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
            raise RuntimeError("please update the cookies of exhentai")
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
            res = self.__session.post("https://api.e-hentai.org/api.php",
                json = {"method": "gdata", "gidlist": [[int(id_s[0]), id_s[1]]], "namespace": 1},
                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:129.0) Gecko/20100101 Firefox/129.0"}).json()
        except:
            time.sleep(5.1) # 等待5s重试
            res = self.__session.post("https://api.e-hentai.org/api.php",
                json = {"method": "gdata", "gidlist": [[int(id_s[0]), id_s[1]]], "namespace": 1},
                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:129.0) Gecko/20100101 Firefox/129.0"}).json()
        if res["gmetadata"][0]["expunged"]:
            raise RuntimeError(f"{res['gmetadata'][0]['title']} was delete from ehentai")
        return {"id": ids, "title": res["gmetadata"][0]["title"], "pagecount": int(res["gmetadata"][0]["filecount"]),
                "tags": res["gmetadata"][0]["tags"], "cover": {"url": res["gmetadata"][0]["thumb"], "headers": {}}}

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
        res = self.__session.get(f"{self.__base_url}/g/{id_str}/?p={str(page_list)}",
                        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:129.0) Gecko/20100101 Firefox/129.0"})
        self.__error_handle(res)
        soup = BeautifulSoup(res.content, "html.parser")
        items = soup.find("div", id = "gdt").find_all(class_ = "gdtm")
        for i in range(len(items)):
            result[page_list * 40 + i] = items[i].div.a.attrs["href"]
        return result

    def get_img_url(self, url: str) -> dict:
        # 亦可通过api获取图片，通过api也需要图片页面的url
        # 首次通过api获取图片时，先要从html中获取showKey（每天更新，每个画廊不同）
        # api其他参数均来自图片页面url
        # {"method": "showpage","gid": 618395,"page": 1,"imgkey": "1463dfbc16","showkey": "387132-43f9269494"}
        self.__is_banned()
        if self.__exhentai:
            self.__update_cookies()
        res = self.__session.get(url, headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:129.0) Gecko/20100101 Firefox/129.0"})
        self.__error_handle(res)
        soup = BeautifulSoup(res.content, "html.parser")
        return {"url": soup.find("div", id = "i3").a.img.attrs["src"], "headers": {}}
