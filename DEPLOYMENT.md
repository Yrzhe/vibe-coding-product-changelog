# 部署指南

## 目录结构

```
竞品迭代沉淀/
├── docker-compose.yml    # 主配置文件
├── run-crawler.sh        # 爬虫运行脚本
├── storage/              # 产品数据 JSON 文件
├── info/                 # 标签定义和配置
│   ├── admin_config.json # Admin 密码配置
│   ├── competitor.json   # 竞品列表
│   ├── tag.json          # 标签体系
│   └── summary.json      # AI 总结
├── logs/                 # 日志目录（自动创建）
├── webapp/               # Web 前端应用
│   ├── Dockerfile
│   └── ...
└── script/               # 爬虫和监控脚本
    ├── Dockerfile
    ├── requirements.txt
    ├── api_server.py     # API 服务（支持 Admin）
    ├── monitor.py        # 增量更新脚本
    ├── llm_tagger.py     # LLM 打标脚本
    ├── ai_summary.py     # AI 总结脚本
    ├── parse_changelog.py # YouWare changelog 解析
    ├── prompts/          # LLM 配置
    │   └── llm_config.json
    └── crawl/            # 各产品爬虫
```

## 功能说明

### 服务架构

| 服务 | 端口 | 功能 |
|------|------|------|
| `web` | 8080 | 前端页面 + Nginx 反代 API |
| `api` | 3003 | API 服务（Admin、触发脚本） |
| `scheduler` | - | 定时任务（每天 9:00 自动爬取） |

### 自动化功能

1. **定时监控**：scheduler 服务每天 9:00 自动运行增量更新
2. **手动触发**：Admin 页面点击按钮触发增量更新或 AI 总结
3. **YouWare 更新**：Admin 页面编辑保存后自动解析 + 打标

## 快速开始

### 1. 配置 LLM API

在部署前，需要配置 LLM API 密钥：

```bash
# 复制示例配置
cp script/prompts/llm_config.example.json script/prompts/llm_config.json

# 编辑配置，填入你的 API Key
vim script/prompts/llm_config.json
```

### 2. 配置 Admin 密码

```bash
# 编辑 Admin 密码
vim info/admin_config.json
```

### 3. 构建镜像

```bash
cd /path/to/竞品迭代沉淀

# 构建所有镜像
docker-compose build
```

### 4. 启动所有服务

```bash
# 启动所有服务（包括定时任务）
docker-compose up -d

# 查看状态
docker-compose ps

# 查看日志
docker-compose logs -f
```

访问 http://localhost:8080

### 3. 手动运行爬虫

```bash
# 使用脚本运行（推荐）
chmod +x run-crawler.sh
./run-crawler.sh

# 或直接使用 docker-compose
docker-compose --profile crawler run --rm crawler

# 只爬取指定产品
docker-compose --profile crawler run --rm crawler python /app/script/monitor.py --product v0
```

## 定时任务配置

### Linux/Mac (crontab)

```bash
# 编辑 crontab
crontab -e

# 添加定时任务（每天凌晨 2 点运行）
0 2 * * * /path/to/竞品迭代沉淀/run-crawler.sh >> /var/log/changelog-crawler.log 2>&1

# 或每 6 小时运行一次
0 */6 * * * /path/to/竞品迭代沉淀/run-crawler.sh >> /var/log/changelog-crawler.log 2>&1
```

### 使用 systemd timer（更可靠）

创建 `/etc/systemd/system/changelog-crawler.service`:

```ini
[Unit]
Description=Changelog Crawler Service
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
WorkingDirectory=/path/to/竞品迭代沉淀
ExecStart=/path/to/竞品迭代沉淀/run-crawler.sh
User=your-user

[Install]
WantedBy=multi-user.target
```

创建 `/etc/systemd/system/changelog-crawler.timer`:

```ini
[Unit]
Description=Run changelog crawler daily

[Timer]
OnCalendar=*-*-* 02:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

启用定时器:

```bash
sudo systemctl daemon-reload
sudo systemctl enable changelog-crawler.timer
sudo systemctl start changelog-crawler.timer

# 查看状态
systemctl list-timers | grep changelog
```

## 服务器部署

### 1. 上传文件

```bash
# 使用 rsync 上传（推荐）
rsync -avz --exclude 'node_modules' --exclude '.git' \
    /path/to/竞品迭代沉淀/ user@server:/opt/changelog/

# 或使用 scp
scp -r 竞品迭代沉淀 user@server:/opt/changelog/
```

### 2. 在服务器上构建和启动

```bash
ssh user@server
cd /opt/changelog

# 构建镜像
docker-compose build

# 启动 Web 服务
docker-compose up -d web

# 设置定时任务
chmod +x run-crawler.sh
crontab -e
# 添加: 0 2 * * * /opt/changelog/run-crawler.sh >> /var/log/changelog-crawler.log 2>&1
```

### 3. 配置反向代理（Nginx）

```nginx
server {
    listen 80;
    server_name changelog.example.com;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

## 数据更新说明

- `storage/` 和 `info/` 目录通过 volume 挂载，数据更新后立即生效
- 爬虫使用增量模式，会保留已有的 tags 标注
- 每周自动执行一次全量同步检查
- 日志保存在 `logs/` 目录

## 常用命令

```bash
# 查看 Web 服务日志
docker-compose logs -f web

# 重启 Web 服务
docker-compose restart web

# 停止所有服务
docker-compose down

# 重新构建并启动
docker-compose up -d --build web

# 手动运行爬虫（调试模式）
docker-compose --profile crawler run --rm crawler python /app/script/monitor.py --product v0

# 清理无用镜像
docker image prune -f
```

## 故障排查

### 爬虫失败

1. 检查日志: `cat logs/crawler-$(date +%Y%m%d).log`
2. 手动运行单个产品: `./run-crawler.sh --product v0`
3. 进入容器调试:
   ```bash
   docker-compose --profile crawler run --rm crawler bash
   python /app/script/monitor.py --product v0
   ```

### Web 页面数据不更新

1. 确认数据文件已更新: `ls -la storage/`
2. 清除浏览器缓存
3. 检查 nginx 配置是否正确挂载了 volume

### Docker 构建失败

1. 检查 Dockerfile 语法
2. 确保网络连接正常（需要下载 Playwright 浏览器）
3. 清理 Docker 缓存: `docker builder prune -f`
