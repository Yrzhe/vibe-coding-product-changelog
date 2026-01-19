#!/usr/bin/env python3
"""
Replit Changelog Crawler
爬取 https://docs.replit.com/updates/ 的功能更新数据
Replit 使用分页结构，每周一个页面
"""

import json
import re
from datetime import datetime
from pathlib import Path
from playwright.sync_api import sync_playwright


def parse_date(date_str: str) -> str:
    """
    将日期字符串解析为 YYYY-MM-DD 格式
    支持格式: "January 09, 2026", "December 26, 2025" 等
    """
    if not date_str:
        return ""
    
    date_str = date_str.strip()
    
    formats = [
        "%B %d, %Y",     # January 09, 2026
        "%B %d %Y",      # January 09 2026
        "%b %d, %Y",     # Jan 09, 2026
        "%b %d %Y",      # Jan 09 2026
    ]
    
    for fmt in formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    
    return ""


def extract_date_from_url(url: str) -> str:
    """从 URL 中提取日期"""
    # URL 格式: /updates/2026/01/09/changelog
    match = re.search(r'/updates/(\d{4})/(\d{2})/(\d{2})/', url)
    if match:
        return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
    return ""


def crawl_replit_changelog():
    """爬取 Replit changelog 页面"""
    base_url = "https://docs.replit.com/updates/"
    features = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        print(f"正在访问 {base_url}...")
        page.goto(base_url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(5000)
        
        # 获取所有日期页面的链接
        date_links = page.evaluate("""
            () => {
                const links = [];
                const seen = new Set();
                
                document.querySelectorAll('a[href*="/updates/"]').forEach(a => {
                    const href = a.getAttribute('href');
                    if (href && href.match(/\\/updates\\/\\d{4}\\/\\d{2}\\/\\d{2}\\/changelog/)) {
                        if (!seen.has(href)) {
                            seen.add(href);
                            links.push({
                                url: 'https://docs.replit.com' + href,
                                text: a.innerText.trim()
                            });
                        }
                    }
                });
                
                return links;
            }
        """)
        
        print(f"找到 {len(date_links)} 个更新页面")
        
        # 处理所有更新页面
        for link_info in date_links:
            try:
                url = link_info['url']
                date_text = link_info['text']
                
                # 优先从 URL 提取日期
                parsed_date = extract_date_from_url(url)
                if not parsed_date:
                    parsed_date = parse_date(date_text)
                
                # 跳过无效日期
                if not parsed_date or not re.match(r'\d{4}-\d{2}-\d{2}', parsed_date):
                    continue
                
                print(f"  正在爬取 {parsed_date} ({date_text})...")
                
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(2000)
                
                # 提取该页面的所有功能
                page_features = page.evaluate("""
                    () => {
                        const features = [];
                        const seen = new Set();
                        
                        // 查找所有 h3 标题
                        document.querySelectorAll('h3').forEach(h3 => {
                            const titleEl = h3.querySelector('[class*="cursor-pointer"]') || h3;
                            let title = titleEl.innerText?.trim();
                            
                            // 清理标题
                            title = title.replace('Navigate to header', '').trim();
                            
                            if (!title || title.length < 3 || seen.has(title)) return;
                            // 跳过分类标题
                            if (["What's new", "Platform", "Agent", "Core Agent", "Changelog"].includes(title)) return;
                            seen.add(title);
                            
                            // 获取描述
                            let desc = [];
                            let next = h3.nextElementSibling;
                            let count = 0;
                            
                            while (next && count < 5) {
                                if (next.matches('h2, h3')) break;
                                const txt = next.innerText?.trim();
                                if (txt && !txt.startsWith('Navigate')) {
                                    desc.push(txt);
                                }
                                next = next.nextElementSibling;
                                count++;
                            }
                            
                            features.push({
                                title: title,
                                description: desc.join('\\n').substring(0, 2000)
                            });
                        });
                        
                        return features;
                    }
                """)
                
                for feat in page_features:
                    features.append({
                        "title": feat['title'],
                        "description": feat['description'],
                        "time": parsed_date,
                        "tags": []
                    })
                    print(f"    ✓ {feat['title'][:50]}...")
                    
            except Exception as e:
                print(f"    ✗ 爬取失败: {e}")
                continue
        
        browser.close()
    
    print(f"\n总共获取 {len(features)} 条功能更新")
    return features


def get_storage_dir():
    """获取 storage 目录（支持本地和 Docker 环境）"""
    script_dir = Path(__file__).parent
    
    # Docker 环境: /app/crawl/xxx.py -> storage 在 /app/storage
    if script_dir == Path("/app/crawl"):
        return Path("/app/storage")
    
    # 本地环境: script/crawl/xxx.py -> storage 在 ../../storage
    return script_dir.parent.parent / "storage"


def save_data(features: list):
    """保存数据到 storage/replit.json"""
    storage_dir = get_storage_dir()
    storage_dir.mkdir(exist_ok=True)
    
    output_data = [
        {
            "name": "replit",
            "url": "https://docs.replit.com/updates/"
        },
        {
            "name": "feature",
            "features": features
        }
    ]
    
    output_path = storage_dir / "replit.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=4)
    
    print(f"数据已保存到 {output_path}")
    print(f"共 {len(features)} 条功能更新")


def main():
    print("=" * 50)
    print("Replit Changelog Crawler")
    print("=" * 50)
    
    features = crawl_replit_changelog()
    
    if features:
        save_data(features)
    else:
        print("未获取到任何数据")


if __name__ == "__main__":
    main()
