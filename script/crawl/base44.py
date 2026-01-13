#!/usr/bin/env python3
"""
Base44 Changelog Crawler
爬取 https://base44.com/changelog 的功能更新数据
点击每个 Read more 链接获取完整描述
"""

import json
import re
from datetime import datetime
from pathlib import Path
from playwright.sync_api import sync_playwright


def parse_month_year(month_year: str) -> str:
    """
    将月份年份转换为日期 (取该月1日)
    支持格式: "January 2026", "December 2025"
    """
    if not month_year:
        return ""
    
    month_year = month_year.strip()
    
    formats = [
        "%B %Y",      # January 2026
        "%b %Y",      # Jan 2026
    ]
    
    for fmt in formats:
        try:
            dt = datetime.strptime(month_year, fmt)
            return dt.strftime("%Y-%m-01")
        except ValueError:
            continue
    
    return month_year


def crawl_base44_changelog():
    """爬取 Base44 changelog 页面"""
    url = "https://base44.com/changelog"
    features = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        print(f"正在访问 {url}...")
        page.goto(url, wait_until="domcontentloaded", timeout=90000)
        page.wait_for_timeout(5000)
        
        # 滚动加载所有内容
        print("滚动加载页面内容...")
        for i in range(15):
            page.evaluate("window.scrollBy(0, 2000)")
            page.wait_for_timeout(400)
        
        page.evaluate("window.scrollTo(0, 0)")
        page.wait_for_timeout(1000)
        
        # 首先收集所有条目的基本信息和详情链接
        print("收集所有 changelog 条目...")
        entries = page.evaluate("""
            () => {
                const entries = [];
                const seen = new Set();
                let currentMonth = '';
                
                // 遍历页面内容，查找月份和条目
                const allElements = document.querySelectorAll('*');
                
                allElements.forEach(el => {
                    const text = el.innerText?.trim() || '';
                    
                    // 检查是否是月份格式
                    if (/^(January|February|March|April|May|June|July|August|September|October|November|December)\\s+\\d{4}$/.test(text)) {
                        currentMonth = text;
                    }
                });
                
                // 查找所有 Read more 链接
                const readMoreLinks = document.querySelectorAll('a[href*="/changelog/feature/"]');
                
                readMoreLinks.forEach(link => {
                    const href = link.href;
                    
                    // 获取标题 - 查找附近的文本
                    let title = '';
                    let parent = link.parentElement;
                    let attempts = 0;
                    
                    while (parent && attempts < 5) {
                        // 查找同级或父级的标题元素
                        const siblings = parent.querySelectorAll('p, span, h1, h2, h3, h4');
                        for (const sib of siblings) {
                            const sibText = sib.innerText?.trim();
                            if (sibText && 
                                sibText.length > 3 && 
                                sibText.length < 200 &&
                                sibText !== 'Read more' && 
                                sibText !== 'New Releases' && 
                                sibText !== 'Improvements' &&
                                sibText !== 'Bug Fixes' &&
                                !/^(January|February|March|April|May|June|July|August|September|October|November|December)/.test(sibText)) {
                                title = sibText;
                                break;
                            }
                        }
                        if (title) break;
                        parent = parent.parentElement;
                        attempts++;
                    }
                    
                    // 查找日期 - 在父元素中查找月份格式
                    let month = '';
                    parent = link.parentElement;
                    attempts = 0;
                    
                    while (parent && attempts < 10) {
                        const monthPattern = /(January|February|March|April|May|June|July|August|September|October|November|December)\\s+\\d{4}/;
                        const parentText = parent.innerText || '';
                        const match = parentText.match(monthPattern);
                        if (match) {
                            month = match[0];
                            break;
                        }
                        parent = parent.parentElement;
                        attempts++;
                    }
                    
                    if (title && !seen.has(title)) {
                        seen.add(title);
                        entries.push({
                            title: title,
                            url: href,
                            month: month
                        });
                    }
                });
                
                return entries;
            }
        """)
        
        print(f"找到 {len(entries)} 条更新条目，开始获取详情...")
        
        # 访问每个详情页获取描述
        for i, entry in enumerate(entries):
            title = entry.get('title', '')
            detail_url = entry.get('url', '')
            month = entry.get('month', '')
            
            description = ""
            
            if detail_url:
                try:
                    print(f"  [{i+1}/{len(entries)}] 获取详情: {title[:40]}...")
                    page.goto(detail_url, wait_until="domcontentloaded", timeout=30000)
                    page.wait_for_timeout(2000)
                    
                    # 提取详情页描述
                    description = page.evaluate("""
                        () => {
                            const desc = [];
                            
                            // 查找主要内容区域
                            const contentSelectors = [
                                'main p', 'article p', '.content p', 
                                '[class*="content"] p', '[class*="body"] p',
                                'div p'
                            ];
                            
                            for (const selector of contentSelectors) {
                                const paragraphs = document.querySelectorAll(selector);
                                paragraphs.forEach(p => {
                                    const txt = p.innerText?.trim();
                                    if (txt && txt.length > 10 && !desc.includes(txt)) {
                                        desc.push(txt);
                                    }
                                });
                                if (desc.length >= 3) break;
                            }
                            
                            // 也获取列表项
                            const lis = document.querySelectorAll('main li, article li, .content li');
                            lis.forEach(li => {
                                const txt = li.innerText?.trim();
                                if (txt && txt.length > 5 && !desc.includes(txt)) {
                                    desc.push('• ' + txt);
                                }
                            });
                            
                            return desc.slice(0, 15).join('\\n').substring(0, 2000);
                        }
                    """)
                except Exception as e:
                    print(f"    获取详情失败: {e}")
            
            feature = {
                "title": title,
                "description": description if description else f"Feature update: {title}",
                "time": parse_month_year(month),
                "tags": []
            }
            
            features.append(feature)
        
        browser.close()
    
    # 按日期排序
    features.sort(key=lambda x: x['time'] if x['time'] else '0000-00-00', reverse=True)
    
    return features


def save_data(features: list):
    """保存数据"""
    script_dir = Path(__file__).parent
    project_root = script_dir.parent.parent
    storage_dir = project_root / "storage"
    storage_dir.mkdir(exist_ok=True)
    
    output_data = [
        {"name": "base44", "url": "https://base44.com/changelog"},
        {"name": "feature", "features": features}
    ]
    
    output_path = storage_dir / "base44.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=4)
    
    print(f"\n数据已保存到 {output_path}")
    print(f"共 {len(features)} 条功能更新")


def main():
    print("=" * 50)
    print("Base44 Changelog Crawler")
    print("=" * 50)
    
    features = crawl_base44_changelog()
    
    if features:
        save_data(features)
    else:
        print("未获取到任何数据")


if __name__ == "__main__":
    main()
