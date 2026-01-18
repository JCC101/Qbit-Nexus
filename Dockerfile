# 使用官方轻量级 Python 镜像
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 禁用 pip 缓存并安装依赖
# 只需要 Flask (Web框架) 和 qbittorrent-api (API交互库)
RUN pip install --no-cache-dir flask qbittorrent-api

# 将我们的 Python 主程序复制进去
COPY app.py .

# 设置环境变量，告诉程序数据存放在 /data 目录
ENV DATA_DIR=/data

# 暴露容器内部端口 (映射端口在 compose 中配置)
EXPOSE 5000

# 启动命令
CMD ["python", "app.py"]