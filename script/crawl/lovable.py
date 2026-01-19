#!/usr/bin/env python3
"""
Lovable Changelog Crawler
爬取 https://docs.lovable.dev/changelog 的功能更新数据
确保获取所有历史数据（从 Dec 3, 2024 开始）
"""

import json
import re
from datetime import datetime
from pathlib import Path
from playwright.sync_api import sync_playwright


def parse_date_from_id(date_id: str) -> str:
    """
    将日期 ID 解析为 YYYY-MM-DD 格式
    例如: dec-23,-2025 -> 2025-12-23
    """
    if not date_id:
        return ""
    
    # 清理并解析
    date_id = date_id.lower().replace(",", "").replace("-", " ").strip()
    # dec 23 2025
    
    month_map = {
        'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4,
        'may': 5, 'jun': 6, 'jul': 7, 'aug': 8,
        'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
    }
    
    parts = date_id.split()
    if len(parts) >= 3:
        month_str = parts[0]
        day_str = parts[1]
        year_str = parts[2]
        
        month = month_map.get(month_str[:3], 0)
        if month and day_str.isdigit() and year_str.isdigit():
            return f"{year_str}-{month:02d}-{int(day_str):02d}"
    
    return ""


def crawl_lovable_changelog():
    """爬取 Lovable changelog 页面"""
    url = "https://docs.lovable.dev/changelog"
    features = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        print(f"正在访问 {url}...")
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(3000)
        
        # 滚动加载所有内容
        print("滚动加载所有内容...")
        last_height = 0
        no_change_count = 0
        
        for scroll_round in range(100):
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(500)
            
            new_height = page.evaluate("document.body.scrollHeight")
            
            if new_height == last_height:
                no_change_count += 1
                if no_change_count >= 3:
                    print(f"  页面加载完成 (滚动 {scroll_round + 1} 次)")
                    break
            else:
                no_change_count = 0
                last_height = new_height
        
        page.evaluate("window.scrollTo(0, 0)")
        page.wait_for_timeout(1000)
        
        # 提取数据 - 基于日期区块结构
        print("提取功能更新数据...")
        data = page.evaluate("""
            () => {
                const features = [];
                const seen = new Set();
                
                // 获取所有日期区块（ID 包含日期格式的 DIV）
                const dateBlocks = document.querySelectorAll('div[id*="%2C-"]');
                
                dateBlocks.forEach(block => {
                    const dateId = decodeURIComponent(block.id);
                    
                    // 获取此区块内的所有 h3 标题
                    const h3s = block.querySelectorAll('h3');
                    
                    h3s.forEach(h3 => {
                        const strongEl = h3.querySelector('strong');
                        if (!strongEl) return;
                        
                        const title = strongEl.innerText?.trim();
                        if (!title || title.length < 3 || seen.has(title)) return;
                        seen.add(title);
                        
                        // 获取描述 - h3 后面的内容
                        let desc = [];
                        let next = h3.nextElementSibling;
                        let count = 0;
                        
                        while (next && count < 15) {
                            // 如果遇到下一个 h3，停止
                            if (next.matches('h3') || next.querySelector('h3')) break;
                            const txt = next.innerText?.trim();
                            if (txt && !txt.startsWith('Navigate') && txt.length > 5) {
                                desc.push(txt);
                            }
                            next = next.nextElementSibling;
                            count++;
                        }
                        
                        features.push({
                            title: title,
                            description: desc.join('\\n').substring(0, 2000),
                            dateId: dateId
                        });
                    });
                    
                    // 还要获取区块内的列表项（一些更新是以列表形式呈现的）
                    const lists = block.querySelectorAll('ul > li');
                    lists.forEach(li => {
                        // 跳过已经作为 h3 处理过的
                        if (li.querySelector('h3')) return;
                        
                        const text = li.innerText?.trim();
                        if (!text || text.length < 20) return;
                        
                        // 检查是否是功能更新描述（通常较长）
                        const firstLine = text.split('\\n')[0].trim();
                        if (firstLine.length < 10 || seen.has(firstLine)) return;
                        
                        let title = firstLine;
                        if (title.length > 100) {
                            title = title.substring(0, 100) + '...';
                        }
                        
                        seen.add(firstLine);
                        features.push({
                            title: title,
                            description: text,
                            dateId: dateId
                        });
                    });
                });
                
                return features;
            }
        """)
        
        print(f"找到 {len(data)} 条功能更新")
        
        # 处理日期
        for item in data:
            date_str = parse_date_from_id(item.get('dateId', ''))
            feature = {
                'title': item['title'],
                'description': item['description'],
                'time': date_str,
                'tags': []
            }
            features.append(feature)
            date_display = date_str if date_str else '(无日期)'
            print(f"  ✓ {date_display}: {item['title'][:50]}...")
        
        browser.close()
    
    # 按日期排序（最新在前）
    features.sort(key=lambda x: x['time'] if x['time'] else '0000-00-00', reverse=True)
    
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
    """保存数据"""
    storage_dir = get_storage_dir()
    storage_dir.mkdir(exist_ok=True)
    
    output_data = [
        {"name": "lovable", "url": "https://docs.lovable.dev/changelog"},
        {"name": "feature", "features": features}
    ]
    
    output_path = storage_dir / "lovable.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=4)
    
    print(f"\n数据已保存到 {output_path}")
    print(f"共 {len(features)} 条功能更新")


def main():
    print("=" * 50)
    print("Lovable Changelog Crawler")
    print("=" * 50)
    
    features = crawl_lovable_changelog()
    
    if features:
        save_data(features)
    else:
        print("未获取到任何数据")


if __name__ == "__main__":
    main()
