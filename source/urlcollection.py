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
        urls = urls.split("$")
        cursor.execute("SELECT urls FROM collection WHERE title = ?", (title,))
        result = cursor.fetchone()
        if result:
            r_urls = result[0].split("$")
            r_urls.extend(urls)
            urls = r_urls
            cursor.execute("UPDATE collection SET urls = ? WHERE title = ?", ("$".join(urls), title,))
        else:
            cursor.execute("INSERT INTO collection (title, urls) VALUES (?, ?)", (title, "$".join(urls),))
        connection.commit()
        cursor.close()
        connection.close()
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