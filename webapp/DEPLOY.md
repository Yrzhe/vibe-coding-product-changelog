# 部署说明

## 目录结构

```
竞品迭代沉淀/
├── storage/          # 产品数据 JSON 文件
├── info/             # 标签定义 JSON 文件
└── webapp/           # Web 应用
    ├── Dockerfile
    ├── docker-compose.yml
    └── ...
```

## 构建镜像

```bash
cd webapp

# 方式 1: 使用 docker-compose 构建
docker-compose build

# 方式 2: 单独构建镜像
docker build -t product-changelog-viewer:latest .
```

## 运行服务

```bash
# 使用 docker-compose 启动（推荐）
docker-compose up -d

# 或者单独运行
docker run -d \
  --name changelog-viewer \
  -p 8080:80 \
  -v $(pwd)/../storage:/usr/share/nginx/html/data/storage:ro \
  -v $(pwd)/../info:/usr/share/nginx/html/data/info:ro \
  product-changelog-viewer:latest
```

访问 http://localhost:8080

## 数据更新

数据目录（storage/ 和 info/）通过 volume 挂载到容器中，更新数据文件后会立即生效，无需重启容器。

### 定时更新数据（crontab 示例）

如果你有数据抓取脚本 `update-data.sh`，可以设置 crontab 每天运行：

```bash
# 编辑 crontab
crontab -e

# 添加定时任务（每天凌晨 2 点更新数据）
0 2 * * * /path/to/update-data.sh >> /var/log/changelog-update.log 2>&1
```

## 服务器部署

### 1. 上传文件到服务器

将整个 `竞品迭代沉淀` 目录上传到服务器，或只上传必要文件：

```bash
scp -r webapp/ user@server:/path/to/app/
scp -r storage/ user@server:/path/to/app/
scp -r info/ user@server:/path/to/app/
```

### 2. 在服务器上构建并运行

```bash
ssh user@server
cd /path/to/app/webapp
docker-compose up -d --build
```

### 3. 配置反向代理（可选）

如果使用 Nginx 作为反向代理：

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## 常用命令

```bash
# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down

# 重启服务
docker-compose restart

# 重新构建并启动
docker-compose up -d --build
```
