import os
from lib.utils import Doujinshi, SourceType

def get_tag(proxy, doujinshi: Doujinshi, url) -> list[str]:
    if not doujinshi.type == SourceType.local:
        return []
    path = doujinshi.identifier
    dir_str1 = os.path.dirname(path)
    folder_name1 = os.path.basename(dir_str1)
    if folder_name1 == "":
        return []
    dir_str2 = os.path.dirname(dir_str1)
    folder_name2 = os.path.basename(dir_str2)
    if folder_name2 == "":
        return [f"artist:{folder_name1}"]
    return [f"other:{folder_name2}", f"artist:{folder_name1}"]