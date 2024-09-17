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
    id: uuid.UUID = Field(default_factory = uuid.uuid4, primary_key = True) # 自动生成id
    title: str
    pagecount: Union[int, None] = None
    tags: str = ''
    groups: str = ''
    identifier: str
    type: SourceType = SourceType.local
    source: str

class Group(SQLModel, table = True):
    id: uuid.UUID = Field(default_factory = uuid.uuid4, primary_key = True) # 自动生成id
    name: str

def get_groups(session: Session) -> dict:
    group_list = {}
    group_data = session.exec(select(Group))
    for g in group_data:
        group_list[str(g.id)] = g.name
    return group_list

def translate_tags(tags, tag_database):
    new_tags = []
    for tag in tags:
        tag_parts = tag.split(":")
        if len(tag_parts) == 1:
            new_tags.append(tag)
        else:
            tag_type = tag_parts[0].strip()
            tag_value = tag_parts[1].strip()
            if tag_type in tag_database:
                if tag_value in tag_database[tag_type]:
                    new_tags.append(f"{tag_type}:{tag_database[tag_type][tag_value]}")
                else:
                    new_tags.append(tag)
            else:
                new_tags.append(tag)
    return new_tags

def get_metadata(doujinshi: Doujinshi, group_list: dict, tag_database: dict = None) -> dict:
    tags = doujinshi.tags.split("|")
    tags = [item for item in tags if item != ""]
    if not tag_database == None:
        translated_tags = translate_tags(tags, tag_database)
    else:
        translated_tags = None
    # 获取group
    groups = []
    group_ids = doujinshi.groups.split("|")
    group_ids = [item for item in group_ids if item != ""]
    for gid in group_ids:
        groups.append(group_list[gid])
    # 获取封面
    thumb_path = f".data/thumb/{str(doujinshi.id)}.jpg"
    if not os.path.exists(thumb_path):
        cover_url = "/doujinshi/nothumb/thumbnail"
    else:
        cover_url = f"/doujinshi/{str(doujinshi.id)}/thumbnail"
    if translated_tags == None:
        return {"id": str(doujinshi.id), "title": doujinshi.title, "source": doujinshi.source,
                "groups": groups, "tags": tags, "cover": cover_url}
    return {"id": str(doujinshi.id), "title": doujinshi.title, "source": doujinshi.source,
                "groups": groups, "tags": tags, "translated_tags": translated_tags, "cover": cover_url}

def get_doujinshi_list(engine, random_num, tag_database) -> dict:
    doujinshi = []
    with Session(engine) as session:
        group_list = get_groups(session)
        results = session.exec(select(Doujinshi))
        for result in results:
            doujinshi.append(get_metadata(result, group_list, tag_database))
        if random_num != None: # 随机
            return random.sample(doujinshi, min(len(doujinshi), random_num))
        return doujinshi

def get_doujinshi_by_id(engine, id: str, tag_database) -> dict:
    with Session(engine) as session:
        try:
            uid = uuid.UUID(id)
        except:
            return {}
        result = session.exec(select(Doujinshi).where(Doujinshi.id == uid)).first()
        if result == None:
            return {}
        group_list = get_groups(session)
        return get_metadata(result, group_list, tag_database)

def delete_metadata(engine, id: str) -> dict:
    with Session(engine) as session:
        try:
            uid = uuid.UUID(id)
        except:
            return False
        result = session.exec(select(Doujinshi).where(Doujinshi.id == uid)).first()
        if result == None:
            return False
        try:
            os.remove(f".data/thumb/{str(result.id)}.jpg")
        except:
            pass
        session.delete(result)
        session.commit()
        return True

def search_doujinshi(engine, parameters, tag_database) -> dict:
    doujinshi = []
    with Session(engine) as session:
        group_list = get_groups(session)
        results = session.exec(select(Doujinshi).where(Doujinshi.title.like(f"%{parameters[0]}%")))
        for result in results: # 应用tag筛选
            if len(parameters[1]) != 0:
                r_tags = result.tags.split("|")
                r_tags = [item for item in r_tags if item != ""]
                skip = False
                for i in parameters[1]:
                    if not i in r_tags:
                        skip = True
                        break
                if skip:
                    continue
            if len(parameters[2]) != 0: # 应用group筛选
                r_groups = result.groups.split("|")
                r_groups = [item for item in r_groups if item != ""]
                if not parameters[2] in r_groups:
                    continue
            if len(parameters[3]) != 0: # 应用源筛选
                if parameters[3] != result.source:
                    continue
            doujinshi.append(get_metadata(result, group_list, tag_database))
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
        group_list = get_groups(session)
        if not str(uid) in group_list:
            return {}
        results = session.exec(select(Doujinshi).where(Doujinshi.groups.like(f"%{str(uid)}%")))
        items = []
        for r in results:
            items.append(get_metadata(r, group_list)) # 获取metadata
        return {"name": group_list[str(uid)], "doujinshis": items}

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
            return 0 # 同名group已存在
        result.name = name
        session.add(result)
        logging.info(f"rename group {result.name} to {name}")
        session.commit()
        return 1

def delete_group_by_id(engine, id: str) -> bool:
    with Session(engine) as session:
        # 删除group
        try:
            uid = uuid.UUID(id)
        except:
            return False
        result = session.exec(select(Group).where(Group.id == uid)).first()
        if result == None:
            return False
        session.delete(result)
        logging.info(f"delete {result.name} from group table")
        # 更改doujinshi组设置
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