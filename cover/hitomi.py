import re
import time
import json
import requests
from lib.utils import Doujinshi

def get_gg(id, proxy):
    res = requests.get(f"https://ltn.hitomi.la/gg.js?_={int(time.time() * 1000)}", proxies = proxy,
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:129.0) Gecko/20100101 Firefox/129.0",
                    "Referer": f"https://hitomi.la/reader/{id}.html"})
    text = res.text
    end = text.find("; break;")
    start = text.find("switch (g) {") + 18
    gg_b = text[text.find("b: '") + 4 : -5]
    gg_m = text[start : end - 7].split(":\ncase ")
    return gg_b, gg_m, int(text[end - 1])

def count_subdomain(url, base, gg_m, v):
    pattern = r"/[0-9a-f]{61}([0-9a-f]{2})([0-9a-f])"
    m = re.search(pattern, url)
    if m == None:
        sub = "a"
    else:
        r = int(m[2] + m[1], 16)
        if str(r) in gg_m:
            r = v
        else:
            r = int(v == 0)
        sub = chr(97 + r) + base
    return url.replace("//a.", f"//{sub}.")

def get_thumbnail(image, id, proxy):
    gg_b, gg_m, v = get_gg(id, proxy)
    url = "https://a.hitomi.la/" + "webpbigtn/" + re.sub(r'^.*(..)(.)$', r'\2/\1/' + image["hash"], image["hash"]) + ".webp"
    url = count_subdomain(url, "tn", gg_m, v)
    return url

def get_cover(source, proxy, doujinshi: Doujinshi, url) -> list:
    if url == None:
        # TODO: search
        return
    else:
        if url.startswith("http"):
            url = url.split("/")[-1].split("#")[0]
            url = url[0: -5]
        _url = url.split("-")[-1]
    res = requests.get(f"https://ltn.hitomi.la/galleries/{_url}.js", proxies = proxy,
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:129.0) Gecko/20100101 Firefox/129.0",
                       "Referer": f"https://hitomi.la/doujinshi/{url}.html"})
    data = json.loads(res.content[18 :])
    image_url = get_thumbnail(data["files"][0], data["id"], proxy)
    with open(f".data/thumb/{doujinshi.id}.jpg", "wb") as f:
        res = requests.get(image_url, proxies = proxy,
                    headers = {"Referer": f"https://hitomi.la/doujinshi/{id}.html"}).content
        f.write(res)
    time.sleep(0.5)