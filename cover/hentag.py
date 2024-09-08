import re
import time
import requests
from lib.database import Doujinshi

def get_cover(app_state, doujinshi: Doujinshi, url) -> None:
    if url == None:
        name = re.sub(r"[\【\[][^\\\]\【\】]+[\】\]]", "", doujinshi.title).strip()
        url = "https://hentag.com/api/v1/search/vault/title"
        json = {"title": name}
    else:
        if url.startswith("http"):
            url = url.strip("/").split("/")[-1]
        json = {"ids": [url]}
        url = "https://hentag.com/api/v1/search/vault/id"
    res = requests.post(url, proxies = app_state["settings"]["proxy"], json = json).json()
    with open(f".data/thumb/{doujinshi.id}.jpg", "wb") as f:
        res = requests.get(res[0]["coverImageUrl"], proxies = app_state["settings"]["proxy"]).content
        f.write(res)
    time.sleep(0.5)