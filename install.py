import os
import json

# create data folder
print("create data folder...")
os.makedirs(".data", exist_ok = True)
# create doujinshi library folder
os.makedirs(".data/doujinshi", exist_ok = True)
# create config file
print("create config file...")
with open(".data/config.json", "w", encoding = "utf-8") as f:
    f.write(json.dumps({
        "settings": {
            "host": "127.0.0.1",
            "port": 9000,
            "proxy": "",
            "proxy_webpage": False
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
print("config file: .data/config.json")
print("start application: python app.py")