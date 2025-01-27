import os
import sqlite3
from lib.utils import SourceType

class Source:
    TYPE = SourceType.web
    SLEEP = 0.1

    def __init__(self, config) -> None:
        connection = sqlite3.connect(".data/urlcollection.db")
        cursor = connection.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS collection (
                title TEXT PRIMARY KEY,
                urls TEXT
            )''')
        connection.commit()
        cursor.close()
        connection.close()

    def get_metadata(self, id: str) -> dict:
        connection = sqlite3.connect(".data/urlcollection.db")
        cursor = connection.cursor()
        id_splited = id.split("#")
        title = id_splited[0]
        urls = id_splited[1].strip("$")
        cursor.execute("SELECT title FROM collection WHERE title LIKE ?", (title + "%",))
        results = cursor.fetchall()
        index = 0
        for result in results:
            try:
                remain = result[0].removeprefix(title)
                if remain == "":
                    index = 1
                else:
                    index_ = int(remain)
                    if index_ >= index:
                        index = index_ + 1
            except:
                pass
        if index > 0:
            title = f"{title} {index}"
        cursor.execute("INSERT INTO collection (title, urls) VALUES (?, ?)", (title, urls))
        connection.commit()
        cursor.close()
        connection.close()
        urls = urls.split("$")
        return {"id": title + "#", "title": title, "pagecount": len(urls), "tags": [],
                "cover": {"url": urls[0], "headers": {}}}

    def get_pages(self, id: str) -> dict:
        connection = sqlite3.connect(".data/urlcollection.db")
        cursor = connection.cursor()
        title = id[: -1]
        cursor.execute(f"SELECT urls FROM collection WHERE title = ?", (title,))
        result = cursor.fetchone()
        if result:
            urls = result[0].split("$")
        else:
            urls = []
        cursor.close()
        connection.close()
        return {"urls": urls, "headers": {}}