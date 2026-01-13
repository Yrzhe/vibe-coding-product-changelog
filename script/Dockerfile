# 爬虫和监控脚本容器（带定时任务）
FROM python:3.11-slim

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    chromium \
    chromium-driver \
    fonts-wqy-zenhei \
    cron \
    && rm -rf /var/lib/apt/lists/*

# 设置时区为北京时间
ENV TZ=Asia/Shanghai
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

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

# 创建定时任务配置（每天上午 10 点北京时间运行）
RUN echo "0 10 * * * cd /app && /usr/local/bin/python /app/script/monitor.py --auto >> /app/logs/crawler.log 2>&1" > /etc/cron.d/crawler \
    && chmod 0644 /etc/cron.d/crawler \
    && crontab /etc/cron.d/crawler \
    && touch /var/log/cron.log

WORKDIR /app

# 启动 cron 服务（前台运行）
CMD ["cron", "-f"]
