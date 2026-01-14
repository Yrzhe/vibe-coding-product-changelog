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
    """异步运行脚本"""
    def run():
        global running_tasks
        if task_type:
            running_tasks[task_type] = True
        
        root = get_project_root()
        # Docker 中脚本在 /app 下，本地在 script/ 下
        if root == Path("/app"):
            script_path = root / script_name
        else:
            script_path = root / "script" / script_name
        try:
            result = subprocess.run(
                [sys.executable, str(script_path)],
                capture_output=True,
                text=True,
                timeout=600  # 10 分钟超时
            )
            if callback:
                callback(result.returncode == 0)
        except Exception as e:
            print(f"脚本运行失败: {e}")
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
            
            self.send_json_response(200, status)
        
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
