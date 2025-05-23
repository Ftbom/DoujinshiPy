import re
import time
import requests
from bs4 import BeautifulSoup
from lib.utils import Doujinshi

def get_tag(proxy, doujinshi: Doujinshi, url) -> list[str]:
    if url == None:
        name = re.sub(r"[\【\[][^\\\]\【\】]+[\】\]]", "", doujinshi.title).strip()
        res = requests.get(f"https://www.wnacg.com/search/?q={name}&f=_all&s=create_time_DESC&syn=yes", proxies = proxy,
                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:129.0) Gecko/20100101 Firefox/129.0"})
        soup = BeautifulSoup(res.content, "html.parser")
        url = "https://www.wnacg.com" + soup.find("div", class_ = "pic_box").a.attrs["href"]
        time.sleep(0.1)
    res = requests.get(url, proxies = proxy,
                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:129.0) Gecko/20100101 Firefox/129.0"})
    soup = BeautifulSoup(res.content, "html.parser")
    tags = []
    for tag in soup.find("div", class_ = "addtags").find_all("a", class_ = "tagshow"):
        tag = tag.get_text()
        add = True
        for exclude in ["薄码", "厚码", "无修", "无码", "無修", "修正", "马赛克", "黑条", "黑條"]:
            if exclude in tag:
                add = False
                break
        if add:
            tags.append(tag)
    time.sleep(0.5)
    return tags