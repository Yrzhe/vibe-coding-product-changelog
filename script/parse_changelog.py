#!/usr/bin/env python3
"""
解析 YouWare Changelog Markdown 文件为 JSON 格式
支持增量更新和自动打标
"""

import json
import re
from datetime import datetime
from pathlib import Path


def get_project_root():
    """获取项目根目录（支持本地和 Docker 环境）"""
    script_dir = Path(__file__).parent
    if script_dir == Path("/app"):
        return Path("/app")
    return script_dir.parent


def parse_date(date_str: str) -> str:
    """解析日期字符串为 YYYY-MM-DD 格式"""
    if not date_str:
        return ""
    
    date_str = date_str.strip()
    
    # 尝试解析 "January 12, 2026" 格式
    try:
        dt = datetime.strptime(date_str, "%B %d, %Y")
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        pass
    
    # 尝试解析 "Jan 12, 2026" 格式
    try:
        dt = datetime.strptime(date_str, "%b %d, %Y")
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        pass
    
    return date_str


def parse_changelog_markdown(content: str) -> list:
    """
    解析 Markdown 格式的 changelog 为 feature 列表
    
    格式示例：
    ## v2.7.4 – January 12, 2026
    ### Features
    #### Feature Title
    Feature description...
    ### Patches
    - Fixed something
    """
    features = []
    
    # 按版本块分割
    version_pattern = r'^## (v[\d.]+)\s*[–-]\s*(.+)$'
    
    lines = content.split('\n')
    current_version = ''
    current_date = ''
    current_category = ''
    current_title = ''
    current_description = []
    in_feature_block = False
    
    def save_current_feature():
        nonlocal current_title, current_description, in_feature_block
        if current_title:
            desc = '\n'.join(current_description).strip()
            features.append({
                'title': current_title,
                'description': desc,
                'time': current_date,
                'version': current_version,
                'category': current_category
            })
        current_title = ''
        current_description = []
        in_feature_block = False
    
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        
        # 检测版本号行
        version_match = re.match(version_pattern, stripped)
        if version_match:
            save_current_feature()
            current_version = version_match.group(1)
            current_date = parse_date(version_match.group(2))
            current_category = ''
            i += 1
            continue
        
        # 检测分类行 (### Features, ### Patches 等)
        if stripped.startswith('### '):
            save_current_feature()
            current_category = stripped[4:].strip()
            i += 1
            continue
        
        # 检测功能标题行 (#### Title)
        if stripped.startswith('#### '):
            save_current_feature()
            current_title = stripped[5:].strip()
            in_feature_block = True
            i += 1
            continue
        
        # 检测列表项 (- Item)
        if stripped.startswith('- '):
            save_current_feature()
            item_text = stripped[2:].strip()
            
            # 检查是否是 **标题:** 格式
            bold_match = re.match(r'\*\*(.+?):\*\*\s*(.+)', item_text)
            if bold_match:
                current_title = bold_match.group(1).strip()
                current_description = [bold_match.group(2).strip()]
            else:
                # 普通列表项，整行作为标题
                current_title = item_text
                current_description = []
            
            in_feature_block = True
            i += 1
            continue
        
        # 累积描述内容
        if in_feature_block and stripped:
            # 跳过分隔线
            if stripped == '---':
                save_current_feature()
            else:
                current_description.append(stripped)
        
        i += 1
    
    # 保存最后一个 feature
    save_current_feature()
    
    return features


def load_existing_tags(features_path: Path) -> dict:
    """加载现有的标签数据"""
    tag_map = {}
    
    if not features_path.exists():
        return tag_map
    
    try:
        with open(features_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if len(data) >= 2:
            for feature in data[1].get('features', []):
                title = feature.get('title', '')
                tags = feature.get('tags', [])
                if title and isinstance(tags, list) and tags:
                    tag_map[title.lower()] = tags
    except:
        pass
    
    return tag_map


def parse_and_save(raw_file: Path = None, output_file: Path = None, preserve_tags: bool = True):
    """
    解析 changelog 并保存为 JSON
    
    Args:
        raw_file: 原始 markdown 文件路径
        output_file: 输出 JSON 文件路径
        preserve_tags: 是否保留已有的标签
    """
    root = get_project_root()
    
    if raw_file is None:
        raw_file = root / "storage" / "youware_changelog_raw.txt"
    
    if output_file is None:
        output_file = root / "storage" / "youware.json"
    
    # 读取原始文件
    if not raw_file.exists():
        print(f"错误: 文件不存在 {raw_file}")
        return None
    
    with open(raw_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 解析 markdown
    features = parse_changelog_markdown(content)
    print(f"解析到 {len(features)} 条功能更新")
    
    # 加载现有标签
    existing_tags = {}
    if preserve_tags:
        existing_tags = load_existing_tags(output_file)
        print(f"加载了 {len(existing_tags)} 条已有标签")
    
    # 恢复标签
    for feature in features:
        title_key = feature.get('title', '').lower()
        if title_key in existing_tags:
            feature['tags'] = existing_tags[title_key]
        
        # 移除临时字段
        feature.pop('version', None)
        feature.pop('category', None)
    
    # 按日期排序（最新在前）
    features.sort(key=lambda x: x.get('time', '0000-00-00'), reverse=True)
    
    # 构建输出数据
    output_data = [
        {
            "name": "youware",
            "url": "https://youware.app/project/zln9fqecog?enter_from=share&invite_code=FUQ800OLMY&screen_status=1",
            "is_self": True
        },
        {
            "name": "feature",
            "features": features
        }
    ]
    
    # 保存
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=4)
    
    print(f"已保存到 {output_file}")
    print(f"共 {len(features)} 条功能更新")
    
    return features


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="解析 YouWare Changelog")
    parser.add_argument(
        "--input",
        type=str,
        help="输入文件路径 (默认: storage/youware_changelog_raw.txt)"
    )
    parser.add_argument(
        "--output",
        type=str,
        help="输出文件路径 (默认: storage/youware.json)"
    )
    parser.add_argument(
        "--no-preserve-tags",
        action="store_true",
        help="不保留已有标签"
    )
    
    args = parser.parse_args()
    
    root = get_project_root()
    
    raw_file = Path(args.input) if args.input else None
    output_file = Path(args.output) if args.output else None
    
    print("=" * 50)
    print("YouWare Changelog Parser")
    print("=" * 50)
    
    parse_and_save(
        raw_file=raw_file,
        output_file=output_file,
        preserve_tags=not args.no_preserve_tags
    )


if __name__ == "__main__":
    main()
