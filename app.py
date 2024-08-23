import uvicorn
import logging
from lib.utils import *

logging.basicConfig(filename = ".data/info.log", encoding = "utf-8",
                    format = "%(levelname)s %(asctime)s %(message)s", level = logging.INFO)

from api import *

if __name__ == '__main__':
    app_init() # init
    try:
        app_state["memcached_client"].flush_all()
    except ConnectionRefusedError:
        print("please start memcached first")
        exit()
    uvicorn.run(app = app, host = app_state["settings"]["host"], port = app_state["settings"]["port"])