import re
import time
import requests
from lib.database import Doujinshi

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
    res = requests.post(url, proxies = proxy, json = json).json()
    data = res[0]
    tags = []
    if "language" in data:
        tags.append("language:" + data["language"])
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
            tags.append("other:" + i)
    time.sleep(0.5)
    return tags