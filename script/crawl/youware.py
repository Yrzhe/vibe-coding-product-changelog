#!/usr/bin/env python3
"""
YouWare Changelog Crawler
爬取 YouWare changelog 页面的功能更新数据

页面结构（从截图分析）：
- 左侧：版本号（如 v2.7.4）+ 日期（如 January 12, 2026）
- 右侧：更新内容
  - 分类标签：Features, Improvements, Patches
  - 每个分类下有具体条目，可展开查看
"""

import json
import re
from datetime import datetime
from pathlib import Path
from playwright.sync_api import sync_playwright


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
    
    # 已经是 YYYY-MM-DD 格式
    if re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
        return date_str
    
    return date_str


def crawl_youware_changelog():
    """爬取 YouWare changelog 页面"""
    # 直接访问 changelog 页面
    url = "https://youware.app/project/zln9fqecog?enter_from=share&invite_code=FUQ800OLMY&screen_status=1"
    features = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        )
        page = context.new_page()
        
        print(f"访问 YouWare changelog...")
        page.goto(url, wait_until="domcontentloaded", timeout=120000)
        
        # 等待页面加载
        print("等待页面加载...")
        page.wait_for_timeout(8000)
        
        # 检查是否有 Cloudflare 验证
        title = page.title()
        if "moment" in title.lower() or "cloudflare" in title.lower():
            print("检测到验证页面，请在浏览器中完成验证...")
            page.wait_for_timeout(30000)
        
        # 获取 iframe
        print("查找 changelog iframe...")
        frames = page.frames
        changelog_frame = None
        
        for frame in frames:
            frame_url = frame.url
            if "yw.app" in frame_url and "live" in frame_url:
                changelog_frame = frame
                print(f"  ✓ 找到 iframe: {frame_url[:60]}...")
                break
        
        if not changelog_frame:
            print("未找到 iframe，使用主页面")
            changelog_frame = page
        
        # 滚动到底部加载所有内容
        print("滚动加载所有内容...")
        for i in range(50):
            try:
                changelog_frame.evaluate("window.scrollBy(0, 500)")
                page.wait_for_timeout(300)
            except:
                break
        
        # 回到顶部
        changelog_frame.evaluate("window.scrollTo(0, 0)")
        page.wait_for_timeout(1000)
        
        # 点击所有 "X items" 按钮来展开内容
        print("展开所有折叠内容...")
        try:
            expand_buttons = changelog_frame.query_selector_all('[class*="cursor-pointer"]')
            for btn in expand_buttons:
                try:
                    text = btn.inner_text()
                    if re.search(r'\d+\s*items?', text, re.I):
                        btn.click()
                        page.wait_for_timeout(500)
                except:
                    continue
        except Exception as e:
            print(f"展开时出错: {e}")
        
        page.wait_for_timeout(2000)
        
        # 再次滚动确保所有内容加载
        for i in range(30):
            try:
                changelog_frame.evaluate("window.scrollBy(0, 500)")
                page.wait_for_timeout(200)
            except:
                break
        
        changelog_frame.evaluate("window.scrollTo(0, 0)")
        page.wait_for_timeout(1000)
        
        # 提取数据 - 使用 JavaScript 分析页面结构
        print("提取更新数据...")
        
        data = changelog_frame.evaluate("""
            () => {
                const features = [];
                const seen = new Set();
                
                // 首先收集所有版本块及其日期
                // 结构：左侧有版本号和日期，右侧有具体内容
                
                // 查找所有包含版本号的元素
                const allText = document.body.innerText || '';
                
                // 提取版本-日期对应关系
                // 格式：v2.7.4 (换行或空格) January 12, 2026
                const versionDateMap = {};
                const versionPattern = /v(\\d+\\.\\d+\\.\\d+)/g;
                const datePattern = /(January|February|March|April|May|June|July|August|September|October|November|December)\\s+(\\d{1,2}),?\\s*(\\d{4})/gi;
                
                // 方法1: 按版本块提取
                // 查找所有版本号元素
                const allElements = document.querySelectorAll('*');
                let lastVersion = '';
                let lastDate = '';
                
                // 遍历所有元素，建立版本-日期映射
                for (const el of allElements) {
                    const text = el.innerText?.trim() || '';
                    
                    // 检测版本号 (如 v2.7.4)
                    const vMatch = text.match(/^v(\\d+\\.\\d+\\.\\d+)$/);
                    if (vMatch) {
                        lastVersion = text;
                        
                        // 查找相邻的日期
                        let sibling = el.nextElementSibling;
                        let parent = el.parentElement;
                        
                        // 在父元素中查找日期
                        if (parent) {
                            const parentText = parent.innerText || '';
                            const dMatch = parentText.match(/(January|February|March|April|May|June|July|August|September|October|November|December)\\s+(\\d{1,2}),?\\s*(\\d{4})/i);
                            if (dMatch) {
                                lastDate = dMatch[0];
                                versionDateMap[lastVersion] = lastDate;
                            }
                        }
                    }
                    
                    // 检测日期
                    const dMatch = text.match(/^(January|February|March|April|May|June|July|August|September|October|November|December)\\s+(\\d{1,2}),?\\s*(\\d{4})$/i);
                    if (dMatch && lastVersion) {
                        lastDate = text;
                        versionDateMap[lastVersion] = lastDate;
                    }
                }
                
                // 方法2: 查找功能条目
                // 功能条目通常是有标题和描述的元素
                
                // 查找所有可能是功能标题的元素
                const titleElements = document.querySelectorAll('h1, h2, h3, h4, h5, h6, strong, b, [class*="title"], [class*="heading"], [class*="font-bold"], [class*="font-semibold"]');
                
                let currentVersion = '';
                let currentDate = '';
                let currentCategory = '';
                
                for (const el of titleElements) {
                    const text = el.innerText?.trim() || '';
                    if (!text || text.length < 3) continue;
                    
                    // 跳过版本号
                    if (text.match(/^v\\d+\\.\\d+\\.\\d+$/)) {
                        currentVersion = text;
                        currentDate = versionDateMap[text] || '';
                        continue;
                    }
                    
                    // 跳过日期
                    if (text.match(/^(January|February|March|April|May|June|July|August|September|October|November|December)\\s+\\d/i)) {
                        continue;
                    }
                    
                    // 检测分类
                    if (['Features', 'Improvements', 'Patches', 'Bug Fixes', 'New', 'Fixes'].includes(text)) {
                        currentCategory = text;
                        continue;
                    }
                    
                    // 跳过 UI 元素
                    const skipWords = ['Changelog', 'Comments', 'Discover', 'Sign in', 'Create', 'Remix', 'Made By', 'YouWare', 'items', 'item'];
                    if (skipWords.some(w => text === w || text.startsWith(w + ' '))) {
                        continue;
                    }
                    
                    // 跳过太短或太长的文本
                    if (text.length < 8 || text.length > 300) continue;
                    
                    // 跳过 "X items" 格式
                    if (text.match(/^\\d+\\s+items?$/i)) continue;
                    
                    // 获取描述（查找下一个兄弟元素或父元素的文本）
                    let description = '';
                    
                    // 尝试从父元素获取更多文本
                    let parent = el.parentElement;
                    if (parent) {
                        const parentText = parent.innerText?.trim() || '';
                        if (parentText.length > text.length + 10) {
                            // 移除标题部分，保留描述
                            const idx = parentText.indexOf(text);
                            if (idx >= 0) {
                                description = parentText.substring(idx + text.length).trim();
                            }
                        }
                    }
                    
                    // 尝试从下一个兄弟元素获取
                    if (!description || description.length < 10) {
                        let next = el.nextElementSibling;
                        if (next) {
                            const nextText = next.innerText?.trim() || '';
                            if (nextText && nextText.length > 10 && !nextText.match(/^v\\d/)) {
                                description = nextText;
                            }
                        }
                    }
                    
                    // 清理描述
                    description = description.replace(/^\\n+/, '').trim();
                    if (description.length > 2000) {
                        description = description.substring(0, 2000);
                    }
                    
                    // 查找此元素对应的日期
                    let featureDate = currentDate;
                    
                    // 向上遍历查找最近的版本/日期
                    if (!featureDate) {
                        let ancestor = el.parentElement;
                        let attempts = 0;
                        while (ancestor && attempts < 20) {
                            const ancestorText = ancestor.innerText || '';
                            
                            // 查找版本号
                            const vMatch = ancestorText.match(/v(\\d+\\.\\d+\\.\\d+)/);
                            if (vMatch) {
                                const v = 'v' + vMatch[1];
                                if (versionDateMap[v]) {
                                    featureDate = versionDateMap[v];
                                    break;
                                }
                            }
                            
                            // 直接查找日期
                            const dMatch = ancestorText.match(/(January|February|March|April|May|June|July|August|September|October|November|December)\\s+\\d+,?\\s*\\d{4}/i);
                            if (dMatch) {
                                featureDate = dMatch[0];
                                break;
                            }
                            
                            ancestor = ancestor.parentElement;
                            attempts++;
                        }
                    }
                    
                    // 添加到结果
                    const key = text.toLowerCase();
                    if (!seen.has(key)) {
                        seen.add(key);
                        features.push({
                            title: text,
                            description: description,
                            time: featureDate || '',
                            category: currentCategory
                        });
                    }
                }
                
                // 方法3: 如果上述方法提取不够，尝试提取所有段落
                if (features.length < 10) {
                    const paragraphs = document.querySelectorAll('p, [class*="description"], [class*="content"]');
                    
                    for (const p of paragraphs) {
                        const text = p.innerText?.trim() || '';
                        if (text.length < 20 || text.length > 500) continue;
                        
                        // 提取第一句作为标题
                        const firstSentence = text.split(/[.!?\\n]/)[0].trim();
                        if (firstSentence.length < 10 || firstSentence.length > 200) continue;
                        
                        // 查找日期
                        let date = '';
                        let ancestor = p.parentElement;
                        let attempts = 0;
                        while (ancestor && attempts < 15) {
                            const ancestorText = ancestor.innerText || '';
                            const dMatch = ancestorText.match(/(January|February|March|April|May|June|July|August|September|October|November|December)\\s+\\d+,?\\s*\\d{4}/i);
                            if (dMatch) {
                                date = dMatch[0];
                                break;
                            }
                            ancestor = ancestor.parentElement;
                            attempts++;
                        }
                        
                        const key = firstSentence.toLowerCase();
                        if (!seen.has(key)) {
                            seen.add(key);
                            features.push({
                                title: firstSentence,
                                description: text,
                                time: date
                            });
                        }
                    }
                }
                
                return features;
            }
        """)
        
        print(f"初步提取到 {len(data)} 条数据")
        
        # 处理数据
        for item in data:
            title = item.get('title', '').strip()
            if not title or len(title) < 5:
                continue
            
            # 跳过非功能相关
            skip_patterns = ['Comments', 'Discover', 'Sign in', 'Create', 'Remix', 
                           'Made By', 'We evolve', 'items', 'Loading']
            if any(sp in title for sp in skip_patterns):
                continue
            
            # 解析日期
            time_str = item.get('time', '')
            item['time'] = parse_date(time_str)
            
            # 移除临时字段
            item.pop('category', None)
            
            features.append(item)
            
            date_display = item['time'] if item['time'] else '(无日期)'
            print(f"  ✓ {date_display}: {title[:50]}...")
        
        browser.close()
    
    # 去重
    seen_titles = set()
    unique_features = []
    for f in features:
        title = f.get('title', '').lower()
        if title and title not in seen_titles:
            seen_titles.add(title)
            unique_features.append(f)
    
    # 按日期排序
    unique_features.sort(key=lambda x: x.get('time', '0000-00-00'), reverse=True)
    
    print(f"\n去重后共 {len(unique_features)} 条功能更新")
    
    return unique_features


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
        {
            "name": "youware",
            "url": "https://youware.app/project/zln9fqecog?enter_from=share&invite_code=FUQ800OLMY&screen_status=1",
            "is_self": True
        },
        {"name": "feature", "features": features}
    ]
    
    output_path = storage_dir / "youware.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=4)
    
    print(f"\n数据已保存到 {output_path}")
    print(f"共 {len(features)} 条功能更新")


def main():
    print("=" * 50)
    print("YouWare Changelog Crawler")
    print("=" * 50)
    
    features = crawl_youware_changelog()
    
    if features:
        save_data(features)
    else:
        print("未获取到任何数据")


if __name__ == "__main__":
    main()
