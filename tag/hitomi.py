import time
import json
import requests
from lib.utils import Doujinshi

MIXED_TAGS = ['kodomo doushi', 'animal on animal', 'body swap', 'multimouth blowjob', 'multiple handjob', 'frottage', 'multiple assjob',
              'multiple footjob', 'nudism', 'ffm threesome', 'gang rape', 'group', 'mmf threesome', 'mmt threesome', 'mtf threesome',
              'oyakodon', 'shimaidon', 'ttm threesome', 'twins', 'incest', 'inseki', 'low incest']

def get_tag(source, proxy, doujinshi: Doujinshi, url) -> list:
    if url == None:
        # TODO: search
        return []
    else:
        if url.startswith("http"):
            url = url.split("/")[-1].split("#")[0]
            url = url[0: -5]
        _url = url.split("-")[-1]
    res = requests.get(f"https://ltn.hitomi.la/galleries/{_url}.js", proxies = proxy,
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:129.0) Gecko/20100101 Firefox/129.0",
                       "Referer": f"https://hitomi.la/doujinshi/{url}.html"})
    data = json.loads(res.content[18 :])
    tags = []
    tags.append("category:" + data["type"])
    if not data["characters"] == None:
        for i in data["characters"]:
            tags.append("character:" + i["character"])
    # if not data["language"] == None:
    #     tags.append("language:" + data["language"])
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
            if tag["tag"] in ["uncensored", "full censorship", "mosaic censorship"]:
                continue
            if tag["tag"] in MIXED_TAGS:
                tags.append("mixed:" + tag["tag"])
            else:
                tags.append("other:" + tag["tag"])
    time.sleep(1)
    return tags