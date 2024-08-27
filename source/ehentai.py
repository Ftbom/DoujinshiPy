import time
import requests
from bs4 import BeautifulSoup
from lib.database import SourceType

class Source:
    TYPE = SourceType.web
    SLEEP = 1.5

    def __init__(self, config) -> None:
        self.__session = requests.Session()
        if not config["proxy"] == "":
            self.__session.proxies = {"http": config["proxy"], "https": config["proxy"]}
        if ("cookies" in config) and (config["cookies"] != {}):
            cookies = requests.utils.cookiejar_from_dict(config["cookies"], cookiejar = None,
                                                         overwrite = True)
            self.__session.cookies = cookies
        if config["exhentai"]:
            self.__base_url = "https://exhentai.org"
        else:
            self.__base_url = "https://e-hentai.org"
        self.__banned_time = None

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
        if "been temporarily banned" in res.text:
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
        return {"id": ids, "title": res["gmetadata"][0]["title"], "pagecount": int(res["gmetadata"][0]["filecount"]),
                "tags": res["gmetadata"][0]["tags"], "cover": {"url": res["gmetadata"][0]["thumb"], "headers": {}}}

    def get_pages(self, ids: str) -> dict:
        return {}
    
    def get_page_urls(self, ids: str, page: int) -> dict:
        # page从0开始
        self.__is_banned()
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
        self.__is_banned()
        res = self.__session.get(url, headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:129.0) Gecko/20100101 Firefox/129.0"})
        self.__error_handle(res)
        soup = BeautifulSoup(res.content, "html.parser")
        return {"url": soup.find("div", id = "i3").a.img.attrs["src"], "headers": {}}