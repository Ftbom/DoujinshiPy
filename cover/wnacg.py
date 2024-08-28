import re
import time
import requests
from bs4 import BeautifulSoup
from lib.database import Doujinshi

def get_cover(app_state, doujinshi: Doujinshi, url) -> None:
    if url != None:
        res = requests.get(url, proxies = app_state["settings"]["proxy"],
                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:129.0) Gecko/20100101 Firefox/129.0"})
        soup = BeautifulSoup(res.content, "html.parser")
        image_url = "http:" + soup.find(class_ = "uwthumb").img.attrs["src"].replace("////", "//")
    else:
        name = re.sub(r"[\【\[][^\\\]\【\】]+[\】\]]", "", doujinshi.title).strip()
        res = requests.get(f"https://www.wnacg.com/search/?q={name}&f=_all&s=create_time_DESC&syn=yes",
                proxies = app_state["settings"]["proxy"],
                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:129.0) Gecko/20100101 Firefox/129.0"})
        soup = BeautifulSoup(res.content, "html.parser")
        image_url = "http:" + soup.find("div", class_ = "pic_box").img.attrs["src"]
    with open(f".data/thumb/{doujinshi.id}.jpg", "wb") as f:
        res = requests.get(image_url, proxies = app_state["settings"]["proxy"]).content
        f.write(res)
    time.sleep(0.5)