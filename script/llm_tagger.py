#!/usr/bin/env python3
"""
使用 LLM 为功能更新打标
自动更新 tag.json 中不存在的标签
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


def load_config():
    """加载 LLM 配置"""
    config_path = Path(__file__).parent / "prompts" / "llm_config.json"
    with open(config_path, "r", encoding="utf-8") as f:
        configs = json.load(f)
    return configs[0]  # 使用第一个配置


def load_tags():
    """加载标签体系"""
    tags_path = Path(__file__).parent.parent / "info" / "tag.json"
    with open(tags_path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_tags(tags_data: list):
    """保存标签体系"""
    tags_path = Path(__file__).parent.parent / "info" / "tag.json"
    with open(tags_path, "w", encoding="utf-8") as f:
        json.dump(tags_data, f, ensure_ascii=False, indent=4)


def normalize_name(name: str) -> str:
    """标准化名称，用于模糊匹配"""
    return name.lower().strip().replace(" ", "").replace("-", "").replace("_", "")


def get_tag_index(tags_data: list) -> dict:
    """
    构建标签索引，用于快速查找
    包含标准化名称用于模糊匹配
    """
    index = {}
    norm_to_original = {}  # 标准化名称 -> 原始名称
    
    for i, tag in enumerate(tags_data):
        tag_name = tag.get("name", "")
        tag_norm = normalize_name(tag_name)
        
        subtags = {}
        subtag_norm_map = {}  # 标准化名称 -> 原始名称
        
        for st in tag.get("subtags", []):
            st_name = st.get("name", "")
            st_norm = normalize_name(st_name)
            subtags[st_name] = True
            subtag_norm_map[st_norm] = st_name
        
        index[tag_name] = {
            "index": i,
            "subtags": set(subtags.keys()),
            "subtag_norm_map": subtag_norm_map
        }
        norm_to_original[tag_norm] = tag_name
    
    index["__norm_to_original__"] = norm_to_original
    return index


def normalize_llm_tags(tags: list, tag_index: dict) -> list:
    """
    标准化 LLM 返回的标签，修正名称差异（空格、大小写等）
    """
    norm_to_original = tag_index.get("__norm_to_original__", {})
    normalized_tags = []
    
    for tag_item in tags:
        tag_name = tag_item.get("name", "")
        if not tag_name:
            continue
        
        tag_norm = normalize_name(tag_name)
        
        # 检查是否有模糊匹配的主标签
        if tag_name not in tag_index and tag_norm in norm_to_original:
            original_name = norm_to_original[tag_norm]
            print(f"       🔧 标签名称修正: \"{tag_name}\" -> \"{original_name}\"")
            tag_name = original_name
        
        # 处理子标签
        subtags = tag_item.get("subtags", [])
        normalized_subtags = []
        
        if tag_name in tag_index:
            subtag_norm_map = tag_index[tag_name].get("subtag_norm_map", {})
            
            for st in subtags:
                st_name = st.get("name", "")
                if not st_name:
                    continue
                
                st_norm = normalize_name(st_name)
                
                # 检查是否有模糊匹配的子标签
                if st_name not in tag_index[tag_name]["subtags"] and st_norm in subtag_norm_map:
                    original_st_name = subtag_norm_map[st_norm]
                    print(f"       🔧 子标签名称修正: \"{st_name}\" -> \"{original_st_name}\"")
                    st_name = original_st_name
                
                normalized_subtags.append({"name": st_name})
        else:
            # 新标签，保持原样
            normalized_subtags = subtags
        
        normalized_tags.append({
            "name": tag_name,
            "subtags": normalized_subtags
        })
    
    return normalized_tags


def update_tags_with_new(tags_data: list, tag_index: dict, new_tags: list) -> tuple:
    """
    检查并更新标签体系
    返回: (是否有更新, 新增的标签列表, 新增的子标签列表)
    """
    updated = False
    new_tag_names = []
    new_subtag_names = []
    norm_to_original = tag_index.get("__norm_to_original__", {})
    
    for tag_item in new_tags:
        tag_name = tag_item.get("name", "")
        subtags = tag_item.get("subtags", [])
        
        if not tag_name:
            continue
        
        tag_norm = normalize_name(tag_name)
        
        # 检查主标签是否存在（包括模糊匹配）
        if tag_name not in tag_index and tag_name != "__norm_to_original__":
            # 检查是否有模糊匹配
            if tag_norm in norm_to_original:
                # 已存在的标签，跳过添加新标签
                continue
            
            # 新的主标签
            new_tag = {
                "name": tag_name,
                "description": f"{tag_name} 相关功能",
                "subtags": []
            }
            
            subtag_norm_map = {}
            # 添加子标签
            for st in subtags:
                st_name = st.get("name", "")
                if st_name:
                    new_tag["subtags"].append({
                        "name": st_name,
                        "description": st_name
                    })
                    subtag_norm_map[normalize_name(st_name)] = st_name
                    new_subtag_names.append(f"{tag_name}/{st_name}")
            
            tags_data.append(new_tag)
            tag_index[tag_name] = {
                "index": len(tags_data) - 1,
                "subtags": {st.get("name", "") for st in subtags if st.get("name")},
                "subtag_norm_map": subtag_norm_map
            }
            # 更新标准化映射
            norm_to_original[tag_norm] = tag_name
            new_tag_names.append(tag_name)
            updated = True
        elif tag_name in tag_index and tag_name != "__norm_to_original__":
            # 主标签存在，检查子标签
            existing_subtags = tag_index[tag_name]["subtags"]
            subtag_norm_map = tag_index[tag_name].get("subtag_norm_map", {})
            tag_idx = tag_index[tag_name]["index"]
            
            for st in subtags:
                st_name = st.get("name", "")
                if not st_name:
                    continue
                
                st_norm = normalize_name(st_name)
                
                # 检查子标签是否存在（包括模糊匹配）
                if st_name not in existing_subtags and st_norm not in subtag_norm_map:
                    # 新的子标签
                    tags_data[tag_idx]["subtags"].append({
                        "name": st_name,
                        "description": st_name
                    })
                    tag_index[tag_name]["subtags"].add(st_name)
                    subtag_norm_map[st_norm] = st_name
                    new_subtag_names.append(f"{tag_name}/{st_name}")
                    updated = True
    
    return updated, new_tag_names, new_subtag_names


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
    解析 LLM 响应
    返回: (tags列表, 是否解析成功, 错误信息)
    """
    if not response:
        return [], False, "响应为空"
    
    # 尝试直接解析
    try:
        data = json.loads(response)
        tags = data.get("tags", [])
        if validate_tags_format(tags):
            return tags, True, None
        else:
            return [], False, "tags 格式不正确"
    except json.JSONDecodeError:
        pass
    
    # 尝试从代码块中提取
    json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response, re.DOTALL)
    if json_match:
        try:
            data = json.loads(json_match.group(1))
            tags = data.get("tags", [])
            if validate_tags_format(tags):
                return tags, True, None
        except json.JSONDecodeError:
            pass
    
    # 尝试找到 JSON 对象 - 更宽松的匹配
    json_match = re.search(r'\{\s*"tags"\s*:\s*\[.*?\]\s*\}', response, re.DOTALL)
    if json_match:
        try:
            data = json.loads(json_match.group(0))
            tags = data.get("tags", [])
            if validate_tags_format(tags):
                return tags, True, None
        except json.JSONDecodeError:
            pass
    
    return [], False, "无法解析 JSON"


def validate_tags_format(tags: list) -> bool:
    """验证 tags 格式是否正确"""
    if not isinstance(tags, list):
        return False
    
    for tag in tags:
        if not isinstance(tag, dict):
            return False
        if "name" not in tag:
            return False
        if not isinstance(tag.get("name"), str):
            return False
        
        subtags = tag.get("subtags", [])
        if not isinstance(subtags, list):
            return False
        
        for subtag in subtags:
            if not isinstance(subtag, dict):
                return False
            if "name" not in subtag:
                return False
    
    return True


def build_prompt(title: str, description: str, tags_data: list) -> str:
    """构建打标提示词"""
    tags_json = json.dumps(tags_data, ensure_ascii=False, indent=2)
    
    prompt = f"""你是一个竞品分析专家，负责为竞品的功能更新进行分类打标。

## 现有标签体系

{tags_json}

## 待打标的功能

- **标题**: {title}
- **描述**: {description}

## 任务

请从现有标签体系中选择最合适的标签（tag）和子标签（subtag）。

## 输出要求

直接输出 JSON，不要其他内容：

```json
{{
    "tags": [
        {{
            "name": "标签名称",
            "subtags": [
                {{"name": "子标签1"}},
                {{"name": "子标签2"}}
            ]
        }}
    ]
}}
```

## 规则

1. 优先使用现有标签和子标签
2. 可以选择多个 tag
3. subtag 应该是功能涉及的具体主体（服务名、模型名等）
4. 如果现有子标签没有匹配项，可以留空 subtags 数组
5. 如果功能涉及新的具体主体（如新的第三方服务），可以添加新的 subtag

请直接输出 JSON："""
    
    return prompt


def tag_single_feature(title: str, description: str, config: dict, tags_data: list, tag_index: dict) -> tuple:
    """
    为单个功能打标，支持重试和标签名称标准化
    
    返回: (tags, success)
        - (tags, True): 成功打标，tags 是标签列表
        - ([], True): LLM 判断为非功能性内容
        - (None, False): 调用失败，需要下次重试
    """
    prompt = build_prompt(title, description, tags_data)
    
    for attempt in range(MAX_RETRIES):
        # 调用 LLM
        response = call_llm_with_retry(prompt, config, max_retries=1)  # 网络重试在 call_llm_with_retry 中处理
        
        if not response:
            if attempt < MAX_RETRIES - 1:
                print(f"       ⚠️ 响应为空，重试 {attempt + 2}/{MAX_RETRIES}...")
                time.sleep(RETRY_DELAY)
                continue
            print(f"       ❌ LLM 调用失败")
            return (None, False)  # 调用失败
        
        # 解析响应
        tags, success, error = parse_llm_response(response)
        
        if success:
            if tags:
                # 标准化标签名称（修正空格、大小写差异）
                normalized_tags = normalize_llm_tags(tags, tag_index)
                return (normalized_tags, True)
            else:
                # LLM 返回空标签，说明是非功能性内容
                return ([], True)
        
        if not success:
            if attempt < MAX_RETRIES - 1:
                print(f"       ⚠️ JSON 解析失败 ({error})，重试 {attempt + 2}/{MAX_RETRIES}...")
                time.sleep(RETRY_DELAY)
                continue
            else:
                print(f"       ❌ JSON 解析失败: {error}")
                return (None, False)  # 解析失败
    
    return (None, False)  # 所有重试都失败


def process_all_features(use_llm: bool = True, limit_per_file: int = None, target_file: str = None):
    """
    处理功能更新
    
    Args:
        use_llm: 是否使用 LLM 打标
        limit_per_file: 每个文件最多处理条数
        target_file: 只处理指定文件 (如: v0.json)
    """
    project_root = Path(__file__).parent.parent
    storage_dir = project_root / "storage"
    
    config = load_config()
    tags_data = load_tags()
    tag_index = get_tag_index(tags_data)
    
    total_processed = 0
    total_tagged = 0
    total_skipped = 0
    all_new_tags = []
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
        
        # 找出需要打标的功能（tags 字段不存在的才需要打标）
        # tags: "None" 表示已处理过但判定为非功能性内容，不需要再处理
        # tags: [...] 表示已打标，不需要再处理
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
            
            print(f"    {total_processed + 1}. {title[:40]}...")
            
            if use_llm:
                tags, success = tag_single_feature(title, description, config, tags_data, tag_index)
                time.sleep(0.5)  # 避免请求过快
            else:
                tags, success = [], True
            
            if not success:
                # LLM 调用失败，不设置 tags，下次会重试
                print(f"       ⏭️ 跳过，等待下次重试")
                total_processed += 1
                continue
            
            if tags:
                features[idx]["tags"] = tags
                tagged_count += 1
                print(f"       ✓ {len(tags)} 个标签")
                
                # 检查并更新标签体系
                updated, new_tags, new_subtags = update_tags_with_new(
                    tags_data, tag_index, tags
                )
                if new_tags:
                    print(f"       🆕 新增主标签: {', '.join(new_tags)}")
                    all_new_tags.extend(new_tags)
                if new_subtags:
                    print(f"       🆕 新增子标签: {', '.join(new_subtags)}")
                    all_new_subtags.extend(new_subtags)
                
                # 有新标签则立即保存标签体系
                if updated:
                    save_tags(tags_data)
            else:
                # LLM 成功返回但标签为空，说明是非功能性内容
                features[idx]["tags"] = "None"
                skipped_count += 1
                print(f"       ○ 非功能性内容，跳过")
            
            # 每处理一条就立即保存，防止中断丢失
            with open(json_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            
            total_processed += 1
        
        print(f"  已处理 {len(features_to_tag)} 条，打标 {tagged_count} 条，跳过 {skipped_count} 条")
        total_tagged += tagged_count
        total_skipped += skipped_count
    
    # 保存更新后的标签体系
    if all_new_tags or all_new_subtags:
        save_tags(tags_data)
        print(f"\n📝 标签体系已更新:")
        if all_new_tags:
            print(f"   新增主标签 ({len(all_new_tags)}): {', '.join(all_new_tags)}")
        if all_new_subtags:
            print(f"   新增子标签 ({len(all_new_subtags)}): {', '.join(all_new_subtags)}")
    
    print(f"\n{'='*50}")
    print(f"总计处理 {total_processed} 条功能更新")
    print(f"  ✓ 成功打标: {total_tagged} 条")
    print(f"  ○ 非功能性跳过: {total_skipped} 条")
    print(f"{'='*50}")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="LLM 打标脚本")
    parser.add_argument("--limit", type=int, default=None, help="每个文件最多处理多少条")
    parser.add_argument("--dry-run", action="store_true", help="只显示需要打标的条目，不实际调用 LLM")
    parser.add_argument("--file", type=str, default=None, help="只处理指定文件 (如: v0.json)")
    
    args = parser.parse_args()
    
    print("=" * 50)
    print("LLM 功能更新打标")
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
