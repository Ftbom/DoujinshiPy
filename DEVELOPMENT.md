# 开发指南

## doujinshi源插件

>在source文件夹下，`source/info.json`中为插件信息

### 云盘文件

```python
class Source:
    TYPE = SourceType.cloud
    SLEEP = 0.1 # 连续获取文件时的停顿时间，防止触发限制

    # @config 从配置文件中读取的json对象
    def __init__(self, config) -> None:
        pass
    
    # 返回值 (文件名,文件ID)的列表
    def get_doujinshi(self) -> list[tuple[str]]:
        pass
    
    # @file_id 文件ID
    # 返回值 {"url": <文件下载链接>, "suffix_range": <链接是否支持负偏移>, 
    #        "headers": {<下载文件的headers>}, "proxy": {<下载文件的代理设置>}}
    def get_file(self, file_id: str) -> dict:
        pass
```

### 来自网站的内容

#### 可一次获取所有图片链接

```python
class Source:
  TYPE = SourceType.web
  SLEEP = 0.5 # 连续获取图片时的停顿时间，防止触发限制

  def __init__(self, config) -> None:
    pass

  # @id doujinshi的id，注意要处理传入id为链接的情况
  # 返回值 {"id": <用于获取图片的ID>, "title": <名称>, "pagecount": <总页数>,
  #         "tags": [<Tag>], "cover": {"url": <封面链接>, "headers": {<获取封面的headers>}}}
  def get_metadata(self, id: str) -> dict:
    pass

  # @id id
  # 返回值 {"urls": [<图片链接>], "headers": {<获取图片的headers>}}
  def get_pages(self, id: str) -> dict:
    return {"urls": [], "headers": {}}
```

#### 需要逐次获取图片链接

```python
class Source:
  TYPE = SourceType.web
  SLEEP = 0.5 # 连续获取图片时的停顿时间，防止触发限制

  def __init__(self, config) -> None:
    pass

  # @id doujinshi的id，注意要处理传入id为链接的情况
  # 返回值 {"id": <用于获取图片的ID>, "title": <名称>, "pagecount": <总页数>,
  #         "tags": [<Tag>], "cover": {"url": <封面链接>, "headers": {<获取封面的headers>}}}
  def get_metadata(self, id: str) -> dict:
    pass

  # 弃用，需返回[]或{}
  def get_pages(self, id: str) -> dict:
    pass
  
  # @id id
  # @page 第page页（从0开始）
  # 返回值 {<页码>: <包含对应页码图片的页面链接>}（可同时返回多个页码的结果）
  def get_page_urls(self, id: str, page: int) -> dict:
    pass

  # @ url 页面链接
  # 返回值 {"url": <从页面链接获取的图片链接>, "headers": {<获取图片的headers>}}
  def get_img_url(self, url: str) -> dict:
    pass
```

#### 补充

若需要对doujinshi图片进行bytes处理，需要在类的方法内添加：
>不包括封面

```python
# @img_bytes 原始图片的bytes
# 返回值 处理后的bytes
def img_processor(self, img_bytes: bytes) -> bytes:
  pass
```

## 获取封面的插件

>在cover文件夹下，`cover/info.json`中为插件信息

```python
# @source doujinshi对应的源对象（一般用不上）
# @proxy 代理设置
# @doujinshi doujinshi数据
# @url 用于辅助获取封面的信息
# 返回值 封面bytes
def get_cover(source, proxy, doujinshi: Doujinshi, url) -> bytes:
    if url == None:
        return b''
    return b''
```

## 获取tag的插件

>在tag文件夹下，`tag/info.json`中为插件信息

```python
# @source doujinshi对应的源对象（一般用不上）
# @proxy 代理设置
# @doujinshi doujinshi数据
# @url 用于辅助获取封面的信息
# 返回值 tag列表
def get_tag(source, proxy, doujinshi: Doujinshi, url) -> list[str]:
    if url == None:
        return []
    return []
```