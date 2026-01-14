# 用于运行爬虫、API 服务和监控脚本的 Docker 镜像
FROM python:3.11-slim

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    chromium \
    chromium-driver \
    fonts-wqy-zenhei \
    cron \
    curl \
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

# 复制所有脚本
COPY . /app/

# 创建必要目录
RUN mkdir -p /app/logs /app/storage /app/info /app/prompts

# 设置 cron 权限
RUN chmod 644 /etc/crontab

# 暴露 API 端口
EXPOSE 3003

# 默认命令：运行 API 服务器
CMD ["python3", "api_server.py"]
