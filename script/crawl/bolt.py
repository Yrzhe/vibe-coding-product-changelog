#!/usr/bin/env python3
"""
Bolt Changelog Crawler
爬取 https://support.bolt.new/release-notes 的功能更新数据
获取所有 New Features 和 Improvements（包括列表项）
"""

import json
import re
from datetime import datetime
from pathlib import Path
from playwright.sync_api import sync_playwright


def parse_date_range(date_str: str) -> str:
    """
    解析日期范围，返回结束日期
    支持格式: "Dec 15 - Jan 2", "Dec 8-14", "November 8- Dec 7", "June 2025", "September 2025"
    """
    if not date_str:
        return ""
    
    date_str = date_str.strip()
    
    # 处理纯月份格式 "June 2025", "September 2025"
    month_year_match = re.match(r'^([A-Za-z]+)\s+(\d{4})$', date_str)
    if month_year_match:
        return date_str  # 保留原格式
    
    # 默认年份
    year = "2025"
    if "Jan" in date_str and "2026" not in date_str:
        year = "2026"
    
    # 提取所有月份和日期
    month_day_patterns = re.findall(r'([A-Za-z]+)\s*(\d+)', date_str)
    
    if month_day_patterns:
        # 取最后一个月日组合
        month, day = month_day_patterns[-1]
        try:
            dt = datetime.strptime(f"{month} {day} {year}", "%b %d %Y")
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            try:
                dt = datetime.strptime(f"{month} {day} {year}", "%B %d %Y")
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                pass
    
    return date_str


def crawl_bolt_changelog():
    """爬取 Bolt changelog 页面"""
    url = "https://support.bolt.new/release-notes"
    features = []
    
    with sync_playwright() as p:
        # 使用 headful 模式确保页面完全加载
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        
        print(f"正在访问 {url}...")
        page.goto(url, wait_until="domcontentloaded", timeout=90000)
        page.wait_for_timeout(5000)
        
        # 滚动加载所有内容
        print("滚动加载页面内容...")
        for i in range(25):
            page.evaluate("window.scrollBy(0, 2000)")
            page.wait_for_timeout(300)
        
        page.evaluate("window.scrollTo(0, 0)")
        page.wait_for_timeout(1000)
        
        # 提取所有功能更新数据
        print("提取功能更新数据...")
        data = page.evaluate("""
            () => {
                const features = [];
                const seen = new Set();
                
                // 首先收集所有日期节点
                const dateInfo = {};
                const dateContainers = document.querySelectorAll('a[href^="#"]');
                dateContainers.forEach(link => {
                    const href = link.getAttribute('href')?.replace('#', '') || '';
                    const dateSpan = link.parentElement?.querySelector('[class*="cursor-pointer"]');
                    if (dateSpan) {
                        const text = dateSpan.innerText?.trim() || '';
                        if (text && (text.match(/[A-Za-z]+.*\\d/) || text.match(/^[A-Za-z]+\\s+\\d{4}$/))) {
                            dateInfo[href] = text;
                        }
                    }
                });
                
                // 辅助函数：查找元素对应的日期
                function findDate(element) {
                    let el = element;
                    let attempts = 0;
                    
                    while (el && attempts < 30) {
                        // 检查 id 属性
                        const id = el.id;
                        if (id && dateInfo[id]) {
                            return dateInfo[id];
                        }
                        
                        // 检查前一个兄弟的日期
                        let prev = el.previousElementSibling;
                        while (prev) {
                            const dateLink = prev.querySelector('a[href^="#"]');
                            if (dateLink) {
                                const href = dateLink.getAttribute('href')?.replace('#', '');
                                if (href && dateInfo[href]) {
                                    return dateInfo[href];
                                }
                            }
                            // 直接检查文本
                            const dateSpan = prev.querySelector('[class*="cursor-pointer"]');
                            if (dateSpan) {
                                const text = dateSpan.innerText?.trim();
                                if (text && (text.match(/[A-Za-z]+.*\\d/) || text.match(/^[A-Za-z]+\\s+\\d{4}$/))) {
                                    return text;
                                }
                            }
                            prev = prev.previousElementSibling;
                        }
                        
                        el = el.parentElement;
                        attempts++;
                    }
                    return '';
                }
                
                // 提取 h3 标题（主要功能更新）
                const h3s = document.querySelectorAll('h3');
                h3s.forEach(h3 => {
                    const titleEl = h3.querySelector('[class*="cursor-pointer"]') || h3;
                    let title = titleEl.innerText?.trim() || '';
                    title = title.replace('Navigate to header', '').trim();
                    
                    if (!title || title.length < 5 || seen.has(title)) return;
                    // 跳过分类标题
                    if (['New features', 'Improvements', 'Bug fixes', 'New features - Bolt V2'].includes(title)) return;
                    seen.add(title);
                    
                    const dateText = findDate(h3);
                    
                    // 获取描述
                    let desc = [];
                    let next = h3.nextElementSibling;
                    let count = 0;
                    
                    while (next && count < 10) {
                        if (next.matches('h2, h3') || next.querySelector('h2, h3')) break;
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
                        type: 'feature'
                    });
                });
                
                // 提取 h2 "Improvements" 下的列表项
                const h2s = document.querySelectorAll('h2');
                h2s.forEach(h2 => {
                    // 清理文本中的特殊字符
                    const h2Text = h2.innerText?.replace(/[\\u200b\\n]/g, '').replace('Navigate to header', '').trim();
                    
                    if (h2Text === 'Improvements') {
                        const dateText = findDate(h2);
                        
                        // 获取下面的列表
                        let nextEl = h2.nextElementSibling;
                        while (nextEl) {
                            const nextText = nextEl.innerText?.replace(/[\\u200b\\n]/g, '').trim();
                            // 遇到下一个 section 时停止
                            if (nextEl.matches('h2') || nextText.startsWith('New features') || nextText.startsWith('Improvements')) {
                                break;
                            }
                            
                            // 查找列表项
                            const lis = nextEl.querySelectorAll('li');
                            lis.forEach(li => {
                                const text = li.innerText?.trim();
                                if (text && text.length > 15) {
                                    // 提取第一句作为标题
                                    let title = text.split(/[.!?]/)[0].trim();
                                    if (title.length > 100) {
                                        title = title.substring(0, 100) + '...';
                                    }
                                    
                                    if (title.length >= 10 && !seen.has(title)) {
                                        seen.add(title);
                                        features.push({
                                            title: title,
                                            description: text,
                                            time: dateText,
                                            type: 'improvement'
                                        });
                                    }
                                }
                            });
                            
                            nextEl = nextEl.nextElementSibling;
                        }
                    }
                });
                
                return features;
            }
        """)
        
        print(f"找到 {len(data)} 条功能更新 (features + improvements)")
        
        # 处理日期格式
        for item in data:
            item['time'] = parse_date_range(item.get('time', ''))
            item['tags'] = []
            del item['type']  # 移除临时字段
            features.append(item)
            date_display = item['time'] if item['time'] else '(无日期)'
            print(f"  ✓ {date_display}: {item['title'][:50]}...")
        
        browser.close()
    
    # 按日期排序
    def sort_key(x):
        t = x.get('time', '')
        if not t:
            return '0000-00-00'
        # 处理 "June 2025" 格式
        if re.match(r'^[A-Za-z]+\s+\d{4}$', t):
            try:
                dt = datetime.strptime(t, "%B %Y")
                return dt.strftime("%Y-%m-01")
            except:
                return t
        return t
    
    features.sort(key=sort_key, reverse=True)
    
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
        {"name": "bolt", "url": "https://support.bolt.new/release-notes"},
        {"name": "feature", "features": features}
    ]
    
    output_path = storage_dir / "bolt.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=4)
    
    print(f"\n数据已保存到 {output_path}")
    print(f"共 {len(features)} 条功能更新")


def main():
    print("=" * 50)
    print("Bolt Changelog Crawler")
    print("=" * 50)
    
    features = crawl_bolt_changelog()
    
    if features:
        save_data(features)
    else:
        print("未获取到任何数据")


if __name__ == "__main__":
    main()
