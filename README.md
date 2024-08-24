# DoujinshiPy

多合一本子库

## 安装

**需要安装unrar和memcached**

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

## 源配置

### onedrive

云盘

重定向链接：http://localhost:5000/getAToken

```
"name": {"type": "onedrive", config: {"id": "", "secret": "", "proxy": "", "path": ""}}
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

## wnacg

网站

```
"name": {"type": "wnacg", config: {"proxy": ""}}
```