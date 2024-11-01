import re
import time
import json
import requests
from lib.utils import SourceType

MIXED_TAGS = ['kodomo doushi', 'animal on animal', 'body swap', 'multimouth blowjob', 'multiple handjob', 'frottage', 'multiple assjob',
              'multiple footjob', 'nudism', 'ffm threesome', 'gang rape', 'group', 'mmf threesome', 'mmt threesome', 'mtf threesome',
              'oyakodon', 'shimaidon', 'ttm threesome', 'twins', 'incest', 'inseki', 'low incest']

class Source:
    TYPE = SourceType.web
    SLEEP = 0.5

    def __init__(self, config) -> None:
        if not config["proxy"] == "":
            self.__proxies = {"http": config["proxy"], "https": config["proxy"]}
        else:
            self.__proxies = {}
        if config["webp"]:
            self.__webp = True
        else:
            self.__webp = False
    
    def __get_gg(self, id):
        res = requests.get(f"https://ltn.hitomi.la/gg.js?_={int(time.time() * 1000)}", proxies = self.__proxies,
                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:129.0) Gecko/20100101 Firefox/129.0",
                            "Referer": f"https://hitomi.la/reader/{id}.html"})
        text = res.text
        end = text.find("; break;")
        start = text.find("switch (g) {") + 18
        gg_b = text[text.find("b: '") + 4 : -5]
        gg_m = text[start : end - 7].split(":\ncase ")
        return gg_b, gg_m, int(text[end - 1])
    
    def __count_subdomain(self, url, base, gg_m, v):
        pattern = r"/[0-9a-f]{61}([0-9a-f]{2})([0-9a-f])"
        m = re.search(pattern, url)
        if m == None:
            sub = "a"
        else:
            r = int(m[2] + m[1], 16)
            if str(r) in gg_m:
                r = v
            else:
                r = int(v == 0)
            sub = chr(97 + r) + base
        return url.replace("//a.", f"//{sub}.")
    
    def __get_urls(self, images, id):
        gg_b, gg_m, v = self.__get_gg(id)
        img_urls = []
        for img in images:
            haswebp = img["haswebp"]
            hasavif = img["hasavif"]
            ext = None
            if self.__webp:
                if haswebp:
                    ext = "webp"
                elif hasavif:
                    ext = "avif"
            else:
                if hasavif:
                    ext = "avif"
                elif haswebp:
                    ext = "webp"
            if ext == None:
                raise RuntimeError("fail to get image url of hitomi")
            m = re.search(r"(..)(.)$", img["hash"])
            gg_s = str(int(m.group(2) + m.group(1), 16))
            url = "https://a.hitomi.la/" + ext + "/" + gg_b + gg_s + "/" + img["hash"] + "." + ext
            img_urls.append(self.__count_subdomain(url, "a", gg_m, v))
        return img_urls
    
    def __get_thumbnail(self, image, id):
        gg_b, gg_m, v = self.__get_gg(id)
        if self.__webp:
            url = "https://a.hitomi.la/" + "webpbigtn/" + re.sub(r'^.*(..)(.)$', r'\2/\1/' + image["hash"], image["hash"]) + ".webp"
        else:
            url = "https://a.hitomi.la/" + "avifbigtn/" + re.sub(r'^.*(..)(.)$', r'\2/\1/' + image["hash"], image["hash"]) + ".avif"
        url = self.__count_subdomain(url, "tn", gg_m, v)
        return url

    def get_metadata(self, id: str) -> dict:
        if id.startswith("http"):
            id = id.split("/")[-1].split("#")[0]
            id = id[0: -5]
        id_ = id.split("-")[-1]
        res = requests.get(f"https://ltn.hitomi.la/galleries/{id_}.js", proxies = self.__proxies,
                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:129.0) Gecko/20100101 Firefox/129.0",
                           "Referer": f"https://hitomi.la/doujinshi/{id}.html"})
        data = json.loads(res.content[18 :])
        tags = []
        tags.append("category:" + data["type"])
        if not data["characters"] == None:
            for i in data["characters"]:
                tags.append("character:" + i["character"])
        if not data["language"] == None:
            tags.append("language:" + data["language"])
        if not data["artists"] == None:
            for i in data["artists"]:
                tags.append("artist:" + i["artist"])
        if not data["parodys"] == None:
            for i in data["parodys"]:
                tags.append("parody:" + i["parody"])
        if not data["groups"] == None:
            for i in data["groups"]:
                tags.append("group:" + i["group"])
        for tag in data["tags"]:
            if "female" in tag:
                if tag["female"] == "1":
                    tags.append("female:" + tag["tag"])
                else:
                    tags.append("male:" + tag["tag"])
            else:
                if tag["tag"] in MIXED_TAGS:
                    tags.append("mixed:" + tag["tag"])
                else:
                    tags.append("other:" + tag["tag"])
        return {"id": data["id"], "title": data["title"], "pagecount": len(data["files"]), "tags": tags,
                "cover": {"url": self.__get_thumbnail(data["files"][0], data["id"]), "headers": {"Referer": f"https://hitomi.la/doujinshi/{id}.html"}}}

    def get_pages(self, id: str) -> dict:
        res = requests.get(f"https://ltn.hitomi.la/galleries/{id}.js", proxies = self.__proxies,
                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:129.0) Gecko/20100101 Firefox/129.0",
                            "Referer": f"https://hitomi.la/reader/{id}.html"})
        data = json.loads(res.content[18 :])
        return {"urls": self.__get_urls(data["files"], id), "headers": {"Referer": f"https://hitomi.la/reader/{id}.html"}}