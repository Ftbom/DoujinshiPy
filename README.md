# DoujinshiPy

## 运行

**需要先安装unrar和redis**

```shell
python app.py
```

## 支持的类型

* 本地文件
  >支持zip、rar和7z
* 云盘文件
  >支持zip
* 来自网站的内容

## 使用

* API参考
  >`http://127.0.0.1:9000/docs`或`http://127.0.0.1:9000/redoc`
* 简单WEB界面
  >`http://127.0.0.1:9000/web`
* [tachiyomi插件](https://github.com/Ftbom/tachiyomi_doujinshione_code)

## 功能说明

### Tag翻译

* 数据来源：[EhTagTranslation](https://github.com/EhTagTranslation/Database/releases)
* 当tag形式为`tag_type:tag_value`时，只翻译tag_value部分

### 搜索

* 搜索关键词匹配tag或title
* 关键词格式`query1$,query2$,query3`
* 启用tag翻译后，关键词也匹配翻译后的tag

### 页码

* 页码从1开始，为正数时返回正序结果，负数时返回倒序结果
* 页码为0时，返回所有结果

## doujinshi来源

[Sources](SOURCES.md)

## 开发

[Development](DEVELOPMENT.md)
