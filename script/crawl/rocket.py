#!/usr/bin/env python3
"""
Rocket.new Changelog Crawler
爬取 https://docs.rocket.new/inspiration-and-help/changelog 的功能更新数据
"""

import json
import re
from datetime import datetime
from pathlib import Path
from playwright.sync_api import sync_playwright


def parse_date(date_str: str) -> str:
    """解析日期字符串"""
    if not date_str:
        return ""
    
    date_str = date_str.strip()
    
    # 已经是 YYYY-MM-DD 格式
    if re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
        return date_str
    
    return date_str


def crawl_rocket_changelog():
    """爬取 Rocket changelog 页面"""
    url = "https://docs.rocket.new/inspiration-and-help/changelog"
    features = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        print(f"正在访问 {url}...")
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(5000)
        
        # 滚动加载 - 需要多次滚动到页面底部
        for _ in range(40):
            page.evaluate("window.scrollBy(0, 2000)")
            page.wait_for_timeout(300)
        
        page.evaluate("window.scrollTo(0, 0)")
        page.wait_for_timeout(1000)
        
        # 提取数据 - 同时处理 h4 和 strong 标签
        data = page.evaluate("""
            () => {
                const features = [];
                const seen = new Set();
                
                // 方法1: 查找所有 h4 标题 - 新版格式
                const h4s = document.querySelectorAll('h4');
                
                h4s.forEach(h4 => {
                    const titleEl = h4.querySelector('[class*="cursor-pointer"]') || h4;
                    let title = titleEl.innerText?.trim() || '';
                    title = title.replace('Navigate to header', '').trim();
                    
                    if (!title || title.length < 3 || seen.has(title)) return;
                    seen.add(title);
                    
                    // 向上查找日期
                    let dateText = '';
                    let parent = h4.parentElement;
                    let maxUp = 10;
                    
                    while (parent && maxUp > 0) {
                        const prevSibling = parent.previousElementSibling;
                        if (prevSibling) {
                            const dateLink = prevSibling.querySelector('a[href^="#20"]');
                            if (dateLink) {
                                const dateSpan = prevSibling.querySelector('[class*="cursor-pointer"]');
                                if (dateSpan) {
                                    const text = dateSpan.innerText.trim();
                                    if (text.match(/^\\d{4}-\\d{2}-\\d{2}$/)) {
                                        dateText = text;
                                        break;
                                    }
                                }
                            }
                        }
                        parent = parent.parentElement;
                        maxUp--;
                    }
                    
                    // 获取描述
                    let desc = [];
                    let next = h4.nextElementSibling;
                    let count = 0;
                    
                    while (next && count < 10) {
                        if (next.matches('h3, h4') || next.querySelector('h4')) break;
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
                        time: dateText,
                        tags: []
                    });
                });
                
                // 方法2: 查找所有日期区块 - 处理老版格式（没有 h4 的情况）
                const dateLinks = document.querySelectorAll('a[href^="#20"]');
                
                dateLinks.forEach(dateLink => {
                    const href = dateLink.getAttribute('href') || '';
                    const dateMatch = href.match(/#(\\d{4}-\\d{2}-\\d{2})/);
                    if (!dateMatch) return;
                    
                    const dateText = dateMatch[1];
                    
                    // 检查这个日期是否已经有 h4 功能
                    const hasH4Features = features.some(f => f.time === dateText);
                    if (hasH4Features) return;
                    
                    const dateContainer = dateLink.parentElement;
                    if (!dateContainer) return;
                    
                    const featuresContainer = dateContainer.nextElementSibling;
                    if (!featuresContainer) return;
                    
                    // 查找 strong 标签作为小标题
                    const strongs = featuresContainer.querySelectorAll('strong');
                    
                    strongs.forEach(strong => {
                        let title = strong.innerText?.trim() || '';
                        if (!title || title.length < 3 || seen.has(title + dateText)) return;
                        // 跳过分类标题
                        if (['New Features', 'Enhancements', 'Bug Fixes', 'Feature Completion'].includes(title)) return;
                        seen.add(title + dateText);
                        
                        // 获取描述 - strong 后面的 list
                        let desc = [];
                        let next = strong.nextElementSibling;
                        
                        if (next && next.matches('ul, ol')) {
                            const items = next.querySelectorAll('li');
                            items.forEach(li => {
                                const txt = li.innerText?.trim();
                                if (txt) desc.push('• ' + txt);
                            });
                        }
                        
                        features.push({
                            title: title,
                            description: desc.join('\\n').substring(0, 2000),
                            time: dateText,
                            tags: []
                        });
                    });
                });
                
                // 按日期排序
                features.sort((a, b) => {
                    if (!a.time) return 1;
                    if (!b.time) return -1;
                    return b.time.localeCompare(a.time);
                });
                
                return features;
            }
        """)
        
        print(f"找到 {len(data)} 条功能更新")
        
        for item in data:
            item['time'] = parse_date(item.get('time', ''))
            features.append(item)
            date_display = item['time'] if item['time'] else '(无日期)'
            print(f"  ✓ {date_display}: {item['title'][:50]}...")
        
        browser.close()
    
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
        {"name": "rocket", "url": "https://docs.rocket.new/inspiration-and-help/changelog"},
        {"name": "feature", "features": features}
    ]
    
    output_path = storage_dir / "rocket.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=4)
    
    print(f"\n数据已保存到 {output_path}")
    print(f"共 {len(features)} 条功能更新")


def main():
    print("=" * 50)
    print("Rocket.new Changelog Crawler")
    print("=" * 50)
    
    features = crawl_rocket_changelog()
    
    if features:
        save_data(features)
    else:
        print("未获取到任何数据")


if __name__ == "__main__":
    main()
