# 用于运行爬虫和监控脚本的 Docker 镜像
FROM python:3.11-slim

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    chromium \
    chromium-driver \
    fonts-wqy-zenhei \
    cron \
    && rm -rf /var/lib/apt/lists/*

# 设置 Playwright 环境变量
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
ENV PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=0

WORKDIR /app

# 复制依赖文件并安装
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 安装 Playwright 浏览器
RUN playwright install chromium --with-deps

# 复制脚本到 /app/script/
COPY . /app/script/

# 创建日志目录
RUN mkdir -p /app/logs

# 设置工作目录
WORKDIR /app

# 默认命令：运行一次监控
CMD ["python", "/app/script/monitor.py", "--auto"]
