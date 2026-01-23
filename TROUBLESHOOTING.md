# 常见问题与解决方案

## 1. Scheduler 容器不断重启 - crond not found

**现象**：
```
docker logs changelog-scheduler
/bin/sh: 6: crond: not found
```
容器状态显示 `Restarting (127)`

**原因**：
Docker 镜像基于 Debian (`python:3.11-slim`)，但配置文件使用的是 Alpine Linux 的 cron 命令 `crond`。Debian 系统的 cron 守护进程命令是 `cron`，不是 `crond`。

**解决方案**：
使用正确的命令创建容器：
```bash
docker run -d \
  --name changelog-scheduler \
  --restart unless-stopped \
  -v $(pwd)/storage:/app/storage \
  -v $(pwd)/info:/app/info \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/script/prompts:/app/prompts \
  -e TZ=Asia/Shanghai \
  -e PYTHONUNBUFFERED=1 \
  changelog-scheduler:latest \
  /bin/bash -c 'echo "Setting up cron job..." && echo "0 9 * * * cd /app && python3 monitor.py >> /app/logs/cron.log 2>&1" > /etc/cron.d/monitor-cron && chmod 0644 /etc/cron.d/monitor-cron && crontab /etc/cron.d/monitor-cron && echo "Cron scheduled: daily at 09:00 (Asia/Shanghai)" && echo "Starting cron daemon..." && cron -f'
```

---

## 2. docker-compose 报错 KeyError: 'ContainerConfig'

**现象**：
```
KeyError: 'ContainerConfig'
ERROR: for scheduler  'ContainerConfig'
```

**原因**：
VPS 上的 docker-compose 版本过旧（1.29.2），与新版 Docker 不兼容。

**解决方案**：
不使用 docker-compose，直接用 docker 命令操作：
```bash
# 先删除旧容器
docker rm -f <container_name>

# 用 docker run 创建新容器（参考下面的完整命令）
```

---

## 3. 脚本执行超时 (>600秒)

**现象**：
Admin 页面手动运行增量更新时显示"脚本执行超时"

**原因**：
爬取所有竞品产品需要较长时间（每个产品 1-3 分钟，总共 8 个产品），默认 10 分钟超时不够用。

**解决方案**：
已将 `api_server.py` 中的超时时间从 600 秒增加到 1800 秒（30 分钟）。

---

## 4. ⚠️ 直接运行爬虫会覆盖已有标签

**现象**：
运行 `docker exec -it changelog-api python3 crawl/lovable.py` 后，所有已打的标签丢失。

**原因**：
爬虫脚本 (`crawl/*.py`) 直接将数据保存到 JSON 文件，**不会保留已有的标签**。
只有通过 `monitor.py` 运行才会合并保留标签。

**正确做法**：
- ✅ 使用 Admin 页面的"增量更新"按钮
- ✅ 运行 `python3 monitor.py`
- ❌ **不要**直接运行 `python3 crawl/xxx.py`

**如果标签被覆盖了**：
重新运行打标脚本：
```bash
docker exec -it changelog-api python3 llm_tagger.py --file <product>.json
```

---

## 5. 容器管理命令参考

### 查看所有相关容器状态
```bash
docker ps | grep changelog
```

### 查看容器日志
```bash
docker logs <container_name> --tail 50
```

### 创建 API 容器
```bash
docker run -d \
  --name changelog-api \
  --restart unless-stopped \
  -p 3003:3003 \
  -v $(pwd)/storage:/app/storage \
  -v $(pwd)/info:/app/info \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/script/prompts:/app/prompts \
  -e TZ=Asia/Shanghai \
  -e PYTHONUNBUFFERED=1 \
  changelog-api:latest \
  python3 api_server.py
```

### 创建 Scheduler 容器
```bash
docker run -d \
  --name changelog-scheduler \
  --restart unless-stopped \
  -v $(pwd)/storage:/app/storage \
  -v $(pwd)/info:/app/info \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/script/prompts:/app/prompts \
  -e TZ=Asia/Shanghai \
  -e PYTHONUNBUFFERED=1 \
  changelog-scheduler:latest \
  /bin/bash -c 'echo "Setting up cron job..." && echo "0 9 * * * cd /app && python3 monitor.py >> /app/logs/cron.log 2>&1" > /etc/cron.d/monitor-cron && chmod 0644 /etc/cron.d/monitor-cron && crontab /etc/cron.d/monitor-cron && echo "Cron scheduled: daily at 09:00 (Asia/Shanghai)" && echo "Starting cron daemon..." && cron -f'
```

### 删除容器
```bash
docker rm -f <container_name>
```

### 进入容器执行命令
```bash
docker exec -it changelog-api python3 llm_tagger.py --file lovable.json
```

---

## 6. 定时任务说明

- **运行时间**：每天早上 9:00（北京时间 Asia/Shanghai）
- **运行内容**：`monitor.py` 会依次爬取所有竞品，合并数据保留标签，为新内容打标，如果有新功能则自动生成 AI 总结
- **日志位置**：`logs/cron.log`

### 验证定时任务是否正确配置
```bash
docker exec changelog-scheduler crontab -l
# 应显示: 0 9 * * * cd /app && python3 monitor.py >> /app/logs/cron.log 2>&1
```
