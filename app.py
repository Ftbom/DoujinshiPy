import uvicorn
import logging
from lib.utils import *
from fastapi.middleware.wsgi import WSGIMiddleware

logging.basicConfig(filename = ".data/info.log", encoding = "utf-8",
                    format = "%(levelname)s %(asctime)s %(message)s", level = logging.INFO)

from routes import *

if __name__ == '__main__':
    app_init(app_state) # init
    app.mount("/web", WSGIMiddleware(flask_app))
    uvicorn.run(app = app, host = app_state["settings"]["host"], port = app_state["settings"]["port"], access_log = False)