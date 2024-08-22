import os
import uuid
import random
import logging
from enum import Enum
from typing import Union
from sqlmodel import Field, SQLModel, Session, select

class SourceType(Enum):
    local = 0
    cloud = 1
    web = 2

class Doujinshi(SQLModel, table = True):
    id: uuid.UUID = Field(default_factory = uuid.uuid4, primary_key = True) # generate id
    title: str
    pagecount: Union[int, None] = None
    tags: str = ''
    groups: str = ''
    identifier: str
    type: SourceType = SourceType.local
    source: str

class Group(SQLModel, table = True):
    id: uuid.UUID = Field(default_factory = uuid.uuid4, primary_key = True) # generate id
    name: str

def get_metadata(doujinshi: Doujinshi) -> dict:
    tags = doujinshi.tags.split("|")
    try:
        tags.remove("")
    except:
        pass
    return {"id": str(doujinshi.id), "title": doujinshi.title,
            "tags": tags, "cover": f"/doujinshi/{str(doujinshi.id)}/thumbnail"}

def get_doujinshi_list(engine, random_num) -> dict:
    doujinshi = []
    with Session(engine) as session:
        results = session.exec(select(Doujinshi))
        for result in results:
            doujinshi.append(get_metadata(result))
        if random_num != None: # random
            return random.sample(doujinshi, min(len(doujinshi), random_num))
        return doujinshi

def get_doujinshi_by_id(engine, id: str) -> dict:
    with Session(engine) as session:
        try:
            uid = uuid.UUID(id)
        except:
            return {}
        result = session.exec(select(Doujinshi).where(Doujinshi.id == uid)).first()
        if result == None:
            return {}
        return get_metadata(result)

def delete_metadata(engine, id: str) -> dict:
    with Session(engine) as session:
        try:
            uid = uuid.UUID(id)
        except:
            return False
        result = session.exec(select(Doujinshi).where(Doujinshi.id == uid)).first()
        if result == None:
            return False
        session.delete(result)
        session.commit()
        return True

def get_thumb_by_id(engine, id: str):
    with Session(engine) as session:
        try:
            uid = uuid.UUID(id)
        except:
            return None
        result = session.exec(select(Doujinshi).where(Doujinshi.id == uid)).first()
        if result == None:
            return None
        thumb_path = f".data/thumb/{str(uid)}.jpg"
        if not os.path.exists(thumb_path):
            return "cover/nothumb.png"
        return thumb_path

def search_doujinshi(engine, parameter) -> dict:
    doujinshi = []
    with Session(engine) as session:
        results = session.exec(select(Doujinshi).where(Doujinshi.title.like(f"%{parameter.query}%")))
        for result in results: # apply tag filter
            if len(parameter.tag) != 0:
                r_tags = result.tags.split("|")
                try:
                    r_tags.remove("")
                except:
                    pass
                skip = False
                for i in parameter.tag:
                    if not i in r_tags:
                        skip = True
                        break
                if skip:
                    continue
            if len(parameter.group) != 0: # apply group filter
                r_groups = result.groups.split("|")
                try:
                    r_groups.remove("")
                except:
                    pass
                if not parameter.group in r_groups:
                    continue
            if len(parameter.source) != 0: # apply source filter
                if parameter.source != result.source:
                    continue
            doujinshi.append(get_metadata(result))
        return doujinshi

def set_metadata(engine, id: str, metadata) -> bool:
    with Session(engine) as session:
        try:
            uid = uuid.UUID(id)
        except:
            return False
        result = session.exec(select(Doujinshi).where(Doujinshi.id == uid)).first()
        if result == None:
            return False
        result.title = metadata.title
        result.tags = "|".join(metadata.tag)
        session.add(result)
        session.commit()
        logging.info(f"set the metadata of doujinshi {id}")
        return True

def get_group_list(engine) -> list[str]:
    with Session(engine) as session:
        group_list = []
        results = session.exec(select(Group))
        for result in results:
            group_list.append({"id": str(result.id), "name": result.name})
        return group_list

def get_doujinshi_by_group(engine, id: str) -> dict:
    with Session(engine) as session:
        try:
            uid = uuid.UUID(id)
        except:
            return {}
        result = session.exec(select(Group).where(Group.id == uid)).first()
        if result == None:
            return {}
        results = session.exec(select(Doujinshi).where(Doujinshi.groups.like(f"%{str(uid)}%")))
        items = []
        for r in results:
            items.append(get_metadata(r)) # get metadata
        return {"name": result.name, "doujinshis": items}

def rename_group_by_id(engine, id: str, name: str) -> int:
    with Session(engine) as session:
        try:
            uid = uuid.UUID(id)
        except:
            return -1
        result = session.exec(select(Group).where(Group.id == uid)).first()
        if result == None:
            return -1
        if session.exec(select(Group).where(Group.name == name)).first() != None:
            return 0 # already exist the same name
        result.name = name
        session.add(result)
        logging.info(f"rename group {result.name} to {name}")
        session.commit()
        return 1

def delete_group_by_id(engine, id: str) -> bool:
    with Session(engine) as session:
        # delete group
        try:
            uid = uuid.UUID(id)
        except:
            return False
        result = session.exec(select(Group).where(Group.id == uid)).first()
        if result == None:
            return False
        session.delete(result)
        logging.info(f"delete {result.name} from group table")
        # change group field of doujinshi
        uid_str = str(uid)
        results = session.exec(select(Doujinshi).where(Doujinshi.groups.like(f"%{uid_str}%")))
        for r in results:
            group_list = r.groups.split("|")
            if uid_str in group_list:
                group_list.remove(uid_str)
                r.groups = "|".join(group_list)
                session.add(r)
        logging.info(f"delete {result.name} from groups field of doujinshi")
        session.commit()
        return True