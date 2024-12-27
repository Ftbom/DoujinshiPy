# DoujinshiPy

多合一本子库

## 安装

**需要先安装unrar和redis**

```shell
python install.py
```

## 支持类型

* local
  >本地文件，支持zip、rar和7z
* cloud
  >云盘文件，仅支持zip
* web
  >网站内容

## 开发

### cover

获取封面的插件

```python
# app_state为程序信息，包括代理设置和数据库等。详细信息见api.py
def get_cover(app_state, doujinshi: Doujinshi, url) -> bytes:
  if url != None:
    # 通过url获取
    pass
  else:
    # 通过doujinshi信息获取
    pass
  return img_bytes
```
>注意对一些网站需要适当sleep，防止网站封禁IP
>

### tag

```python
# app_state为程序信息，包括代理设置和数据库等。详细信息见api.py
def get_tag(app_state, doujinshi: Doujinshi, url) -> list[str]:
  if url != None:
    # 通过url获取
    pass
  else:
    # 通过doujinshi信息获取
    pass
  return tags
```
>注意对一些网站需要适当sleep，防止网站封禁IP

### 源

若需要对图片（不包括cover）bytes进行处理，需要在类的方法内添加：

```python
def img_processor(self, img_bytes: bytes) -> bytes:
  return img
```

cloud源

```python
class Source:
  TYPE = SourceType.cloud
  SLEEP = 0.1 # 适当sleep，防止IP被封禁

  def __init__(self, config) -> None:
    pass

  def get_doujinshi(self) -> list[tuple[str]]:
    return doujinshi # [(文件名, 文件唯一ID)]
    
  def get_file(self, identifier: str) -> str:
    return {"url": "", "suffix_range": True, "headers": {}, "proxy": {}}
```

web源

可一次爬取所有图片：

```python
class Source:
  TYPE = SourceType.web
  SLEEP = 0.5

  def __init__(self, config) -> None:
    pass

  def get_metadata(self, id: str) -> dict:
    return {"id": "", "title": "", "pagecount": "", "tags": [], "cover": {"url": "", "headers": {}}}

  def get_pages(self, id: str) -> dict:
    return {"urls": [], "headers": {}}
```

需逐页爬取图片：

```python
class Source:
  TYPE = SourceType.web
  SLEEP = 1.5

  def __init__(self, config) -> None:
    pass
            
  def get_metadata(self, id: str) -> dict:
    return {"id": "", "title": "", "pagecount": "", "tags": [], "cover": {"url": "", "headers": {}}}

  def get_pages(self, ids: str) -> dict:
    # return []
    return {}
    
  def get_page_urls(self, ids: str, page: int) -> dict:
    # page从0开始
    return result # {page_num: url}(int: str)，可包含一页或多页

  def get_img_url(self, url: str) -> dict:
    return {"url": "", "headers": {}}
```

## 源配置

### onedrive

云盘

重定向链接：http://localhost:5000/getAToken

```
"name": {"type": "onedrive", config: {"id": "", "secret": "", "business": false, "appfolder": false, "proxy": "", "path": ""}}
```

### pcloud

云盘

```
"name": {"type": "pcloud", config: {"username": "", "passwd": "", "proxy": "", "path": ""}}
```

### local

本地

```
"name": {"type": "local", config: {"path": ""}}
```

### wnacg

网站

```
"name": {"type": "wnacg", config: {"proxy": ""}}
```

### hitomi

网站

```
"name": {"type": "hitomi", config: {"proxy": "", "webp": false}}
```

### ehentai

网站

若不访问exhentai的内容，不需设置用户信息和cookies。

```
"name": {"type": "ehentai", config: {"proxy": "", "exhentai": false}}
```

若访问exhentai内容，需要设置用户信息或cookies。

若为欧美IP且IP纯净，可直接设置用户名和密码。
>设置用户名后会忽略cookies设置

```
"name": {"type": "ehentai", config: {"proxy": "", "exhentai": true,
          "user": {"username": "", "passwd": ""}}}
```

若有欧美IP但IP不纯净，需要设置cookies，并每年手动更新cookies一次。

```
"name": {"type": "ehentai", config: {"proxy": "", "exhentai": true,
          "cookies": {"ipb_member_id": "", "ipb_pass_hash": ""}}}
```

若没有欧美IP，cookies必须包括igneous（不可为mystery），且应每一个月手动更新一次igneous

```
"name": {"type": "ehentai", config: {"proxy": "", "exhentai": true,
          "cookies": {"igneous": "", "ipb_member_id": "", "ipb_pass_hash": ""}}}
```
