#!/usr/bin/env python3
"""
v0 Changelog Crawler
爬取 https://v0.app/changelog 的功能更新数据
"""

import json
import re
from datetime import datetime
from pathlib import Path
from playwright.sync_api import sync_playwright


def parse_date(date_str: str) -> str:
    """
    将日期字符串解析为 YYYY-MM-DD 格式
    支持格式: "Jan 8, 2026", "Dec 22, 2025" 等
    """
    try:
        dt = datetime.strptime(date_str.strip(), "%b %d, %Y")
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        # 尝试其他格式
        try:
            dt = datetime.strptime(date_str.strip(), "%B %d, %Y")
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            return date_str


def extract_text_content(element) -> str:
    """提取元素的文本内容，处理嵌套结构"""
    return element.inner_text().strip()


def crawl_v0_changelog():
    """爬取 v0 changelog 页面"""
    url = "https://v0.app/changelog"
    features = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        print(f"正在访问 {url}...")
        page.goto(url, wait_until="networkidle")
        
        # 等待页面加载完成
        page.wait_for_selector("main", timeout=10000)
        
        # 获取所有 article 元素
        articles = page.query_selector_all("main article")
        print(f"找到 {len(articles)} 个功能更新条目")
        
        for article in articles:
            try:
                # 提取日期
                time_elem = article.query_selector("time")
                date_str = time_elem.inner_text() if time_elem else ""
                parsed_date = parse_date(date_str)
                
                # 提取标题 (h2)
                title_elem = article.query_selector("h2")
                title = title_elem.inner_text().strip() if title_elem else ""
                
                # 提取描述内容
                description_parts = []
                
                # 获取段落内容
                paragraphs = article.query_selector_all("p")
                for p in paragraphs:
                    text = p.inner_text().strip()
                    if text:
                        description_parts.append(text)
                
                # 获取列表内容
                list_items = article.query_selector_all("li")
                for li in list_items:
                    text = li.inner_text().strip()
                    if text:
                        description_parts.append(f"• {text}")
                
                description = "\n".join(description_parts)
                
                if title:  # 只添加有标题的条目
                    features.append({
                        "title": title,
                        "description": description,
                        "time": parsed_date,
                        "tags": []
                    })
                    print(f"  ✓ {parsed_date}: {title[:50]}...")
                    
            except Exception as e:
                print(f"  ✗ 解析失败: {e}")
                continue
        
        browser.close()
    
    return features


def save_data(features: list):
    """保存数据到 storage/v0.json"""
    # 获取项目根目录
    script_dir = Path(__file__).parent
    project_root = script_dir.parent.parent
    storage_dir = project_root / "storage"
    
    # 确保 storage 目录存在
    storage_dir.mkdir(exist_ok=True)
    
    # 构建输出数据结构
    output_data = [
        {
            "name": "v0",
            "url": "https://v0.app/changelog"
        },
        {
            "name": "feature",
            "features": features
        }
    ]
    
    output_path = storage_dir / "v0.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=4)
    
    print(f"\n数据已保存到 {output_path}")
    print(f"共 {len(features)} 条功能更新")


def main():
    print("=" * 50)
    print("v0 Changelog Crawler")
    print("=" * 50)
    
    features = crawl_v0_changelog()
    
    if features:
        save_data(features)
    else:
        print("未获取到任何数据")


if __name__ == "__main__":
    main()
