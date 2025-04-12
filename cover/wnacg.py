import re
import time
import requests
from bs4 import BeautifulSoup
from lib.utils import Doujinshi

def get_cover(proxy, doujinshi: Doujinshi, url) -> bytes:
    if url != None:
        res = requests.get(url, proxies = proxy,
                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:129.0) Gecko/20100101 Firefox/129.0"})
        soup = BeautifulSoup(res.content, "html.parser")
        image_url = "http:" + soup.find(class_ = "uwthumb").img.attrs["src"].replace("////", "//")
    else:
        name = re.sub(r"[\【\[][^\\\]\【\】]+[\】\]]", "", doujinshi.title).strip()
        res = requests.get(f"https://www.wnacg.com/search/?q={name}&f=_all&s=create_time_DESC&syn=yes", proxies = proxy,
                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:129.0) Gecko/20100101 Firefox/129.0"})
        soup = BeautifulSoup(res.content, "html.parser")
        image_url = "http:" + soup.find("div", class_ = "pic_box").img.attrs["src"]
    time.sleep(0.5)
    return requests.get(image_url, proxies = proxy).content