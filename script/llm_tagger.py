#!/usr/bin/env python3
"""
使用 LLM 为功能更新打标
新逻辑：LLM 只识别二级标签，通过映射表自动获得一级标签
支持网络错误和 JSON 解析错误重试
"""

import json
import time
import re
from pathlib import Path
import requests


# 重试配置
MAX_RETRIES = 3
RETRY_DELAY = 2  # 秒


def get_project_root():
    """获取项目根目录（支持本地和 Docker 环境）"""
    script_dir = Path(__file__).parent
    if script_dir == Path("/app"):
        return Path("/app")
    return script_dir.parent


def get_script_dir():
    """获取脚本目录"""
    script_dir = Path(__file__).parent
    if script_dir == Path("/app"):
        return Path("/app")
    return script_dir


def load_config():
    """加载 LLM 配置"""
    config_path = get_script_dir() / "prompts" / "llm_config.json"
    with open(config_path, "r", encoding="utf-8") as f:
        configs = json.load(f)
    return configs[0]  # 使用第一个配置


def load_tags():
    """加载标签体系（新结构：primary_tags + subtag_to_primary）"""
    tags_path = get_project_root() / "info" / "tag.json"
    with open(tags_path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_tags(tags_data: dict):
    """保存标签体系"""
    tags_path = get_project_root() / "info" / "tag.json"
    with open(tags_path, "w", encoding="utf-8") as f:
        json.dump(tags_data, f, ensure_ascii=False, indent=4)


def normalize_name(name: str) -> str:
    """标准化名称，用于模糊匹配"""
    return name.lower().strip().replace(" ", "").replace("-", "").replace("_", "")


def build_subtag_index(tags_data: dict) -> dict:
    """
    构建二级标签索引，用于快速查找和映射
    返回: {
        "subtag_norm_to_original": {"openai": "OpenAI", ...},
        "subtag_to_primary": {"OpenAI": "AI Model", ...},
        "all_subtags": ["OpenAI", "Anthropic", ...]
    }
    """
    subtag_to_primary = tags_data.get("subtag_to_primary", {})
    subtag_norm_to_original = {}
    all_subtags = []
    
    for subtag_name in subtag_to_primary.keys():
        norm = normalize_name(subtag_name)
        subtag_norm_to_original[norm] = subtag_name
        all_subtags.append(subtag_name)
    
    return {
        "subtag_norm_to_original": subtag_norm_to_original,
        "subtag_to_primary": subtag_to_primary,
        "all_subtags": all_subtags
    }


def normalize_subtag(subtag_name: str, subtag_index: dict) -> str:
    """
    标准化二级标签名称（修正空格、大小写差异）
    返回: 标准化后的名称，如果是新标签则返回原名称
    """
    norm = normalize_name(subtag_name)
    norm_to_original = subtag_index.get("subtag_norm_to_original", {})
    
    if norm in norm_to_original:
        return norm_to_original[norm]
    return subtag_name


def map_subtags_to_tags(subtags: list, tags_data: dict, subtag_index: dict) -> list:
    """
    将二级标签列表映射到完整的标签结构
    输入: ["OpenAI", "Agent Mode", "Custom Domain"]
    输出: [
        {"name": "AI Model", "subtags": [{"name": "OpenAI"}]},
        {"name": "Agent", "subtags": [{"name": "Agent Mode"}]},
        {"name": "Deployment", "subtags": [{"name": "Custom Domain"}]}
    ]
    """
    subtag_to_primary = tags_data.get("subtag_to_primary", {})
    
    # 获取所有一级标签名（用于过滤 LLM 错误返回的一级标签名）
    primary_tag_names = {pt["name"] for pt in tags_data.get("primary_tags", [])}
    
    # 按一级标签分组
    primary_to_subtags = {}
    new_subtags = []  # 新的二级标签（需要归入 Others）
    
    for subtag in subtags:
        # 标准化名称
        normalized = normalize_subtag(subtag, subtag_index)
        
        # 过滤掉一级标签名（LLM 错误返回）
        if normalized in primary_tag_names:
            print(f"       ⚠️ 忽略一级标签名: {normalized}")
            continue
        
        if normalized in subtag_to_primary:
            primary = subtag_to_primary[normalized]
            if primary not in primary_to_subtags:
                primary_to_subtags[primary] = []
            primary_to_subtags[primary].append({"name": normalized})
        else:
            # 新的二级标签，归入 Others
            new_subtags.append(normalized)
    
    # 处理新的二级标签 - 归入 Others
    if new_subtags:
        if "Others" not in primary_to_subtags:
            primary_to_subtags["Others"] = []
        for new_subtag in new_subtags:
            primary_to_subtags["Others"].append({"name": new_subtag})
            # 更新映射表
            tags_data["subtag_to_primary"][new_subtag] = "Others"
            subtag_index["subtag_to_primary"][new_subtag] = "Others"
            subtag_index["subtag_norm_to_original"][normalize_name(new_subtag)] = new_subtag
            subtag_index["all_subtags"].append(new_subtag)
            # 添加到 Others 的 subtags 列表
            for pt in tags_data.get("primary_tags", []):
                if pt["name"] == "Others":
                    pt["subtags"].append({"name": new_subtag, "description": new_subtag})
                    break
    
    # 转换为输出格式
    result = []
    for primary, subs in primary_to_subtags.items():
        result.append({
            "name": primary,
            "subtags": subs
        })
    
    return result


def call_llm_with_retry(prompt: str, config: dict, max_retries: int = MAX_RETRIES) -> str:
    """调用 LLM API，支持重试"""
    headers = {
        "Content-Type": "application/json",
        "x-api-key": config["api_key"],
        "anthropic-version": "2023-06-01"
    }
    
    payload = {
        "model": config["model"],
        "max_tokens": 1024,
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ]
    }
    
    last_error = None
    
    for attempt in range(max_retries):
        try:
            response = requests.post(
                f"{config['base_url']}/v1/messages",
                headers=headers,
                json=payload,
                timeout=60  # 增加超时时间
            )
            response.raise_for_status()
            result = response.json()
            return result.get("content", [{}])[0].get("text", "")
        except requests.exceptions.Timeout as e:
            last_error = f"超时: {e}"
        except requests.exceptions.ConnectionError as e:
            last_error = f"连接错误: {e}"
        except requests.exceptions.RequestException as e:
            last_error = f"请求错误: {e}"
        except Exception as e:
            last_error = f"未知错误: {e}"
        
        if attempt < max_retries - 1:
            wait_time = RETRY_DELAY * (attempt + 1)
            print(f"       ⚠️ 第 {attempt + 1} 次失败 ({last_error})，{wait_time}s 后重试...")
            time.sleep(wait_time)
    
    print(f"       ❌ LLM 调用失败 ({max_retries} 次重试后): {last_error}")
    return ""


def parse_llm_response(response: str) -> tuple:
    """
    解析 LLM 响应（新格式：只返回二级标签列表）
    返回: (subtags列表, 是否解析成功, 错误信息)
    """
    if not response:
        return [], False, "响应为空"
    
    # 尝试直接解析
    try:
        data = json.loads(response)
        subtags = data.get("subtags", [])
        if isinstance(subtags, list):
            return subtags, True, None
        else:
            return [], False, "subtags 格式不正确"
    except json.JSONDecodeError:
        pass
    
    # 尝试从代码块中提取
    json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response, re.DOTALL)
    if json_match:
        try:
            data = json.loads(json_match.group(1))
            subtags = data.get("subtags", [])
            if isinstance(subtags, list):
                return subtags, True, None
        except json.JSONDecodeError:
            pass
    
    # 尝试找到 JSON 对象 - 更宽松的匹配
    json_match = re.search(r'\{\s*"subtags"\s*:\s*\[.*?\]\s*\}', response, re.DOTALL)
    if json_match:
        try:
            data = json.loads(json_match.group(0))
            subtags = data.get("subtags", [])
            if isinstance(subtags, list):
                return subtags, True, None
        except json.JSONDecodeError:
            pass
    
    return [], False, "无法解析 JSON"


def build_prompt(title: str, description: str, tags_data: dict) -> str:
    """构建打标提示词（新版：只识别二级标签）"""
    
    # 构建二级标签列表供 LLM 参考
    subtag_categories = []
    all_primary_names = set()
    for pt in tags_data.get("primary_tags", []):
        all_primary_names.add(pt["name"])
        if pt["name"] == "Others":
            continue  # 不显示 Others
        subtags = [st["name"] for st in pt.get("subtags", [])]
        if subtags:
            subtag_categories.append(f"【{pt['name']}】: {', '.join(subtags)}")
    
    subtag_list = "\n".join(subtag_categories)
    primary_names_str = ", ".join(sorted(all_primary_names - {"Others"}))
    
    prompt = f"""你是一个竞品分析专家，负责为竞品的功能更新进行分类打标。

## 可用的二级标签（按类别分组）

{subtag_list}

## 待打标的功能

- **标题**: {title}
- **描述**: {description}

## 任务

选择 1-2 个最准确的二级标签。标签应该互斥，不要选择重叠的标签。

## ⚠️ 严格规则

### 1. 禁止返回一级标签名
以下是一级标签名，绝对不能作为结果返回：{primary_names_str}

### 2. 严格匹配原则

**Integration 必须明确提到服务名**
- 只有明确提到 "GitHub"、"Supabase"、"Stripe" 等服务名时才能打对应标签
- "repository push" 不等于 GitHub（可能是内置 Git 功能）→ 打性能相关标签
- "push timing" / "performance" → "Speed"（属于 Performance）

**Backend vs Agent**
- 存储、数据库相关 → "Storage" 或 "Database"（属于 Backend）
- 只有涉及 AI 自动化工作流才打 Agent 标签
- "AI Integration Persistence"（存储 AI 生成内容）→ "Storage"，不是 Automation

**Social Share vs Integration**
- Twitter/LinkedIn/Telegram **分享按钮** → "Social Share"（属于 Community）
- 只有真正调用 API 才是 Integration

**Social Login vs Integration**  
- Google/Apple/GitHub/Twitter **登录** → "Social Login"（属于 Auth）
- Google Analytics → "Usage Stats"（属于 Analytics）

**Backend vs Integration**
- 产品内置后端（YouBase/Lovable Cloud/Bolt Database）→ Backend
- 明确提到第三方服务名（Supabase/Firebase）→ Integration

### 3. AI Model 打标
- GPT-4, GPT-5, o1, o3, Codex → "OpenAI"
- Claude Opus, Sonnet, Haiku → "Anthropic"
- Gemini, Veo, Imagen → "Google"（模型更新，不是 Google 登录！）
- Grok → "xAI"
- Kimi → "Moonshot"
- MiniMax M2 → "MiniMax"
- GLM 4.5, 4.6, 4.7 → "GLM"

### 3.5 Media 打标严格规则
**Audio Generation 只用于 AI 生成语音/音频**
- TTS（文字转语音）、AI 配音、ElevenLabs 等 → "Audio Generation"
- 音频文件上传/支持 → "File Upload"（属于 File），不是 Audio Generation！
- 视频理解（video understanding/analysis）→ "Video Understanding"，不是 Audio Generation！
- 即使描述中提到 "audio understanding"，如果是视频分析功能 → 仍是 "Video Understanding"

**Image/Video 区分**
- 图片生成 → "Image Generation"
- 图片编辑 → "Image Edit"  
- 视频生成 → "Video Generation"
- 视频分析/理解 → "Video Understanding"

### 3.6 第三方服务识别
**以下是第三方服务，应打 Integration 标签（需明确提到名称）**：
- 代码托管: GitHub, GitLab, Bitbucket
- 项目管理: Jira, Linear, Notion, Confluence, Todoist
- 通讯: Slack, Discord, Twilio
- 支付: Stripe, Plaid
- 云服务: Snowflake, AWS, GCP, Azure, Cloudflare
- AI 服务: ChatGPT, Perplexity, ElevenLabs, Replicate
- 客服: Zendesk, Intercom
- 设计: Figma
- 开发工具: VS Code, Cursor

**以下不是 Integration**：
- 产品内置的数据库/存储 → Backend（Database/Storage）
- 分享按钮 → Community（Social Share）
- 登录方式 → Auth（Social Login）

### 4. 标签互斥原则
- 每个功能只选最准确的 1-2 个标签
- 避免选择语义重叠的标签

### 4.5 移动端 App 标签区分
**iOS App / Android App = 生成移动应用的能力**
- 只有产品支持"导出/生成 iOS App"或"导出/生成 Android App"时才打这个标签
- 产品本身有移动端版本（如 "YouWare Mobile App"）不算 → 应打 "Mobile Editor" 或其他相关标签
- 移动端编辑器功能 → "Mobile Editor"（属于 Editor）
- 移动端推送通知 → "Push Notification"（属于 Community）

### 4.6 YouWare 不支持的功能（请勿错打）
**以下是 YouWare 明确没有的功能，不要给 YouWare 打这些标签**：
- Security Scan（安全扫描）：除非明确提到安全漏洞扫描功能
- Content Moderation（内容审核）：除非明确提到 AI 内容审核系统
- Keyboard Shortcuts（键盘快捷键）：除非明确提到自定义快捷键功能

### 4.7 Auth 归类
**用户可用的认证服务归入 Backend/Auth**
- 产品提供给用户项目使用的 Auth 服务（如 YouBase 的认证）→ "Database" 或 "Auth Related"（属于 Backend）
- 用户登录产品的方式（如 Google 登录 YouWare）→ "Social Login"（属于 Auth）

### 4.8 Framework 标签
**前端框架/库支持**
- TailwindCSS、shadcn、Three.js、React、Vue → "Framework" 相关标签
- 如果明确提到支持某个框架 → 打对应的 Framework 二级标签

### 5. Bug 修复
- 纯粹的 Bug 修复（无具体功能描述）→ 返回空数组
- 如果 Bug 修复涉及具体功能，打对应功能的标签

## 输出格式

```json
{{
    "subtags": ["标签1", "标签2"]
}}
```

如果是纯 Bug 修复或非功能性内容：
```json
{{
    "subtags": []
}}
```

请直接输出 JSON："""
    
    return prompt


def tag_single_feature(title: str, description: str, config: dict, tags_data: dict, subtag_index: dict) -> tuple:
    """
    为单个功能打标
    
    返回: (tags, success, new_subtags_added)
        - (tags, True, [...]): 成功打标
        - ([], True, []): LLM 判断为非功能性内容
        - (None, False, []): 调用失败
    """
    prompt = build_prompt(title, description, tags_data)
    new_subtags_added = []
    
    for attempt in range(MAX_RETRIES):
        response = call_llm_with_retry(prompt, config, max_retries=1)
        
        if not response:
            if attempt < MAX_RETRIES - 1:
                print(f"       ⚠️ 响应为空，重试 {attempt + 2}/{MAX_RETRIES}...")
                time.sleep(RETRY_DELAY)
                continue
            print(f"       ❌ LLM 调用失败")
            return (None, False, [])
        
        subtags, success, error = parse_llm_response(response)
        
        if success:
            if subtags:
                # 获取一级标签名（用于过滤）
                primary_tag_names = {pt["name"] for pt in tags_data.get("primary_tags", [])}
                existing_subtags = set(subtag_index.get("all_subtags", []))
                
                # 记录新增的二级标签（排除一级标签名）
                for st in subtags:
                    normalized = normalize_subtag(st, subtag_index)
                    # 跳过一级标签名
                    if normalized in primary_tag_names:
                        continue
                    if normalized not in existing_subtags and st not in existing_subtags:
                        new_subtags_added.append(st)
                
                # 映射到完整标签结构
                tags = map_subtags_to_tags(subtags, tags_data, subtag_index)
                return (tags, True, new_subtags_added)
            else:
                return ([], True, [])
        
        if not success:
            if attempt < MAX_RETRIES - 1:
                print(f"       ⚠️ JSON 解析失败 ({error})，重试 {attempt + 2}/{MAX_RETRIES}...")
                time.sleep(RETRY_DELAY)
                continue
            else:
                print(f"       ❌ JSON 解析失败: {error}")
                return (None, False, [])
    
    return (None, False, [])


def process_all_features(use_llm: bool = True, limit_per_file: int = None, target_file: str = None):
    """
    处理功能更新
    
    Args:
        use_llm: 是否使用 LLM 打标
        limit_per_file: 每个文件最多处理条数
        target_file: 只处理指定文件 (如: youware.json)
    """
    project_root = get_project_root()
    storage_dir = project_root / "storage"
    
    config = load_config()
    tags_data = load_tags()
    subtag_index = build_subtag_index(tags_data)
    
    total_processed = 0
    total_tagged = 0
    total_skipped = 0
    all_new_subtags = []
    
    # 确定要处理的文件列表
    if target_file:
        target_path = storage_dir / target_file
        if not target_path.exists():
            print(f"❌ 文件不存在: {target_file}")
            return
        files_to_process = [target_path]
    else:
        files_to_process = list(storage_dir.glob("*.json"))
    
    for json_file in files_to_process:
        if json_file.name == "example.json":
            continue
        
        print(f"\n处理 {json_file.name}...")
        
        with open(json_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        if len(data) < 2:
            continue
        
        features = data[1].get("features", [])
        
        # 找出需要打标的功能
        features_to_tag = []
        for i, feat in enumerate(features):
            if "tags" not in feat:
                features_to_tag.append((i, feat))
        
        if limit_per_file:
            features_to_tag = features_to_tag[:limit_per_file]
        
        print(f"  需要打标: {len(features_to_tag)} 条")
        
        tagged_count = 0
        skipped_count = 0
        
        for idx, feat in features_to_tag:
            title = feat.get("title", "")
            description = feat.get("description", "")
            
            # 显示更长的标题（最多80字符）
            display_title = title[:80] + "..." if len(title) > 80 else title
            print(f"    {total_processed + 1}. {display_title}")
            
            if use_llm:
                tags, success, new_subtags = tag_single_feature(
                    title, description, config, tags_data, subtag_index
                )
                time.sleep(0.5)
            else:
                tags, success, new_subtags = [], True, []
            
            if not success:
                print(f"       ⏭️ 跳过，等待下次重试")
                total_processed += 1
                continue
            
            if tags:
                features[idx]["tags"] = tags
                tagged_count += 1
                # 显示详细的标签信息：一级 > 二级
                tag_details = []
                for t in tags:
                    primary = t["name"]
                    subtag_names = [s["name"] for s in t.get("subtags", [])]
                    if subtag_names:
                        tag_details.append(f"{primary} > {', '.join(subtag_names)}")
                    else:
                        tag_details.append(primary)
                print(f"       ✓ {' | '.join(tag_details)}")
                
                if new_subtags:
                    print(f"       🆕 新增二级标签 (归入 Others): {', '.join(new_subtags)}")
                    all_new_subtags.extend(new_subtags)
                    # 保存更新后的标签体系
                    save_tags(tags_data)
            else:
                features[idx]["tags"] = "None"
                skipped_count += 1
                print(f"       ○ 非功能性内容，跳过")
            
            # 每处理一条就立即保存
            with open(json_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            
            total_processed += 1
        
        print(f"  已处理 {len(features_to_tag)} 条，打标 {tagged_count} 条，跳过 {skipped_count} 条")
        total_tagged += tagged_count
        total_skipped += skipped_count
    
    # 最终保存标签体系
    if all_new_subtags:
        save_tags(tags_data)
        print(f"\n📝 标签体系已更新:")
        print(f"   新增二级标签 (归入 Others): {', '.join(all_new_subtags)}")
    
    print(f"\n{'='*50}")
    print(f"总计处理 {total_processed} 条功能更新")
    print(f"  ✓ 成功打标: {total_tagged} 条")
    print(f"  ○ 非功能性跳过: {total_skipped} 条")
    print(f"{'='*50}")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="LLM 打标脚本（二级标签自动映射一级）")
    parser.add_argument("--limit", type=int, default=None, help="每个文件最多处理多少条")
    parser.add_argument("--dry-run", action="store_true", help="只显示需要打标的条目，不实际调用 LLM")
    parser.add_argument("--file", type=str, default=None, help="只处理指定文件 (如: youware.json)")
    
    args = parser.parse_args()
    
    print("=" * 50)
    print("LLM 功能更新打标（二级标签 → 自动映射一级）")
    print(f"重试配置: 最多 {MAX_RETRIES} 次, 间隔 {RETRY_DELAY}s")
    if args.file:
        print(f"处理文件: {args.file}")
    print("=" * 50)
    
    if args.dry_run:
        process_all_features(use_llm=False, limit_per_file=args.limit, target_file=args.file)
    else:
        process_all_features(use_llm=True, limit_per_file=args.limit, target_file=args.file)


if __name__ == "__main__":
    main()
