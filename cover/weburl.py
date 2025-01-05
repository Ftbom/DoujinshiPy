import time
import requests
from lib.utils import Doujinshi

def get_cover(source, proxy, doujinshi: Doujinshi, url) -> bytes:
    if url == None:
        return b''
    time.sleep(0.1)
    return requests.get(url, proxies = proxy).content