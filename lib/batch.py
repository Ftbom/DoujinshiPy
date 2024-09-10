import os
import uuid
import logging
from sqlmodel import Session, select
from lib.database import Doujinshi, Group

def batch_set_group(app_state, group_name: str, id_list: list[str], replace_old: bool) -> None:
    client = app_state["redis_client"]
    num = len(id_list)
    with Session(app_state["database_engine"]) as session:
        group_statement = select(Group).where(Group.name == group_name)
        group_result = session.exec(group_statement).first()
        if group_result == None: # 新的group名称，新建group
            group_result = Group(name = group_name)
            session.add(group_result)
        count = 0
        for id in id_list:
            count = count + 1
            if (type(id) != str) and (type(id) != list):
                continue
            if type(id) == list:
                if len(id) == 0:
                    continue
                id = str(id[0])
            try:
                statement = select(Doujinshi).where(Doujinshi.id == uuid.UUID(id))
                result = session.exec(statement).first()
            except:
                result = None
            if result == None:
                logging.warning(f"don't find id {id}, skip setting group")
            else:
                if replace_old: # 是否完全覆盖旧group
                    group_str = str(group_result.id)
                else:
                    group_list = result.groups.split("|")
                    try:
                        group_list.remove("")
                    except:
                        pass
                    if not str(group_result.id) in group_list:
                        group_list.append(str(group_result.id))
                    group_str = "|".join(group_list)
                result.groups = group_str
                session.add(result)
                logging.info(f"set group for {id}")
            client.set("batch_operation", f"setting group {count}/{num}")
        session.commit()
        client.set("batch_operation", "finished")

def batch_get_cover(app_state, id_list: list[str], replace_old: bool, func) -> None:
    client = app_state["redis_client"]
    num = len(id_list)
    with Session(app_state["database_engine"]) as session:
        count = 0
        for id in id_list:
            count = count + 1
            client.set("batch_operation", f"getting cover {count}/{num}")
            # 处理id，可为字符串或列表（二元）
            if (type(id) != str) and (type(id) != list):
                continue
            if (type(id) == list):
                if len(id) == 0:
                    continue
                elif len(id) == 1:
                    id = str(id[0])
                    url = None
                else:
                    url = str(id[1])
                    id = str(id[0])
            else:
                url = None
            try:
                target_id = uuid.UUID(id)
                if not replace_old:
                    if os.path.exists(f".data/thumb/{str(target_id)}.jpg"):
                        continue
                # 获取信息
                statement = select(Doujinshi).where(Doujinshi.id == target_id)
                result = session.exec(statement).first()
            except:
                result = None
            if result == None:
                logging.warning(f"don't find id {id}, skip getting cover")
            else:
                try:
                    func(app_state["sources"][result.source], app_state["settings"]["proxy"], result, url) # 获取封面的函数
                    logging.info(f"get cover {id}.jpg")
                except Exception as e:
                    logging.error(f"failed to get cover {id}.jpg, error message: {e}")
        client.set("batch_operation", "finished")

def batch_get_tag(app_state, id_list: list[str], replace_old: bool, func) -> None:
    client = app_state["redis_client"]
    num = len(id_list)
    with Session(app_state["database_engine"]) as session:
        count = 0
        for id in id_list:
            count = count + 1
            client.set("batch_operation", f"getting tag {count}/{num}")
            if (type(id) != str) and (type(id) != list):
                continue
            if (type(id) == list):
                if len(id) == 0:
                    continue
                elif len(id) == 1:
                    id = str(id[0])
                    url = None
                else:
                    url = str(id[1])
                    id = str(id[0])
            else:
                url = None
            try:
                statement = select(Doujinshi).where(Doujinshi.id == uuid.UUID(id))
                result = session.exec(statement).first()
            except:
                result = None
            if result == None:
                logging.warning(f"don't find id {id}, skip getting tag")
            else:
                try:
                    new_tags = func(app_state["sources"][result.source], app_state["settings"]["proxy"], result, url) # 获取tag的函数
                    if replace_old and new_tags != []:
                        tags = new_tags
                    else:
                        tags = result.tags.split("|")
                        try:
                            tags.remove("")
                        except:
                            pass
                        for t in new_tags:
                            if not t in tags:
                                tags.append(t)
                    result.tags = "|".join(tags)
                    session.add(result)
                    logging.info(f"get tag for {id}")
                except:
                    logging.error(f"failed to get tag for {id}")
        session.commit()
        client.set("batch_operation", "finished")
        