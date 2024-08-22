import requests
from lib.database import SourceType
from bs4 import BeautifulSoup

class Source:
    TYPE = SourceType.web

    def __init__(self, config) -> None:
        self.__base_url = "https://wnacg.com"
        pass

    def search(self, query: str, page: int, proxy) -> list:
        results = []
        res = requests.get(f"{self.__base_url}/search?q={query}&m=&syn=yes&f=_all&s=create_time_DESC&p={page}", proxies = proxy,
                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:129.0) Gecko/20100101 Firefox/129.0"})
        soup = BeautifulSoup(res.content, "html.parser")
        for item in soup.find_all(class_ = "gallary_item"):
            title = item.img.attrs["alt"]
            title = title.replace("</em>", "")
            title = title.replace("<em>", "")
            id_ = item.a.attrs["href"].replace("/photos-index-aid-", "").replace(".html", "")
            thumb = "http:" + item.img.attrs["src"]
            results.append({"id": id_, "title": title, "thumb": {"url": thumb, "headers": {}}})
        return results

    def get_metadata(self, id: str, proxy) -> dict:
        res = requests.get(f"{self.__base_url}/photos-index-aid-{id}.html", proxies = proxy,
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

    def get_pages(self, id: str, proxy) -> dict:
        urls = []
        res = requests.get(f"{self.__base_url}/photos-gallery-aid-{id}.html", proxies = proxy,
                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:129.0) Gecko/20100101 Firefox/129.0"})
        start = res.text.find("imglist")
        end = res.text.find("喜歡紳士")
        img_datas = res.text[start + 12 : end + 17].split("},{")
        for img in img_datas:
            urls.append("http:" + img[img.find("//") : img.find('", cap') - 1])
        return {"urls": urls[: -1], "headers": {}}