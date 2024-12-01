import time
import requests
from lib.utils import Doujinshi

def get_cover(source, proxy, doujinshi: Doujinshi, url) -> None:
    if url == None:
        return
    with open(f".data/thumb/{doujinshi.id}.jpg", "wb") as f:
        res = requests.get(url, proxies = proxy).content
        f.write(res)
    time.sleep(0.1)