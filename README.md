# DoujinshiPy

多合一本子库

TODO:
* 支持ehentai，nhentai等获取tag，cover
* 支持ehentai，nhentai等源
* 支持其他云储存

## 安装

**需要安装unrar和memcached**

```shell
python install.py
```

## Onedrive

个人版appfolder，仅支持zip文件

重定向链接：http://localhost:5000/getAToken

```
"name": {"type": "onedrive", config: {"id": "", "secret": "", "proxy": "", "path": ""}}
```

## Local

支持zip、7z、rar文件

```
"name": {"type": "local", config: {"path": ""}}
```

## Wnacg

```
"name": {"type": "wnacg", config: {}}
```
