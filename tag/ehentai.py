import re
import time
import requests
from bs4 import BeautifulSoup
from lib.utils import Doujinshi

def search_name(name: str, proxy: dict) -> str:
    res = requests.get(f"https://e-hentai.org/?f_search={name}", proxies = proxy,
                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:129.0) Gecko/20100101 Firefox/129.0"})
    soup = BeautifulSoup(res.content, "html.parser")
    url = soup.find("table", class_ = "itg").find_all("tr")[1].find("td", class_ = "gl3c").a.attrs["href"]
    return url

def get_tag(source, proxy, doujinshi: Doujinshi, url) -> list:
    if url == None:
        name = re.sub(r"[\【\[][^\\\]\【\】]+[\】\]]", "", doujinshi.title).strip()
        url = search_name(name, proxy)
    ids = url[url.find("/g/") + 3 : -1].strip("/").split("/")
    res = requests.post("https://api.e-hentai.org/api.php", proxies = proxy,
                json = {"method": "gdata", "gidlist": [[int(ids[0]), ids[1]]], "namespace": 1},
                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:129.0) Gecko/20100101 Firefox/129.0"}).json()
    time.sleep(0.8)
    tags = res["gmetadata"][0]["tags"]
    tags.append("category:" + res["gmetadata"][0]["category"].lower().replace(" ",""))
    for tag in tags:
        if "uncensored" in tag:
            tags.remove(tag)
        if "full censorship" in tag:
            tags.remove(tag)
        if "mosaic censorship" in tag:
            tags.remove(tag)
    return tags