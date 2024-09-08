import re
import time
import requests
from bs4 import BeautifulSoup
from lib.database import Doujinshi

def search_name(name: str, proxy: dict) -> str:
    res = requests.get(f"https://e-hentai.org/?f_search={name}", proxies = proxy,
                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:129.0) Gecko/20100101 Firefox/129.0"})
    soup = BeautifulSoup(res.content, "html.parser")
    url = soup.find("table", class_ = "itg").find_all("tr")[1].find("td", class_ = "gl3c").a.attrs["href"]
    return url

def get_cover(app_state, doujinshi: Doujinshi, url) -> None:
    if url == None:
        name = re.sub(r"[\【\[][^\\\]\【\】]+[\】\]]", "", doujinshi.title).strip()
        url = search_name(name, app_state["settings"]["proxy"])
    ids = url[url.find("/g/") + 3 : -1].strip("/").split("/")
    res = requests.post("https://api.e-hentai.org/api.php", proxies = app_state["settings"]["proxy"],
                json = {"method": "gdata", "gidlist": [[int(ids[0]), ids[1]]], "namespace": 1},
                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:129.0) Gecko/20100101 Firefox/129.0"}).json()
    with open(f".data/thumb/{doujinshi.id}.jpg", "wb") as f:
        res = requests.get(res["gmetadata"][0]["thumb"], proxies = app_state["settings"]["proxy"]).content
        f.write(res)
    time.sleep(0.8)