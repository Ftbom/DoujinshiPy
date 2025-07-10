FROM python:3.11-slim

WORKDIR /app

# 安装 Redis
RUN apt-get update && apt-get install -y redis-server && apt-get clean

# 拷贝代码和依赖
COPY . .
RUN pip install --no-cache-dir -r requirements.txt

CMD redis-server --daemonize yes && python app.py