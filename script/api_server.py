#!/usr/bin/env python3
"""
API 服务器
提供 Admin 管理、增量更新和 AI 总结的触发接口
"""

import json
import subprocess
import sys
import threading
import secrets
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse


def get_project_root():
    """
    获取项目根目录
    - 本地开发：script/api_server.py -> 返回 script 的父目录
    - Docker 环境：/app/api_server.py -> 返回 /app
    """
    script_dir = Path(__file__).parent
    # 检查是否在 Docker 中（/app 目录）
    if script_dir == Path("/app"):
        return Path("/app")
    # 本地开发环境
    return script_dir.parent


# Session 存储 (简单内存存储，重启后失效)
sessions = {}

# 任务运行状态
running_tasks = {
    "crawl": False,
    "summary": False
}


def load_admin_config():
    """加载管理员配置"""
    config_path = get_project_root() / "info" / "admin_config.json"
    if config_path.exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"password": "admin", "session_secret": "default_secret"}


def verify_session(token: str) -> bool:
    """验证 session token"""
    if not token:
        return False
    
    session = sessions.get(token)
    if not session:
        return False
    
    # 检查是否过期 (24小时)
    if datetime.now() > session.get('expires', datetime.min):
        del sessions[token]
        return False
    
    return True


def create_session() -> str:
    """创建新的 session"""
    token = secrets.token_hex(32)
    sessions[token] = {
        'created': datetime.now(),
        'expires': datetime.now() + timedelta(hours=24)
    }
    return token


def save_run_status(crawl_time=None, summary_time=None):
    """保存运行状态"""
    status_path = get_project_root() / "info" / "run_status.json"
    
    # 读取现有状态
    status = {}
    if status_path.exists():
        try:
            with open(status_path, "r") as f:
                status = json.load(f)
        except:
            pass
    
    # 更新状态
    if crawl_time:
        status["crawl_last_run"] = crawl_time
    if summary_time:
        status["summary_last_run"] = summary_time
    
    # 保存
    with open(status_path, "w") as f:
        json.dump(status, f, indent=2)


def run_script_async(script_name: str, task_type: str = None, callback=None):
    """异步运行脚本，并记录详细日志"""
    def run():
        global running_tasks
        if task_type:
            running_tasks[task_type] = True
        
        root = get_project_root()
        logs_dir = root / "logs"
        logs_dir.mkdir(exist_ok=True)
        
        # Docker 中脚本在 /app 下，本地在 script/ 下
        if root == Path("/app"):
            script_path = root / script_name
        else:
            script_path = root / "script" / script_name
        
        start_time = datetime.now()
        log_file = logs_dir / f"{task_type or 'script'}_{start_time.strftime('%Y%m%d_%H%M%S')}.log"
        
        try:
            print(f"[{start_time.isoformat()}] 开始运行: {script_name}")
            
            result = subprocess.run(
                [sys.executable, str(script_path)],
                capture_output=True,
                text=True,
                timeout=600  # 10 分钟超时
            )
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            # 写入日志文件
            with open(log_file, "w", encoding="utf-8") as f:
                f.write(f"=== 脚本执行日志 ===\n")
                f.write(f"脚本: {script_name}\n")
                f.write(f"开始时间: {start_time.isoformat()}\n")
                f.write(f"结束时间: {end_time.isoformat()}\n")
                f.write(f"耗时: {duration:.1f} 秒\n")
                f.write(f"返回码: {result.returncode}\n")
                f.write(f"\n=== STDOUT ===\n")
                f.write(result.stdout or "(无输出)")
                f.write(f"\n\n=== STDERR ===\n")
                f.write(result.stderr or "(无错误)")
            
            print(f"[{end_time.isoformat()}] 脚本完成: {script_name}, 耗时 {duration:.1f}秒, 返回码 {result.returncode}")
            
            if result.returncode != 0:
                print(f"脚本错误输出: {result.stderr[:500] if result.stderr else '(无)'}")
            
            if callback:
                callback(result.returncode == 0)
                
        except subprocess.TimeoutExpired as e:
            print(f"脚本执行超时: {script_name}")
            with open(log_file, "w", encoding="utf-8") as f:
                f.write(f"脚本执行超时 (>600秒): {script_name}\n")
            if callback:
                callback(False)
        except Exception as e:
            print(f"脚本运行失败: {script_name}, 错误: {e}")
            with open(log_file, "w", encoding="utf-8") as f:
                f.write(f"脚本运行失败: {e}\n")
            if callback:
                callback(False)
        finally:
            if task_type:
                running_tasks[task_type] = False
    
    thread = threading.Thread(target=run)
    thread.start()


def run_parse_and_tag():
    """运行解析和打标脚本"""
    root = get_project_root()
    
    # Docker 中脚本在 /app 下，本地在 script/ 下
    if root == Path("/app"):
        script_dir = root
    else:
        script_dir = root / "script"
    
    # 1. 运行解析脚本
    print("正在解析 changelog...")
    parse_script = script_dir / "parse_changelog.py"
    try:
        result = subprocess.run(
            [sys.executable, str(parse_script)],
            capture_output=True,
            text=True,
            timeout=60
        )
        print(result.stdout)
        if result.returncode != 0:
            print(f"解析失败: {result.stderr}")
            return False
    except Exception as e:
        print(f"解析脚本运行失败: {e}")
        return False
    
    # 2. 运行打标脚本
    print("正在打标...")
    tag_script = script_dir / "llm_tagger.py"
    try:
        result = subprocess.run(
            [sys.executable, str(tag_script), "--file", "youware.json"],
            capture_output=True,
            text=True,
            timeout=600
        )
        print(result.stdout)
        if result.returncode != 0:
            print(f"打标失败: {result.stderr}")
    except Exception as e:
        print(f"打标脚本运行失败: {e}")
    
    return True


class APIHandler(BaseHTTPRequestHandler):
    
    def get_auth_token(self):
        """从请求头获取认证 token"""
        auth_header = self.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            return auth_header[7:]
        return None
    
    def send_json_response(self, status_code, data):
        """发送 JSON 响应"""
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))
    
    def read_request_body(self):
        """读取请求体"""
        content_length = int(self.headers.get('Content-Length', 0))
        if content_length > 0:
            body = self.rfile.read(content_length)
            return body.decode('utf-8')
        return ''
    
    def do_GET(self):
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        
        if path == "/api/admin/changelog":
            # 获取原始 changelog 文本
            token = self.get_auth_token()
            if not verify_session(token):
                self.send_json_response(401, {"error": "未授权访问"})
                return
            
            raw_file = get_project_root() / "storage" / "youware_changelog_raw.txt"
            if raw_file.exists():
                content = raw_file.read_text(encoding='utf-8')
                self.send_json_response(200, {"content": content})
            else:
                self.send_json_response(200, {"content": ""})
        
        elif path == "/api/status":
            # 获取运行状态
            status_path = get_project_root() / "info" / "run_status.json"
            status = {}
            if status_path.exists():
                with open(status_path, 'r') as f:
                    status = json.load(f)
            
            # 添加当前运行状态
            status["crawl_running"] = running_tasks.get("crawl", False)
            status["summary_running"] = running_tasks.get("summary", False)
            status["tagging_running"] = running_tasks.get("tagging", False)
            
            self.send_json_response(200, status)
        
        elif path == "/api/admin/logs":
            # 获取最近的日志文件列表
            token = self.get_auth_token()
            if not verify_session(token):
                self.send_json_response(401, {"error": "未授权访问"})
                return
            
            logs_dir = get_project_root() / "logs"
            logs = []
            
            if logs_dir.exists():
                # 获取所有 .log 文件，按修改时间排序
                log_files = sorted(
                    logs_dir.glob("*.log"),
                    key=lambda x: x.stat().st_mtime,
                    reverse=True
                )[:10]  # 最近 10 个日志
                
                for log_file in log_files:
                    try:
                        content = log_file.read_text(encoding='utf-8')
                        logs.append({
                            'name': log_file.name,
                            'time': datetime.fromtimestamp(log_file.stat().st_mtime).isoformat(),
                            'content': content[:5000]  # 最多 5000 字符
                        })
                    except:
                        pass
            
            self.send_json_response(200, {"logs": logs})
        
        elif path == "/api/admin/others":
            # 获取所有标记为 Others 的 features
            token = self.get_auth_token()
            if not verify_session(token):
                self.send_json_response(401, {"error": "未授权访问"})
                return
            
            others_features = []
            storage_dir = get_project_root() / "storage"
            products = ['youware', 'base44', 'bolt', 'lovable', 'replit', 'rocket', 'trickle', 'v0']
            
            for product in products:
                product_file = storage_dir / f"{product}.json"
                if not product_file.exists():
                    continue
                
                with open(product_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                feature_data = next((item for item in data if item.get('name') == 'feature'), None)
                if not feature_data:
                    continue
                
                for idx, feature in enumerate(feature_data.get('features', [])):
                    tags = feature.get('tags', [])
                    # 确保 tags 是列表，不是字符串 "None"
                    if not isinstance(tags, list):
                        continue
                    for tag in tags:
                        # 确保 tag 是字典
                        if not isinstance(tag, dict):
                            continue
                        if tag.get('name') == 'Others':
                            subtags = tag.get('subtags', [])
                            others_features.append({
                                'product': product,
                                'feature_index': idx,
                                'title': feature.get('title', ''),
                                'description': feature.get('description', ''),
                                'time': feature.get('time', ''),
                                'current_subtags': [st.get('name') for st in subtags if isinstance(st, dict)]
                            })
                            break
            
            self.send_json_response(200, {"features": others_features})
        
        elif path == "/api/admin/tags":
            # 获取标签结构
            token = self.get_auth_token()
            if not verify_session(token):
                self.send_json_response(401, {"error": "未授权访问"})
                return
            
            tag_file = get_project_root() / "info" / "tag.json"
            if tag_file.exists():
                with open(tag_file, 'r', encoding='utf-8') as f:
                    tags_data = json.load(f)
                self.send_json_response(200, tags_data)
            else:
                self.send_json_response(404, {"error": "标签文件不存在"})
        
        elif path == "/api/admin/untagged":
            # 获取所有未打标的 features（tags为空数组或undefined）
            token = self.get_auth_token()
            if not verify_session(token):
                self.send_json_response(401, {"error": "未授权访问"})
                return
            
            untagged_features = []
            storage_dir = get_project_root() / "storage"
            products = ['youware', 'base44', 'bolt', 'lovable', 'replit', 'rocket', 'trickle', 'v0']
            
            for product in products:
                product_file = storage_dir / f"{product}.json"
                if not product_file.exists():
                    continue
                
                with open(product_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                feature_data = next((item for item in data if item.get('name') == 'feature'), None)
                if not feature_data:
                    continue
                
                for idx, feature in enumerate(feature_data.get('features', [])):
                    tags = feature.get('tags')
                    # 未打标: tags 不存在、为 None、为空数组
                    # 无需打标: tags == "None" (字符串)
                    is_untagged = (
                        tags is None or 
                        (isinstance(tags, list) and len(tags) == 0)
                    )
                    is_none_tag = tags == "None"
                    
                    if is_untagged:
                        untagged_features.append({
                            'product': product,
                            'feature_index': idx,
                            'title': feature.get('title', ''),
                            'description': feature.get('description', ''),
                            'time': feature.get('time', ''),
                            'status': 'untagged'  # 未打标
                        })
                    elif is_none_tag:
                        untagged_features.append({
                            'product': product,
                            'feature_index': idx,
                            'title': feature.get('title', ''),
                            'description': feature.get('description', ''),
                            'time': feature.get('time', ''),
                            'status': 'none'  # 已标记为无需打标
                        })
            
            self.send_json_response(200, {"features": untagged_features})
        
        elif path == "/api/admin/used-subtags":
            # 获取所有被使用的二级标签（用于隐藏未使用的标签）
            token = self.get_auth_token()
            if not verify_session(token):
                self.send_json_response(401, {"error": "未授权访问"})
                return
            
            used_subtags = set()
            storage_dir = get_project_root() / "storage"
            products = ['youware', 'base44', 'bolt', 'lovable', 'replit', 'rocket', 'trickle', 'v0']
            
            for product in products:
                product_file = storage_dir / f"{product}.json"
                if not product_file.exists():
                    continue
                
                with open(product_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                feature_data = next((item for item in data if item.get('name') == 'feature'), None)
                if not feature_data:
                    continue
                
                for feature in feature_data.get('features', []):
                    tags = feature.get('tags', [])
                    if not isinstance(tags, list):
                        continue
                    for tag in tags:
                        if not isinstance(tag, dict):
                            continue
                        for subtag in tag.get('subtags', []):
                            if isinstance(subtag, dict) and subtag.get('name'):
                                used_subtags.add(subtag.get('name'))
            
            self.send_json_response(200, {"used_subtags": list(used_subtags)})
        
        else:
            self.send_response(404)
            self.end_headers()
    
    def do_POST(self):
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        
        if path == "/api/admin/login":
            # 验证密码
            body = self.read_request_body()
            try:
                data = json.loads(body)
            except:
                self.send_json_response(400, {"error": "无效的 JSON"})
                return
            
            password = data.get('password', '')
            config = load_admin_config()
            
            if password == config.get('password', ''):
                token = create_session()
                self.send_json_response(200, {"token": token})
            else:
                self.send_json_response(401, {"error": "密码错误"})
        
        elif path == "/api/admin/changelog":
            # 保存 changelog 并自动解析+打标
            token = self.get_auth_token()
            if not verify_session(token):
                self.send_json_response(401, {"error": "未授权访问"})
                return
            
            body = self.read_request_body()
            try:
                data = json.loads(body)
            except:
                self.send_json_response(400, {"error": "无效的 JSON"})
                return
            
            content = data.get('content', '')
            
            # 保存原始文件
            raw_file = get_project_root() / "storage" / "youware_changelog_raw.txt"
            raw_file.write_text(content, encoding='utf-8')
            
            # 异步运行解析和打标
            def run_async():
                run_parse_and_tag()
            
            thread = threading.Thread(target=run_async)
            thread.start()
            
            self.send_json_response(200, {"status": "saved", "message": "已保存并开始解析打标"})
        
        elif path == "/api/admin/logout":
            # 登出
            token = self.get_auth_token()
            if token and token in sessions:
                del sessions[token]
            self.send_json_response(200, {"status": "logged_out"})
        
        elif path == "/api/admin/config":
            # 更新配置（如 exclude_tags）
            token = self.get_auth_token()
            if not verify_session(token):
                self.send_json_response(401, {"error": "未授权访问"})
                return
            
            body = self.read_request_body()
            try:
                data = json.loads(body)
            except:
                self.send_json_response(400, {"error": "无效的 JSON"})
                return
            
            # 读取现有配置
            config_path = get_project_root() / "info" / "admin_config.json"
            config = load_admin_config()
            
            # 更新 exclude_tags
            if 'exclude_tags' in data:
                config['exclude_tags'] = data['exclude_tags']
            
            # 保存配置
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=4)
            
            self.send_json_response(200, {"status": "saved"})
        
        elif path == "/api/run-crawl":
            # 触发增量更新
            if running_tasks.get("crawl"):
                self.send_json_response(200, {"status": "already_running"})
                return
            
            # 保存运行时间
            save_run_status(crawl_time=datetime.now().isoformat())
            
            # 异步运行脚本
            run_script_async("monitor.py", task_type="crawl")
            
            self.send_json_response(200, {"status": "started"})
            
        elif path == "/api/run-summary":
            # 触发 AI 总结
            if running_tasks.get("summary"):
                self.send_json_response(200, {"status": "already_running"})
                return
            
            # 保存运行时间
            save_run_status(summary_time=datetime.now().isoformat())
            
            # 异步运行脚本
            run_script_async("ai_summary.py", task_type="summary")
            
            self.send_json_response(200, {"status": "started"})
        
        elif path == "/api/run-tag-all":
            # 触发为所有未打标内容自动打标
            if running_tasks.get("tagging"):
                self.send_json_response(200, {"status": "already_running"})
                return
            
            running_tasks["tagging"] = True
            
            # 异步运行打标脚本
            run_script_async("llm_tagger.py", task_type="tagging")
            
            self.send_json_response(200, {"status": "started"})
        
        elif path == "/api/admin/others/update":
            # 更新 feature 的标签
            token = self.get_auth_token()
            if not verify_session(token):
                self.send_json_response(401, {"error": "未授权访问"})
                return
            
            body = self.read_request_body()
            try:
                data = json.loads(body)
            except:
                self.send_json_response(400, {"error": "无效的 JSON"})
                return
            
            product = data.get('product')
            feature_index = data.get('feature_index')
            new_primary_tag = data.get('primary_tag')
            new_subtag = data.get('subtag')
            
            if not all([product, new_primary_tag, new_subtag]) or feature_index is None:
                self.send_json_response(400, {"error": "缺少必要参数"})
                return
            
            # 1. 更新 tag.json（如果是新的 subtag）
            tag_file = get_project_root() / "info" / "tag.json"
            with open(tag_file, 'r', encoding='utf-8') as f:
                tags_data = json.load(f)
            
            # 检查 subtag 是否已存在于映射中
            subtag_to_primary = tags_data.get('subtag_to_primary', {})
            if new_subtag not in subtag_to_primary:
                # 新的 subtag，需要添加到 tag.json
                subtag_to_primary[new_subtag] = new_primary_tag
                
                # 找到对应的 primary tag 并添加 subtag
                for p_tag in tags_data.get('primary_tags', []):
                    if p_tag.get('name') == new_primary_tag:
                        if 'subtags' not in p_tag:
                            p_tag['subtags'] = []
                        # 检查是否已存在
                        existing = [s for s in p_tag['subtags'] if s.get('name') == new_subtag]
                        if not existing:
                            p_tag['subtags'].append({
                                'name': new_subtag,
                                'description': new_subtag
                            })
                        break
                else:
                    # primary tag 不存在，创建新的
                    tags_data['primary_tags'].append({
                        'name': new_primary_tag,
                        'description': new_primary_tag,
                        'subtags': [{
                            'name': new_subtag,
                            'description': new_subtag
                        }]
                    })
                
                tags_data['subtag_to_primary'] = subtag_to_primary
                
                with open(tag_file, 'w', encoding='utf-8') as f:
                    json.dump(tags_data, f, ensure_ascii=False, indent=4)
            
            # 2. 更新产品的 feature tags
            product_file = get_project_root() / "storage" / f"{product}.json"
            if not product_file.exists():
                self.send_json_response(404, {"error": f"产品文件不存在: {product}"})
                return
            
            with open(product_file, 'r', encoding='utf-8') as f:
                product_data = json.load(f)
            
            feature_data = next((item for item in product_data if item.get('name') == 'feature'), None)
            if not feature_data or feature_index >= len(feature_data.get('features', [])):
                self.send_json_response(404, {"error": "找不到指定的 feature"})
                return
            
            feature = feature_data['features'][feature_index]
            current_tags = feature.get('tags', [])
            
            # 确保 current_tags 是列表
            if not isinstance(current_tags, list):
                current_tags = []
            
            # 移除 Others 标签中该 subtag，添加到正确的 primary tag
            new_tags = []
            for tag in current_tags:
                # 确保 tag 是字典
                if not isinstance(tag, dict):
                    continue
                if tag.get('name') == 'Others':
                    # 从 Others 中移除这个 subtag
                    subtags = tag.get('subtags', [])
                    if isinstance(subtags, list):
                        remaining_subtags = [s for s in subtags if isinstance(s, dict) and s.get('name') != new_subtag]
                    else:
                        remaining_subtags = []
                    if remaining_subtags:
                        tag['subtags'] = remaining_subtags
                        new_tags.append(tag)
                    # 如果 Others 没有 subtag 了，就不添加了
                elif tag.get('name') == new_primary_tag:
                    # 已有这个 primary tag，添加 subtag
                    subtags = tag.get('subtags', [])
                    if isinstance(subtags, list):
                        existing_subtags = [s.get('name') for s in subtags if isinstance(s, dict)]
                    else:
                        existing_subtags = []
                        tag['subtags'] = []
                    if new_subtag not in existing_subtags:
                        tag['subtags'].append({'name': new_subtag})
                    new_tags.append(tag)
                else:
                    new_tags.append(tag)
            
            # 检查是否需要新增 primary tag
            has_primary = any(t.get('name') == new_primary_tag for t in new_tags)
            if not has_primary:
                new_tags.append({
                    'name': new_primary_tag,
                    'subtags': [{'name': new_subtag}]
                })
            
            feature['tags'] = new_tags
            
            with open(product_file, 'w', encoding='utf-8') as f:
                json.dump(product_data, f, ensure_ascii=False, indent=4)
            
            self.send_json_response(200, {"status": "updated"})
        
        elif path == "/api/admin/feature/update-tags":
            # 更新单个 feature 的标签
            token = self.get_auth_token()
            if not verify_session(token):
                self.send_json_response(401, {"error": "未授权访问"})
                return
            
            body = self.read_request_body()
            try:
                data = json.loads(body)
            except:
                self.send_json_response(400, {"error": "无效的 JSON"})
                return
            
            product = data.get('product')
            feature_index = data.get('feature_index')
            new_tags = data.get('tags', [])  # [{name: 'Primary', subtags: [{name: 'Subtag'}]}]
            
            if not product or feature_index is None:
                self.send_json_response(400, {"error": "缺少必要参数"})
                return
            
            # 更新产品的 feature tags
            product_file = get_project_root() / "storage" / f"{product}.json"
            if not product_file.exists():
                self.send_json_response(404, {"error": f"产品文件不存在: {product}"})
                return
            
            with open(product_file, 'r', encoding='utf-8') as f:
                product_data = json.load(f)
            
            feature_data = next((item for item in product_data if item.get('name') == 'feature'), None)
            if not feature_data or feature_index >= len(feature_data.get('features', [])):
                self.send_json_response(404, {"error": "找不到指定的 feature"})
                return
            
            feature = feature_data['features'][feature_index]
            feature['tags'] = new_tags
            
            with open(product_file, 'w', encoding='utf-8') as f:
                json.dump(product_data, f, ensure_ascii=False, indent=4)
            
            self.send_json_response(200, {"status": "updated"})
        
        elif path == "/api/admin/feature/mark-none":
            # 将 feature 标记为 "无需打标"（tags 设为 "None" 字符串）
            token = self.get_auth_token()
            if not verify_session(token):
                self.send_json_response(401, {"error": "未授权访问"})
                return
            
            body = self.read_request_body()
            try:
                data = json.loads(body)
            except:
                self.send_json_response(400, {"error": "无效的 JSON"})
                return
            
            product = data.get('product')
            feature_index = data.get('feature_index')
            mark_as_none = data.get('mark_as_none', True)  # True = 标记为无需打标，False = 清除标记（变为未打标）
            
            if not product or feature_index is None:
                self.send_json_response(400, {"error": "缺少必要参数"})
                return
            
            product_file = get_project_root() / "storage" / f"{product}.json"
            if not product_file.exists():
                self.send_json_response(404, {"error": f"产品文件不存在: {product}"})
                return
            
            with open(product_file, 'r', encoding='utf-8') as f:
                product_data = json.load(f)
            
            feature_data = next((item for item in product_data if item.get('name') == 'feature'), None)
            if not feature_data or feature_index >= len(feature_data.get('features', [])):
                self.send_json_response(404, {"error": "找不到指定的 feature"})
                return
            
            feature = feature_data['features'][feature_index]
            
            if mark_as_none:
                feature['tags'] = "None"  # 设为字符串 "None" 表示无需打标
            else:
                feature['tags'] = []  # 设为空数组表示未打标
            
            with open(product_file, 'w', encoding='utf-8') as f:
                json.dump(product_data, f, ensure_ascii=False, indent=4)
            
            self.send_json_response(200, {"status": "marked" if mark_as_none else "unmarked"})
        
        elif path == "/api/admin/tag/rename":
            # 统一重命名标签（支持合并同名标签）
            token = self.get_auth_token()
            if not verify_session(token):
                self.send_json_response(401, {"error": "未授权访问"})
                return
            
            body = self.read_request_body()
            try:
                data = json.loads(body)
            except:
                self.send_json_response(400, {"error": "无效的 JSON"})
                return
            
            old_name = data.get('old_name')
            new_name = data.get('new_name')
            tag_type = data.get('type', 'subtag')  # 'primary' or 'subtag'
            
            if not old_name or not new_name:
                self.send_json_response(400, {"error": "缺少 old_name 或 new_name"})
                return
            
            if old_name == new_name:
                self.send_json_response(400, {"error": "新旧名称相同"})
                return
            
            # 1. 更新 tag.json
            tag_file = get_project_root() / "info" / "tag.json"
            with open(tag_file, 'r', encoding='utf-8') as f:
                tags_data = json.load(f)
            
            is_merge = False  # 是否是合并操作
            
            if tag_type == 'primary':
                # 检查 new_name 是否已存在（合并操作）
                existing_new = any(p.get('name') == new_name for p in tags_data.get('primary_tags', []))
                is_merge = existing_new
                
                if is_merge:
                    # 合并：找到旧标签和新标签
                    old_tag = next((p for p in tags_data['primary_tags'] if p.get('name') == old_name), None)
                    new_tag = next((p for p in tags_data['primary_tags'] if p.get('name') == new_name), None)
                    
                    if old_tag and new_tag:
                        # 将旧标签的 subtags 合并到新标签
                        existing_subtag_names = {s.get('name') for s in new_tag.get('subtags', [])}
                        for subtag in old_tag.get('subtags', []):
                            if subtag.get('name') not in existing_subtag_names:
                                new_tag.setdefault('subtags', []).append(subtag)
                        
                        # 删除旧标签
                        tags_data['primary_tags'] = [p for p in tags_data['primary_tags'] if p.get('name') != old_name]
                        
                        # 更新 subtag_to_primary 映射
                        for subtag, primary in list(tags_data.get('subtag_to_primary', {}).items()):
                            if primary == old_name:
                                tags_data['subtag_to_primary'][subtag] = new_name
                else:
                    # 重命名一级标签
                    for p_tag in tags_data.get('primary_tags', []):
                        if p_tag.get('name') == old_name:
                            p_tag['name'] = new_name
                            break
                    
                    # 更新 subtag_to_primary 中的值
                    for subtag, primary in list(tags_data.get('subtag_to_primary', {}).items()):
                        if primary == old_name:
                            tags_data['subtag_to_primary'][subtag] = new_name
            else:
                # 检查 new_name 是否已存在（合并操作）
                existing_new = new_name in tags_data.get('subtag_to_primary', {})
                is_merge = existing_new
                
                if is_merge:
                    # 合并：删除旧的 subtag，保留新的
                    for p_tag in tags_data.get('primary_tags', []):
                        p_tag['subtags'] = [s for s in p_tag.get('subtags', []) if s.get('name') != old_name]
                    
                    # 删除旧的映射
                    if old_name in tags_data.get('subtag_to_primary', {}):
                        del tags_data['subtag_to_primary'][old_name]
                else:
                    # 重命名二级标签
                    # 更新 primary_tags 中的 subtags
                    for p_tag in tags_data.get('primary_tags', []):
                        for subtag in p_tag.get('subtags', []):
                            if subtag.get('name') == old_name:
                                subtag['name'] = new_name
                                break
                    
                    # 更新 subtag_to_primary 映射
                    if old_name in tags_data.get('subtag_to_primary', {}):
                        primary = tags_data['subtag_to_primary'].pop(old_name)
                        tags_data['subtag_to_primary'][new_name] = primary
            
            with open(tag_file, 'w', encoding='utf-8') as f:
                json.dump(tags_data, f, ensure_ascii=False, indent=4)
            
            # 2. 更新所有产品文件中的标签（支持合并）
            storage_dir = get_project_root() / "storage"
            products = ['youware', 'base44', 'bolt', 'lovable', 'replit', 'rocket', 'trickle', 'v0']
            updated_count = 0
            merged_count = 0
            
            for product in products:
                product_file = storage_dir / f"{product}.json"
                if not product_file.exists():
                    continue
                
                with open(product_file, 'r', encoding='utf-8') as f:
                    product_data = json.load(f)
                
                modified = False
                feature_data = next((item for item in product_data if item.get('name') == 'feature'), None)
                if not feature_data:
                    continue
                
                for feature in feature_data.get('features', []):
                    tags = feature.get('tags', [])
                    if not isinstance(tags, list):
                        continue
                    
                    if tag_type == 'primary':
                        # 处理一级标签
                        old_tag = next((t for t in tags if isinstance(t, dict) and t.get('name') == old_name), None)
                        new_tag = next((t for t in tags if isinstance(t, dict) and t.get('name') == new_name), None)
                        
                        if old_tag:
                            if new_tag and is_merge:
                                # 合并：将旧标签的 subtags 合并到新标签
                                existing = {s.get('name') for s in new_tag.get('subtags', []) if isinstance(s, dict)}
                                for s in old_tag.get('subtags', []):
                                    if isinstance(s, dict) and s.get('name') not in existing:
                                        new_tag.setdefault('subtags', []).append(s)
                                # 删除旧标签
                                feature['tags'] = [t for t in tags if not (isinstance(t, dict) and t.get('name') == old_name)]
                                merged_count += 1
                            else:
                                # 重命名
                                old_tag['name'] = new_name
                            modified = True
                    else:
                        # 处理二级标签
                        for tag in tags:
                            if not isinstance(tag, dict):
                                continue
                            subtags = tag.get('subtags', [])
                            if not isinstance(subtags, list):
                                continue
                            
                            old_subtag_idx = next((i for i, s in enumerate(subtags) if isinstance(s, dict) and s.get('name') == old_name), None)
                            new_subtag_exists = any(isinstance(s, dict) and s.get('name') == new_name for s in subtags)
                            
                            if old_subtag_idx is not None:
                                if new_subtag_exists and is_merge:
                                    # 合并：删除旧的（新的已存在）
                                    subtags.pop(old_subtag_idx)
                                    merged_count += 1
                                else:
                                    # 重命名
                                    subtags[old_subtag_idx]['name'] = new_name
                                modified = True
                
                if modified:
                    with open(product_file, 'w', encoding='utf-8') as f:
                        json.dump(product_data, f, ensure_ascii=False, indent=4)
                    updated_count += 1
            
            self.send_json_response(200, {
                "status": "merged" if is_merge else "renamed",
                "updated_products": updated_count,
                "merged_items": merged_count if is_merge else 0
            })
        
        elif path == "/api/admin/features":
            # 获取产品的 features 列表
            token = self.get_auth_token()
            if not verify_session(token):
                self.send_json_response(401, {"error": "未授权访问"})
                return
            
            body = self.read_request_body()
            try:
                data = json.loads(body)
            except:
                self.send_json_response(400, {"error": "无效的 JSON"})
                return
            
            product = data.get('product', 'youware')
            page = data.get('page', 1)
            page_size = data.get('page_size', 20)
            search = data.get('search', '')
            
            product_file = get_project_root() / "storage" / f"{product}.json"
            if not product_file.exists():
                self.send_json_response(404, {"error": f"产品文件不存在: {product}"})
                return
            
            with open(product_file, 'r', encoding='utf-8') as f:
                product_data = json.load(f)
            
            feature_data = next((item for item in product_data if item.get('name') == 'feature'), None)
            if not feature_data:
                self.send_json_response(200, {"features": [], "total": 0, "page": page})
                return
            
            all_features = feature_data.get('features', [])
            
            # 搜索过滤
            if search:
                search_lower = search.lower()
                all_features = [
                    (idx, f) for idx, f in enumerate(all_features)
                    if search_lower in f.get('title', '').lower() or 
                       search_lower in f.get('description', '').lower()
                ]
            else:
                all_features = [(idx, f) for idx, f in enumerate(all_features)]
            
            total = len(all_features)
            
            # 分页
            start = (page - 1) * page_size
            end = start + page_size
            page_features = all_features[start:end]
            
            # 构建返回数据
            result_features = []
            for idx, f in page_features:
                result_features.append({
                    'index': idx,
                    'title': f.get('title', ''),
                    'description': f.get('description', ''),
                    'time': f.get('time', ''),
                    'tags': f.get('tags', [])
                })
            
            self.send_json_response(200, {
                "features": result_features,
                "total": total,
                "page": page,
                "page_size": page_size
            })
        
        elif path == "/api/admin/feature/add":
            # 添加新功能条目
            token = self.get_auth_token()
            if not verify_session(token):
                self.send_json_response(401, {"error": "未授权访问"})
                return
            
            body = self.read_request_body()
            try:
                data = json.loads(body)
            except:
                self.send_json_response(400, {"error": "无效的 JSON"})
                return
            
            product = data.get('product', 'youware')
            title = data.get('title', '').strip()
            description = data.get('description', '').strip()
            time_str = data.get('time', '')
            auto_tag = data.get('auto_tag', True)
            
            if not title:
                self.send_json_response(400, {"error": "标题不能为空"})
                return
            
            # 加载产品 JSON
            product_file = get_project_root() / "storage" / f"{product}.json"
            if not product_file.exists():
                self.send_json_response(404, {"error": f"产品文件不存在: {product}"})
                return
            
            with open(product_file, 'r', encoding='utf-8') as f:
                product_data = json.load(f)
            
            feature_data = next((item for item in product_data if item.get('name') == 'feature'), None)
            if not feature_data:
                self.send_json_response(404, {"error": "找不到 feature 数据"})
                return
            
            # 创建新功能
            new_feature = {
                "title": title,
                "description": description,
                "time": time_str or datetime.now().strftime("%Y-%m-%d")
            }
            
            # 插入到最前面
            feature_data['features'].insert(0, new_feature)
            
            # 保存
            with open(product_file, 'w', encoding='utf-8') as f:
                json.dump(product_data, f, ensure_ascii=False, indent=4)
            
            # 如果需要自动打标
            if auto_tag:
                def run_tag():
                    root = get_project_root()
                    if root == Path("/app"):
                        script_path = root / "llm_tagger.py"
                    else:
                        script_path = root / "script" / "llm_tagger.py"
                    try:
                        subprocess.run(
                            [sys.executable, str(script_path), "--file", f"{product}.json"],
                            capture_output=True,
                            text=True,
                            timeout=120
                        )
                    except Exception as e:
                        print(f"自动打标失败: {e}")
                
                thread = threading.Thread(target=run_tag)
                thread.start()
            
            self.send_json_response(200, {"status": "added", "auto_tag": auto_tag})
        
        elif path == "/api/admin/feature/edit":
            # 编辑功能条目（标题、描述、日期）
            token = self.get_auth_token()
            if not verify_session(token):
                self.send_json_response(401, {"error": "未授权访问"})
                return
            
            body = self.read_request_body()
            try:
                data = json.loads(body)
            except:
                self.send_json_response(400, {"error": "无效的 JSON"})
                return
            
            product = data.get('product', 'youware')
            feature_index = data.get('feature_index')
            title = data.get('title')
            description = data.get('description')
            time_str = data.get('time')
            
            if feature_index is None:
                self.send_json_response(400, {"error": "缺少 feature_index"})
                return
            
            # 加载产品 JSON
            product_file = get_project_root() / "storage" / f"{product}.json"
            if not product_file.exists():
                self.send_json_response(404, {"error": f"产品文件不存在: {product}"})
                return
            
            with open(product_file, 'r', encoding='utf-8') as f:
                product_data = json.load(f)
            
            feature_data = next((item for item in product_data if item.get('name') == 'feature'), None)
            if not feature_data or feature_index >= len(feature_data.get('features', [])):
                self.send_json_response(404, {"error": "找不到指定的 feature"})
                return
            
            feature = feature_data['features'][feature_index]
            
            # 更新字段
            if title is not None:
                feature['title'] = title
            if description is not None:
                feature['description'] = description
            if time_str is not None:
                feature['time'] = time_str
            
            # 保存
            with open(product_file, 'w', encoding='utf-8') as f:
                json.dump(product_data, f, ensure_ascii=False, indent=4)
            
            self.send_json_response(200, {"status": "updated"})
        
        elif path == "/api/admin/feature/delete":
            # 删除功能条目
            token = self.get_auth_token()
            if not verify_session(token):
                self.send_json_response(401, {"error": "未授权访问"})
                return
            
            body = self.read_request_body()
            try:
                data = json.loads(body)
            except:
                self.send_json_response(400, {"error": "无效的 JSON"})
                return
            
            product = data.get('product', 'youware')
            feature_index = data.get('feature_index')
            
            if feature_index is None:
                self.send_json_response(400, {"error": "缺少 feature_index"})
                return
            
            # 加载产品 JSON
            product_file = get_project_root() / "storage" / f"{product}.json"
            if not product_file.exists():
                self.send_json_response(404, {"error": f"产品文件不存在: {product}"})
                return
            
            with open(product_file, 'r', encoding='utf-8') as f:
                product_data = json.load(f)
            
            feature_data = next((item for item in product_data if item.get('name') == 'feature'), None)
            if not feature_data or feature_index >= len(feature_data.get('features', [])):
                self.send_json_response(404, {"error": "找不到指定的 feature"})
                return
            
            # 删除
            deleted = feature_data['features'].pop(feature_index)
            
            # 保存
            with open(product_file, 'w', encoding='utf-8') as f:
                json.dump(product_data, f, ensure_ascii=False, indent=4)
            
            self.send_json_response(200, {"status": "deleted", "deleted_title": deleted.get('title', '')})
            
        else:
            self.send_response(404)
            self.end_headers()
    
    def do_OPTIONS(self):
        # CORS 预检请求
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()
    
    def log_message(self, format, *args):
        print(f"[API] {args[0]}")


def main():
    port = 3003
    server = HTTPServer(("0.0.0.0", port), APIHandler)
    print(f"API 服务器运行在 http://0.0.0.0:{port}")
    print("可用接口:")
    print("  POST /api/admin/login     - 管理员登录")
    print("  GET  /api/admin/changelog - 获取 changelog")
    print("  POST /api/admin/changelog - 保存 changelog")
    print("  POST /api/admin/logout    - 登出")
    print("  POST /api/run-crawl       - 触发增量更新")
    print("  POST /api/run-summary     - 触发 AI 总结")
    print("  GET  /api/status          - 获取运行状态")
    print("\n按 Ctrl+C 停止服务器")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n服务器已停止")
        server.server_close()


if __name__ == "__main__":
    main()
