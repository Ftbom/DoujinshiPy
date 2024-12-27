import re
import time
import requests
from lib.utils import Doujinshi

def get_cover(source, proxy, doujinshi: Doujinshi, url) -> bytes:
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
    time.sleep(60)
    return requests.get(res[0]["coverImageUrl"], proxies = proxy).content