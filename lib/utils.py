import os
import json
import shutil
import requests
import importlib

def app_init(app_state) -> None:
    client = app_state["redis_client"]
    try:
        client.flushall()
    except:
        print("please start redis first")
        exit()
    os.makedirs(".data/cache", exist_ok = True)
    os.makedirs(".data/thumb", exist_ok = True)
    # 缓存大小检查
    cache_size = get_cache_size()
    cache_size_limit = app_state["settings"]["max_cache_size"] * 1024 * 1024
    if cache_size >= cache_size_limit:
        try:
            shutil.rmtree(".data/cache")
        except:
            pass
        os.makedirs(".data/cache", exist_ok = True)
        cache_size = 0
    client.set("cache_size", cache_size)
    client.set("cache_size_limit", cache_size_limit)

def get_cache_size() -> int:
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(".data/cache"):
        for filename in filenames:
            file_path = os.path.join(dirpath, filename)
            if os.path.isfile(file_path):
                total_size = total_size + os.path.getsize(file_path)
    return total_size

def get_ehtag_database(proxy):
    print("check for EhTagTranslation database update...")
    releases_url = "https://api.github.com/repos/EhTagTranslation/Database/releases"
    content = requests.get(releases_url, proxies = proxy).content
    json_data = json.loads(content)
    release_tag_name = json_data[0]["tag_name"]
    if not os.path.exists(f".data/tag_database.{release_tag_name}.json"):
        for file_name in os.listdir(".data"):
            if "tag_database" in file_name:
                try:
                    os.remove(os.path.join(".data", file_name))
                except:
                    pass
        print("find new version, try to download...")
        download_url = "https://github.com/EhTagTranslation/Database/releases/latest/download/db.text.json"
        content = requests.get(download_url, proxies = proxy).content
        json_data = json.loads(content)
        data = {}
        for t in json_data["data"][2 :]:
            data_content = {}
            for i in t["data"].keys():
                data_content[i] = t["data"][i]["name"]
            data[t["namespace"]] = data_content
        with open(f".data/tag_database.{release_tag_name}.json", "wb") as f:
            f.write(json.dumps(data).encode("utf-8"))
        return data
    with open(f".data/tag_database.{release_tag_name}.json", "rb") as f:
        return json.loads(f.read())

def load_settings() -> dict:
    with open(".data/config.json", "r", encoding = "utf-8") as f:
        settings = json.loads(f.read())["settings"]
    if settings["proxy"] != "":
        settings["proxy"] = {"http": settings["proxy"], "https": settings["proxy"]}
    else:
        settings["proxy"] = {}
    if settings["tag_translate"]:
        settings["tag_translate"] = get_ehtag_database(settings["proxy"])
    else:
        settings["tag_translate"] = None
    return settings

def load_sources() -> dict:
    sources = {}
    # 读取配置
    with open(".data/config.json", "r", encoding = "utf-8") as f:
        source_config = json.loads(f.read())["source"]
    for key in source_config.keys():
        sources[key] = importlib.import_module(f"source.{source_config[key]['type']}").Source(source_config[key]["config"])
    return sources

def get_sources() -> list:
    with open(".data/config.json", "r", encoding = "utf-8") as f:
        source_config = json.loads(f.read())["source"]
    with open(os.path.join("source", "info.json"), "rb") as f:
        infos = json.loads(f.read())
    s = {}
    for i in source_config.keys():
        s[i] = infos[source_config[i]["type"]]
    return s

def get_file_infos(path: str) -> list:
    with open(os.path.join(path, "info.json"), "rb") as f:
        infos = json.loads(f.read())
    s = []
    for i in os.listdir(path):
        n, e = os.path.splitext(i)
        if e in [".py", ".PY"] and (not n == "__init__"):
            s.append({"name": infos[n]["name"], "value": n, "description": infos[n]["description"]})
    return s