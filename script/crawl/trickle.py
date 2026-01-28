#!/usr/bin/env python3
"""
Trickle Changelog Crawler
爬取 https://trickleai.featurebase.app/changelog 的功能更新数据
"""

import json
import re
from datetime import datetime
from pathlib import Path
from playwright.sync_api import sync_playwright


def parse_date(date_str: str) -> str:
    """
    解析日期字符串
    支持格式: "July 1st, 2025", "December 30th, 2025"
    """
    if not date_str:
        return ""
    
    date_str = date_str.strip()
    
    # 移除序数后缀 (st, nd, rd, th)
    clean_date = re.sub(r'(\d+)(st|nd|rd|th)', r'\1', date_str)
    
    formats = [
        "%B %d, %Y",    # July 1, 2025
        "%b %d, %Y",    # Jul 1, 2025
    ]
    
    for fmt in formats:
        try:
            dt = datetime.strptime(clean_date, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    
    return date_str


def crawl_trickle_changelog():
    """使用 Playwright 爬取 Trickle changelog"""
    url = "https://trickleai.featurebase.app/changelog"
    features = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={'width': 1920, 'height': 1080})
        page = context.new_page()
        
        print(f"正在访问 {url}...")
        page.goto(url, wait_until="domcontentloaded", timeout=90000)
        page.wait_for_timeout(5000)
        
        # 等待页面加载
        try:
            page.wait_for_selector("h1", timeout=15000)
            print("  页面加载成功")
        except:
            print("  警告: 页面可能未完全加载")
        
        # 滚动加载所有内容
        print("滚动加载所有内容...")
        last_link_count = 0
        no_change_count = 0
        
        for scroll_round in range(60):
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(1000)
            
            current_count = page.evaluate("""
                () => document.querySelectorAll('a[href*="/changelog/"]').length
            """)
            
            if current_count == last_link_count:
                no_change_count += 1
                if no_change_count >= 4:
                    print(f"  页面加载完成 (找到 {current_count} 个链接)")
                    break
            else:
                no_change_count = 0
                last_link_count = current_count
                if scroll_round % 5 == 0:
                    print(f"  已滚动 {scroll_round + 1} 次，找到 {current_count} 个链接")
        
        page.wait_for_timeout(1000)
        
        # 提取数据
        print("提取 changelog 数据...")
        
        entries_data = page.evaluate("""
            () => {
                const entries = [];
                const seen = new Set();
                const datePattern = /(January|February|March|April|May|June|July|August|September|October|November|December)\\s+\\d{1,2}(st|nd|rd|th)?,?\\s+\\d{4}/;
                
                // 查找所有 changelog 链接
                const links = document.querySelectorAll('a[href*="/changelog/"]');
                
                links.forEach(link => {
                    const href = link.href || '';
                    if (href.includes('feed.rss') || href.endsWith('/changelog')) return;
                    
                    // 获取标题
                    const h2 = link.querySelector('h2');
                    if (!h2) return;
                    
                    const title = h2.innerText?.trim() || '';
                    if (!title || title.length < 5 || seen.has(title)) return;
                    if (['New', 'Improvements', 'Bug Fixes', 'News', 'Changelog'].includes(title)) return;
                    
                    seen.add(title);
                    
                    // 查找日期 - 向上找到日期段落
                    let dateFound = '';
                    let container = link.closest('div');
                    let attempts = 0;
                    
                    while (container && attempts < 20) {
                        const paragraphs = container.querySelectorAll('p');
                        for (const p of paragraphs) {
                            const text = p.innerText?.trim() || '';
                            if (datePattern.test(text) && text.length < 30) {
                                dateFound = text;
                                break;
                            }
                        }
                        if (dateFound) break;
                        container = container.parentElement;
                        attempts++;
                    }
                    
                    // 获取描述 - 向上查找 2 层找到 "max-w-3xl" 容器
                    let description = '';
                    
                    // link -> parent (max-w-xl) -> parent (flex justify-between) -> parent (max-w-3xl)
                    let contentContainer = link.parentElement?.parentElement?.parentElement;
                    
                    if (contentContainer) {
                        const fullText = contentContainer.innerText || '';
                        // 去掉标题，保留描述部分
                        if (fullText.startsWith(title)) {
                            description = fullText.substring(title.length).trim();
                        } else {
                            // 找到标题位置并截取后面的内容
                            const titleIndex = fullText.indexOf(title);
                            if (titleIndex !== -1) {
                                description = fullText.substring(titleIndex + title.length).trim();
                            } else {
                                description = fullText;
                            }
                        }
                        
                        // 清理描述：移除可能的日期和"Continue Reading"
                        description = description.replace(/Continue Reading/g, '').trim();
                    }
                    
                    entries.push({
                        title: title,
                        description: description.substring(0, 3000),
                        date: dateFound
                    });
                });
                
                return entries;
            }
        """)
        
        print(f"找到 {len(entries_data)} 条条目")
        
        # 处理数据
        for entry in entries_data:
            title = entry.get('title', '').strip()
            
            feature = {
                "title": title,
                "description": entry.get('description', '').strip(),
                "time": parse_date(entry.get('date', '')),
                "tags": []
            }
            
            features.append(feature)
            date_display = feature['time'] if feature['time'] else '(无日期)'
            desc_preview = feature['description'][:50] + '...' if feature['description'] else '(无描述)'
            print(f"  ✓ {date_display}: {title[:40]}... | {desc_preview}")
        
        browser.close()
    
    # 按日期排序
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
        {"name": "trickle", "url": "https://feedback.trickle.so/changelog"},
        {"name": "feature", "features": features}
    ]
    
    output_path = storage_dir / "trickle.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=4)
    
    print(f"\n数据已保存到 {output_path}")
    print(f"共 {len(features)} 条功能更新")


def main():
    print("=" * 50)
    print("Trickle Changelog Crawler (Playwright)")
    print("=" * 50)
    
    features = crawl_trickle_changelog()
    
    if features:
        save_data(features)
    else:
        print("未获取到任何数据")


if __name__ == "__main__":
    main()
