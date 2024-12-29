import requests
from lib.utils import SourceType
from bs4 import BeautifulSoup

# https://www.joymiihub.com/
# https://www.ftvhunter.com/
# https://www.femjoyhunter.com/
# https://www.elitebabes.com/
# https://www.metarthunter.com/
# https://pmatehunter.com/
# https://www.xarthunter.com

class Source:
    TYPE = SourceType.web
    SLEEP = 0.5

    def __init__(self, config) -> None:
        if not config["proxy"] == "":
            self.__proxies = {"http": config["proxy"], "https": config["proxy"]}
        else:
            self.__proxies = {}

    def get_metadata(self, id: str) -> dict:
        if id.startswith("http://") or id.startswith("https://"):
            id = id.split("://")[1].strip("/")
            ids = id.split("/")
        else:
            ids = id.split("$")
        res = requests.get(f"http://{ids[0]}/{ids[1]}/", proxies = self.__proxies,
                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:129.0) Gecko/20100101 Firefox/129.0"})
        soup = BeautifulSoup(res.content, "html.parser")
        title = soup.find("h1").get_text()
        imgs = soup.find("ul", class_ = "list-gallery").find_all("img")
        pagecount = len(imgs)
        cover = imgs[0].attrs["src"].replace("_w400.", "_w200.")
        tags = set()
        for tag in soup.find("p", class_ = "link-btn").find_all("a"):
            tags.add(tag.get_text())
        return {"id": "$".join(ids), "title": title, "pagecount": pagecount, "tags": list(tags), "cover": {"url": cover, "headers": {}}}

    def get_pages(self, id: str) -> dict:
        ids = id.split("$")
        urls = []
        res = requests.get(f"http://{ids[0]}/{ids[1]}/", proxies = self.__proxies,
                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:129.0) Gecko/20100101 Firefox/129.0"})
        soup = BeautifulSoup(res.content, "html.parser")
        for img in soup.find("ul", class_ = "list-gallery").find_all("img"):
            urls.append(img.attrs["src"].replace("_w400.", "_1200."))
        return {"urls": urls, "headers": {}}