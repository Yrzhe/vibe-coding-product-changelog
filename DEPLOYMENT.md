# 部署指南

## 快速部署

```bash
# 1. 克隆仓库
git clone https://github.com/YOUR_USERNAME/vibe-coding-product-changelog.git
cd vibe-coding-product-changelog

# 2. 配置 LLM API（用于自动打标）
cp script/prompts/llm_config.example.json script/prompts/llm_config.json
# 编辑 llm_config.json 填入 API key

# 3. 构建并启动所有服务
docker-compose up -d

# 4. 访问
open http://localhost:8080
```

**就这么简单！** 爬虫会自动每天上午 10 点（北京时间）运行。

## 更新代码

当仓库有更新时：

```bash
cd vibe-coding-product-changelog
git pull
docker-compose up -d --build
```

## 目录结构

```
vibe-coding-product-changelog/
├── docker-compose.yml    # Docker 配置
├── storage/              # 产品数据 JSON 文件
├── info/                 # 标签定义和配置
├── logs/                 # 爬虫日志（自动创建）
├── webapp/               # Web 前端应用
└── script/               # 爬虫和监控脚本（内置定时任务）
```

## 服务说明

| 服务 | 说明 | 端口 |
|------|------|------|
| web | 前端网页 | 8080 |
| crawler | 爬虫服务（每天 10:00 自动运行） | - |

## 常用命令

```bash
# 查看服务状态
docker-compose ps

# 查看 Web 日志
docker-compose logs -f web

# 查看爬虫日志
docker-compose logs -f crawler
cat logs/crawler.log

# 手动触发爬虫
docker-compose exec crawler python /app/script/monitor.py --auto

# 只爬取指定产品
docker-compose exec crawler python /app/script/monitor.py --product v0

# 重启所有服务
docker-compose restart

# 停止所有服务
docker-compose down

# 重新构建并启动
docker-compose up -d --build
```

## 配置反向代理（可选）

Nginx 配置示例:

```nginx
server {
    listen 80;
    server_name changelog.example.com;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## 数据说明

- `storage/` 和 `info/` 通过 volume 挂载，数据更新后立即生效
- 爬虫使用增量模式，保留已有的 tags 标注
- 每周自动执行一次全量同步检查
- 日志保存在 `logs/crawler.log`

## 故障排查

### 爬虫没有运行

```bash
# 检查 crawler 容器是否在运行
docker-compose ps

# 查看 cron 是否正常
docker-compose exec crawler crontab -l

# 查看日志
cat logs/crawler.log
```

### Web 页面数据不更新

1. 确认数据文件已更新: `ls -la storage/`
2. 清除浏览器缓存
3. 检查爬虫日志是否有错误
