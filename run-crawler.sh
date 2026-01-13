#!/bin/bash
# 运行爬虫脚本
# 用法: ./run-crawler.sh [--product NAME]

set -e

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 日志文件
LOG_FILE="$SCRIPT_DIR/logs/crawler-$(date +%Y%m%d).log"
mkdir -p "$SCRIPT_DIR/logs"

echo "========================================" >> "$LOG_FILE"
echo "开始运行: $(date '+%Y-%m-%d %H:%M:%S')" >> "$LOG_FILE"
echo "========================================" >> "$LOG_FILE"

# 运行爬虫容器
docker-compose --profile crawler run --rm crawler python /app/script/monitor.py --auto "$@" 2>&1 | tee -a "$LOG_FILE"

echo "" >> "$LOG_FILE"
echo "完成: $(date '+%Y-%m-%d %H:%M:%S')" >> "$LOG_FILE"
echo "" >> "$LOG_FILE"
