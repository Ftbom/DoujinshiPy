import json
import uvicorn
import logging
from lib.utils import *
from fastapi import FastAPI
from sqlmodel import SQLModel, create_engine
from pymemcache.client.base import Client

class JsonSerde(object):
    def serialize(self, key, value):
        if isinstance(value, str):
            return value.encode("utf-8"), 1
        return json.dumps(value).encode("utf-8"), 2

    def deserialize(self, key, value, flags):
       if flags == 1:
           return value.decode("utf-8")
       if flags == 2:
           return json.loads(value.decode("utf-8"))
       raise Exception("Unknown serialization format")

logging.basicConfig(filename = ".data/info.log", encoding = "utf-8",
                    format = "%(levelname)s %(asctime)s %(message)s", level = logging.INFO)

app_init() # init

app = FastAPI()

app_state = {
    "settings": load_settings(),
    "sources": load_sources(), # load source configration from file
    "database_engine": create_engine("sqlite:///.data/database.db"), # load database
    "memcached_client": Client("localhost", serde=JsonSerde()) # create client
}

SQLModel.metadata.create_all(app_state["database_engine"])

from api import *

if __name__ == '__main__':
    try:
        app_state["memcached_client"].flush_all()
    except ConnectionRefusedError:
        print("please start memcached first")
        exit()
    uvicorn.run(app = app, host = app_state["settings"]["host"], port = app_state["settings"]["port"])