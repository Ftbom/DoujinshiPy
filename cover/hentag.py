import re
import time
import requests
from lib.utils import Doujinshi

def get_cover(source, proxy, doujinshi: Doujinshi, url) -> None:
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
    with open(f".data/thumb/{doujinshi.id}.jpg", "wb") as f:
        res = requests.get(res[0]["coverImageUrl"], proxies = proxy).content
        f.write(res)
    time.sleep(60)