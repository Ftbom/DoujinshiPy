import re
import time
import requests
from lib.utils import Doujinshi

MIXED_TAGS = ['kodomo doushi', 'animal on animal', 'body swap', 'multimouth blowjob', 'multiple handjob', 'frottage', 'multiple assjob',
              'multiple footjob', 'nudism', 'ffm threesome', 'gang rape', 'group', 'mmf threesome', 'mmt threesome', 'mtf threesome',
              'oyakodon', 'shimaidon', 'ttm threesome', 'twins', 'incest', 'inseki', 'low incest']
CATEGORIES_TRANS = {'manga': 'manga', 'doujin': 'doujinshi', 'artist cg': 'artistcg', 'game cg': 'gamecg', 'non-hentai': 'non-h',
                    'western': 'western'}

def get_tag(source, proxy, doujinshi: Doujinshi, url) -> list:
    if url == None:
        name = re.sub(r"[\【\[][^\\\]\【\】]+[\】\]]", "", doujinshi.title).strip()
        url = "https://hentag.com/api/v1/search/vault/title"
        json = {"title": name}
    else:
        if url.startswith("http"):
            url = url.strip("/").split("/")[-1]
        json = {"ids": [url]}
        url = "https://hentag.com/api/v1/search/vault/id"
    res = requests.post(url, proxies = proxy, json = json)
    data = res.json()[0]
    tags = []
    if "category" in data:
        try:
            tags.append("category:" + CATEGORIES_TRANS[data["category"]])
        except:
            pass
    # if "language" in data:
    #     tags.append("language:" + data["language"])
    if "circles" in data:
        for i in data["circles"]:
            tags.append("group:" + i)
    if "artists" in data:
        for i in data["artists"]:
            tags.append("artist:" + i)
    if "parodies" in data:
        for i in data["parodies"]:
            tags.append("parody:" + i)
    if "characters" in data:
        for i in data["characters"]:
            tags.append("character:" + i)
    if "femaleTags" in data:
        for i in data["femaleTags"]:
            tags.append("female:" + i)
    if "maleTags" in data:
        for i in data["maleTags"]:
            tags.append("male:" + i)
    if "otherTags" in data:
        for i in data["otherTags"]:
            if i in ["uncensored", "full censorship", "mosaic censorship"]:
                continue
            if i in MIXED_TAGS:
                tags.append("mixed:" + i)
            else:
                tags.append("other:" + i)
    time.sleep(60)
    return tags