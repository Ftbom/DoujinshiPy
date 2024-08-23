from pathlib import Path
from lib.database import SourceType

class Source:
    TYPE = SourceType.local

    def __init__(self, config) -> None:
        self.__path = Path(config["path"])

    def get_doujinshi(self, path = None) -> list[tuple[str]]:
        doujinshi = []
        if path == None:
            path = self.__path
        if not path.exists():
            raise FileNotFoundError(f"the folder {self.__path} does not exist")
        for child in path.iterdir():
            if child.is_dir():
                doujinshi.extend(self.get_doujinshi(child))
            else:
                if child.suffix in [".zip", ".ZIP", ".7z", ".7Z", ".rar", ".RAR"]:
                    doujinshi.append((child.stem, child.relative_to(self.__path).as_posix())) # (file name, relative file path)
        return doujinshi
    
    def get_file(self, identifier: str) -> str:
        return self.__path.joinpath(identifier).as_posix()