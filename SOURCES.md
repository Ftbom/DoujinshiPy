# 源配置

源配置在`.data/config.json`中更改

## onedrive

Onedrive云盘

需要在Azure中注册应用，重定向链接为：http://localhost:5000/getAToken

```
<自定义显示的名称>: {"type": "onedrive", "config": {"id": <应用ID>, "secret": <应用Secret>,
        "business": <是否是Onedrive Business>, "appfolder": <是否仅访问个人版Appfolder文件夹>,
        "proxy": <代理链接>, "path": <Onedrive内doujinshi文件夹路径>}}
```
>business为true会忽略appfolder设置

## pcloud

Pcloud云盘

```
<自定义显示的名称>: {"type": "pcloud", "config": {"username": <用户名>, "passwd": <密码>,
        "proxy": <代理链接>, "path": <Pcloud内doujinshi文件夹路径>}}
```

## local

本地文件

```
<自定义显示的名称>: {"type": "local", "config": {"path": <本地doujinshi文件夹路径>}}
```

## wnacg

[绅士漫画](https://wnacg.com)

```
<自定义显示的名称>: {"type": "wnacg", "config": {"proxy": <代理链接>}}
```

## hitomi

[Hitomi](https://hitomi.la)

```
<自定义显示的名称>: {"type": "hitomi", "config": {"proxy": <代理链接>, "webp": <是否获取webp图片，否则为avif图片>}}
```

## ehentai

[E-Hentai](https://e-hentai.org/)
[EXHentai](https://exhentai.org/)

### 不访问exhentai的内容

不需设置用户信息和cookies：

```
<自定义显示的名称>: {"type": "ehentai", "config": {"proxy": <代理链接>, "exhentai": false}}
```

### 访问exhentai内容

若为欧美IP且IP纯净，可直接设置用户名和密码。
>设置用户名后会忽略cookies设置

```
<自定义显示的名称>: {"type": "ehentai", "config": {"proxy": <代理链接>, "exhentai": true,
          "user": {"username": <用户名>, "passwd": <密码>}}}
```

若有欧美IP但IP不纯净，需要设置cookies，并每年手动更新cookies一次。

```
<自定义显示的名称>: {"type": "ehentai", config: {"proxy": <代理链接>, "exhentai": true,
          "cookies": {"ipb_member_id": <cookies值>, "ipb_pass_hash": <cookies值>}}}
```

若没有欧美IP，cookies必须包括igneous（不可设为mystery），且应每一个月手动更新一次igneous

```
<自定义显示的名称>: {"type": "ehentai", config: {"proxy": "", "exhentai": true,
          "cookies": {"igneous": <cookies值>, "ipb_member_id": <cookies值>, "ipb_pass_hash": <cookies值>}}}
```

## pornhunter

Hunter类图片站，例如：
* https://www.joymiihub.com/
* https://www.ftvhunter.com/
* https://www.femjoyhunter.com/
* https://www.elitebabes.com/
* https://www.metarthunter.com/
* https://pmatehunter.com/
* https://www.xarthunter.com

```
<自定义显示的名称>: {"type": "pornhunter", config: {"proxy": ""}}
```

## webdav

WEBDAV文件

需要用户名登陆：

```
<自定义显示的名称>: {"type": "webdav", "config": {"username": <用户名>, "passwd": <密码>,
        "proxy": <代理链接>, "url": <webdav链接>}}
```

无需登陆：

```
<自定义显示的名称>: {"type": "webdav", "config": {"proxy": <代理链接>, "url": <webdav链接>}}
```

## urlcollection

WEB图片集合

```
<自定义显示的名称>: {"type": "urlcollection", "config": {}}
```

添加新项的格式：`<集合名称>#<图片链接(以$分隔)>`

## crypt

需要进行rclone crypt解密的云盘

```
<自定义显示的名称>: {"type": "crypt", "config": {"passwd": <crypt passwd>, "passwd2": <crypt passwd2>,
        "passwd_obscured": <passwd是否经过混淆>, "name_encoding": <crypt文件名加密编码，默认base32>,
        "name_obfuscate": <crypt文件名加密standard或obfuscate>, "redis_db": <redis数据库编号，默认0>,
        "source": {"type": <云盘类型>, "config": <云盘配置>}}}
```