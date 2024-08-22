import requests
from lib.database import SourceType
from bs4 import BeautifulSoup

class Source:
    TYPE = SourceType.web

    def __init__(self, config) -> None:
        pass

    def get_metadata(self, id: str, proxy) -> dict:
        res = requests.get(f"https://wnacg.com/photos-index-aid-{id}.html", proxies = proxy,
                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:129.0) Gecko/20100101 Firefox/129.0"})
        soup = BeautifulSoup(res.content, "html.parser")
        title = soup.find("h2").get_text()
        pagecount_str = soup.find(class_ = "uwconn").find_all("label")[1].get_text()
        pagecount = int(pagecount_str.replace("頁數：", "").replace("P", ""))
        cover = "http:" + soup.find(class_ = "uwthumb").img.attrs["src"].replace("////", "//")
        tags = set()
        for tag in soup.find_all("a", class_ = "tagshow"):
            tags.add(tag.get_text())
        return {"id": id, "title": title, "pagecount": pagecount, "tags": list(tags), "cover": cover}

    def get_pages(self, id: str, proxy) -> list[str]:
        urls = []
        res = requests.get(f"https://wnacg.com/photos-gallery-aid-{id}.html", proxies = proxy,
                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:129.0) Gecko/20100101 Firefox/129.0"})
        start = res.text.find("imglist")
        end = res.text.find("喜歡紳士")
        img_datas = res.text[start + 12 : end + 17].split("},{")
        for img in img_datas:
            urls.append("http:" + img[img.find("//") : img.find('", cap') - 1])
        return urls[: -1]