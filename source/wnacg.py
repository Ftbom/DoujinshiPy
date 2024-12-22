import requests
from lib.utils import SourceType
from bs4 import BeautifulSoup

class Source:
    TYPE = SourceType.web
    SLEEP = 0.5

    def __init__(self, config) -> None:
        if not config["proxy"] == "":
            self.__proxies = {"http": config["proxy"], "https": config["proxy"]}
        else:
            self.__proxies = {}
        self.__base_url = "https://www.wnacg.com"

    def get_metadata(self, id: str) -> dict:
        if id.startswith("http://") or id.startswith("https://"):
            id = id[id.find("-aid-") + 5 : id.find(".html")]
        res = requests.get(f"{self.__base_url}/photos-index-aid-{id}.html", proxies = self.__proxies,
                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:129.0) Gecko/20100101 Firefox/129.0"})
        soup = BeautifulSoup(res.content, "html.parser")
        title = soup.find("h2").get_text()
        pagecount_str = soup.find(class_ = "uwconn").find_all("label")[1].get_text()
        pagecount = int(pagecount_str.replace("頁數：", "").replace("P", ""))
        cover = "http:" + soup.find(class_ = "uwthumb").img.attrs["src"].replace("////", "//")
        tags = set()
        for tag in soup.find_all("a", class_ = "tagshow"):
            tags.add(tag.get_text())
        return {"id": id, "title": title, "pagecount": pagecount, "tags": list(tags), "cover": {"url": cover, "headers": {}}}

    def get_pages(self, id: str) -> dict:
        urls = []
        res = requests.get(f"{self.__base_url}/photos-gallery-aid-{id}.html", proxies = self.__proxies,
                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:129.0) Gecko/20100101 Firefox/129.0"})
        start = res.text.find("imglist")
        end = res.text.find("喜歡紳士")
        img_datas = res.text[start + 12 : end + 17].split("},{")
        for img in img_datas:
            urls.append("http:" + img[img.find("//") : img.find('", cap') - 1])
        return {"urls": urls[: -1], "headers": {}}