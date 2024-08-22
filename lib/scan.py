import os
import time
import logging
import requests
from sqlmodel import Session, select
from lib.database import Doujinshi, SourceType

def batch_add_to_library(app_state, id_list: list[str], source_name: str, is_replace: bool) -> None:
    client = app_state["memcached_client"]
    num = len(id_list)
    with Session(app_state["database_engine"]) as session:
        count = 0
        for id in id_list:
            count = count + 1
            result = session.exec(select(Doujinshi).where(Doujinshi.identifier == id).where(Doujinshi.source == source_name)).first()
            if result != None:
                if not is_replace:
                    client.set("add_status", f"adding to library {count}/{num}")
                    continue
                else:
                    if os.path.exists(f".data/thumb/{str(result.id)}.jpg"): # remove old thumb
                        os.remove(f".data/thumb/{str(result.id)}.jpg")
                    session.delete(result)
            try:
                metadata = app_state["sources"][source_name].get_metadata(id, app_state["settings"]["proxy"])
                doujinshi = Doujinshi(title = metadata["title"], pagecount = metadata["pagecount"],
                            tags = "|".join(metadata["tags"]), identifier = metadata["id"],
                            type = SourceType.web, source = source_name)
                # save cover
                with open(f".data/thumb/{str(doujinshi.id)}.jpg", "wb") as f:
                    res = requests.get(metadata["cover"], proxies = app_state["settings"]["proxy"])
                    f.write(res.content)
                session.add(doujinshi) # save to database
                logging.info(f"add {id} of {source_name} source to library")
                time.sleep(0.5)
            except:
                logging.error(f"fail to add {id} of {source_name} source to library")
            client.set("add_status", f"adding to library {count}/{num}")
        session.commit()
        client.set("add_status", "finished")

def clean_database_by_source_name(session: Session, name: str, doujinshi_list: list) -> list:
    statement = select(Doujinshi).where(Doujinshi.source == name)
    results = session.exec(statement)
    for result in results:
        info = (result.title, result.identifier)
        if info in doujinshi_list:
            doujinshi_list.remove(info) # already exist
        else:
            # remove old data (not exist in new datas)
            if os.path.exists(f".data/thumb/{str(result.id)}.jpg"): # remove old thumb
                os.remove(f".data/thumb/{str(result.id)}.jpg")
            session.delete(result)
    return doujinshi_list

def scan_to_database(app_state, name: str) -> None:
    source_object = app_state["sources"][name]
    client = app_state["memcached_client"]
    client.set("scan_source_name", name) # record the name of source library
    logging.info(f"start scanning the {name} library...")
    try:
        client.set("scan_status_code", 1) # set the status code
        logging.info(f"start getting the doujinshi list of {name} library...")
        doujinshi_list = source_object.get_doujinshi() # retrieve the doujinshi list
    except Exception as e:
        logging.error(f"failed to scan the {name} library, error message: {e}")
        client.set("scan_status_code", 4)
        return
    # save information to the database
    client.set("scan_status_code", 2)
    logging.info(f"start saving the information of {name} library to database...")
    with Session(app_state["database_engine"]) as session:
        logging.info(f"clear the old datas from the {name} library")
        doujinshi_list = clean_database_by_source_name(session, name, doujinshi_list)
        for d in doujinshi_list:
            doujinshi = Doujinshi(title = d[0], identifier = d[1],
                              type = source_object.TYPE, source = name)
            session.add(doujinshi)
            logging.info(f"add {d[0]}")
        session.commit()
    client.set("scan_status_code", 3)
    logging.info(f"the {name} library has been scanned")