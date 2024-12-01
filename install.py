import os
import json

print("通过pip安装python包")
os.system("pip install -r requirements.txt")
# create data folder
print("创建数据文件夹...")
os.makedirs(".data", exist_ok = True)
# create doujinshi library folder
os.makedirs(".data/doujinshi", exist_ok = True)
# create config file
if os.path.exists(".data/config.json"):
    c = input("配置文件已存在，是否替换？[Y/n]")
    if not c in ["", "y", "Y"]:
        exit()
print("创建配置文件...")
with open(".data/config.json", "w", encoding = "utf-8") as f:
    f.write(json.dumps({
        "settings": {
            "host": "127.0.0.1",
            "port": 9000,
            "proxy": "",
            "proxy_webpage": False,
            "passwd": "demo",
            "max_num_perpage": 15, # 每页最大doujinshi数
            "max_cache_size": 2048, # 2GB
            "cache_expire": 30, # 天
            "tag_translate": False # 是否对tag进行翻译（针对other:xxx,female:xxx格式）
        },
        "source": {
            "Local": {
                "type": "local",
                "config": {
                    "path": ".data/doujinshi"
                }
            }
        }
    }, indent = 4))
print("--------------------------------")
print("配置文件：.data/config.json")
print("启动：python app.py")