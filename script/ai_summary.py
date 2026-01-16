#!/usr/bin/env python3
"""
AI 总结对比脚本
生成 YouWare 与竞品的功能对比分析

功能：
1. 读取 YouWare 和所有竞品的功能数据
2. 按标签维度分析
3. 调用 LLM 生成：
   - Matrix 总体概览：YouWare 亮点、与竞品差距
   - 每个 Tag 概览：该标签下 YouWare 的情况
4. 保存到 info/summary.json
"""

import json
import time
from datetime import datetime
from pathlib import Path
import requests


# 重试配置
MAX_RETRIES = 3
RETRY_DELAY = 2


def get_project_root():
    """获取项目根目录（支持本地和 Docker 环境）"""
    script_dir = Path(__file__).parent
    if script_dir == Path("/app"):
        return Path("/app")
    return script_dir.parent


def load_config():
    """加载 LLM 配置"""
    config_path = Path(__file__).parent / "prompts" / "llm_config.json"
    with open(config_path, "r", encoding="utf-8") as f:
        configs = json.load(f)
    return configs[0]


def load_exclude_tags():
    """加载要排除的标签列表"""
    config_path = get_project_root() / "info" / "admin_config.json"
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        return config.get("exclude_tags", [])
    except Exception:
        return []


def load_tags():
    """加载标签体系（自动过滤 exclude_tags，包括顶级标签和 subtag）"""
    tags_path = get_project_root() / "info" / "tag.json"
    with open(tags_path, "r", encoding="utf-8") as f:
        tags_data = json.load(f)
    
    # 兼容新旧格式
    if isinstance(tags_data, list):
        all_tags = tags_data
    else:
        all_tags = tags_data.get("primary_tags", [])
    
    # 过滤掉配置中指定的标签
    exclude_tags = load_exclude_tags()
    
    filtered_tags = []
    for tag in all_tags:
        # 跳过被排除的顶级标签
        if tag.get("name") in exclude_tags:
            continue
        
        # 过滤掉 subtag 中被排除的
        subtags = tag.get("subtags", [])
        filtered_subtags = [st for st in subtags if st.get("name") not in exclude_tags]
        
        # 创建新的 tag 对象，避免修改原始数据
        filtered_tag = {**tag, "subtags": filtered_subtags}
        filtered_tags.append(filtered_tag)
    
    return filtered_tags


def load_all_products():
    """加载所有产品数据"""
    storage_dir = get_project_root() / "storage"
    products = {}
    
    for json_file in storage_dir.glob("*.json"):
        if json_file.name == "example.json":
            continue
        
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            if len(data) < 2:
                continue
            
            product_info = data[0]
            product_name = product_info.get("name", json_file.stem)
            is_self = product_info.get("is_self", False)
            features = data[1].get("features", [])
            
            products[product_name] = {
                "name": product_name,
                "is_self": is_self,
                "features": features,
                "feature_count": len(features)
            }
        except Exception as e:
            print(f"加载 {json_file.name} 失败: {e}")
    
    return products


def analyze_tag_coverage(products: dict, tags: list):
    """分析每个产品的标签覆盖情况（自动过滤 exclude_tags）"""
    coverage = {}
    exclude_tags = load_exclude_tags()
    
    for product_name, product_data in products.items():
        product_tags = {}
        
        for feature in product_data["features"]:
            feature_tags = feature.get("tags", [])
            if not isinstance(feature_tags, list):
                continue
            
            for tag in feature_tags:
                tag_name = tag.get("name", "")
                if not tag_name:
                    continue
                
                # 跳过配置中排除的标签
                if tag_name in exclude_tags:
                    continue
                
                if tag_name not in product_tags:
                    product_tags[tag_name] = {
                        "count": 0,
                        "subtags": set()
                    }
                
                product_tags[tag_name]["count"] += 1
                
                for subtag in tag.get("subtags", []):
                    subtag_name = subtag.get("name", "")
                    # 跳过配置中排除的 subtag
                    if subtag_name and subtag_name not in exclude_tags:
                        product_tags[tag_name]["subtags"].add(subtag_name)
        
        # 转换 set 为 list
        for tag_name in product_tags:
            product_tags[tag_name]["subtags"] = list(product_tags[tag_name]["subtags"])
        
        coverage[product_name] = product_tags
    
    return coverage


def call_llm(prompt: str, config: dict, max_tokens: int = 2000) -> str:
    """调用 LLM API"""
    headers = {
        "Content-Type": "application/json",
        "x-api-key": config["api_key"],
        "anthropic-version": "2023-06-01"
    }
    
    payload = {
        "model": config.get("model", "claude-3-sonnet-20240229"),
        "max_tokens": max_tokens,
        "messages": [
            {"role": "user", "content": prompt}
        ]
    }
    
    for attempt in range(MAX_RETRIES):
        try:
            response = requests.post(
                f"{config['base_url']}/v1/messages",
                headers=headers,
                json=payload,
                timeout=120
            )
            
            if response.status_code == 200:
                result = response.json()
                return result["content"][0]["text"]
            else:
                print(f"  API 返回错误: {response.status_code}")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY * (attempt + 1))
        except Exception as e:
            print(f"  请求失败: {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY * (attempt + 1))
    
    return ""


def analyze_competitor_focus(products: dict, coverage: dict) -> dict:
    """分析每个竞品的产品重心和迭代方向"""
    competitor_analysis = {}
    
    for name, product in products.items():
        if product.get("is_self"):
            continue
            
        product_coverage = coverage.get(name, {})
        if not product_coverage:
            continue
        
        # 按功能数量排序标签
        sorted_tags = sorted(
            product_coverage.items(),
            key=lambda x: x[1]["count"],
            reverse=True
        )
        
        # 前3个是核心领域
        top_tags = sorted_tags[:3] if len(sorted_tags) >= 3 else sorted_tags
        
        competitor_analysis[name] = {
            "feature_count": product["feature_count"],
            "top_focus": [
                {
                    "tag": tag,
                    "count": data["count"],
                    "subtags": data["subtags"]
                }
                for tag, data in top_tags
            ],
            "total_tags": len(product_coverage)
        }
    
    return competitor_analysis


def generate_matrix_overview(products: dict, coverage: dict, tags: list, config: dict) -> str:
    """生成 Matrix 总体概览 - 深度业务分析版"""
    print("生成 Matrix 总体概览（深度分析版）...")
    
    # 准备详细数据
    youware_data = None
    competitor_data = []
    
    # 构建标签 -> subtag 数量的映射
    tag_subtag_counts = {}
    tag_subtag_names = {}
    for tag in tags:
        tag_name = tag.get("name", "")
        subtags = tag.get("subtags", [])
        tag_subtag_counts[tag_name] = len(subtags) if subtags else 1
        tag_subtag_names[tag_name] = [s.get("name", "") for s in subtags]
    
    for name, product in products.items():
        tag_summary = coverage.get(name, {})
        
        # 计算每个标签的覆盖率
        tag_details = {}
        for tag_name, tag_data in tag_summary.items():
            total = tag_subtag_counts.get(tag_name, 1)
            covered_subtags = tag_data.get("subtags", [])
            tag_details[tag_name] = {
                "covered": len(covered_subtags),
                "total": total,
                "features": tag_data.get("count", 0),
                "subtags": covered_subtags
            }
        
        summary = {
            "name": name,
            "feature_count": product["feature_count"],
            "tag_count": len(tag_summary),
            "tag_details": tag_details
        }
        
        if product.get("is_self"):
            youware_data = summary
        else:
            competitor_data.append(summary)
    
    if not youware_data:
        return "YouWare 数据未找到"
    
    # 分析竞品重心
    competitor_focus = analyze_competitor_focus(products, coverage)
    
    # 找出 YouWare 缺失的标签和 subtag
    missing_analysis = {}
    for comp in competitor_data:
        for tag_name, details in comp.get("tag_details", {}).items():
            if tag_name not in youware_data.get("tag_details", {}):
                # YouWare 完全缺失这个标签
                if tag_name not in missing_analysis:
                    missing_analysis[tag_name] = {
                        "type": "完全缺失",
                        "competitors_with": [],
                        "subtags_missing": details.get("subtags", [])
                    }
                missing_analysis[tag_name]["competitors_with"].append(comp["name"])
            else:
                # YouWare 有这个标签，但可能缺少 subtag
                youware_subtags = set(youware_data["tag_details"][tag_name].get("subtags", []))
                comp_subtags = set(details.get("subtags", []))
                missing_subtags = comp_subtags - youware_subtags
                
                if missing_subtags:
                    if tag_name not in missing_analysis:
                        missing_analysis[tag_name] = {
                            "type": "部分缺失",
                            "competitors_with": [],
                            "subtags_missing": []
                        }
                    missing_analysis[tag_name]["competitors_with"].append(comp["name"])
                    missing_analysis[tag_name]["subtags_missing"].extend(list(missing_subtags))
    
    # 去重 subtags_missing
    for tag_name in missing_analysis:
        missing_analysis[tag_name]["subtags_missing"] = list(set(missing_analysis[tag_name]["subtags_missing"]))
    
    prompt = f"""你是一位资深的产品战略分析师，老板需要你撰写一份**深度竞品分析报告**，帮助理解 YouWare 在市场中的真实位置。

⚠️ **重要要求**：
- 这份报告是给老板看的，需要有**业务洞察**，不是数据堆砌
- **侧重劣势分析**，让老板清楚我们落后在哪里
- **不要给任何建议或改进方向**，只分析现状
- 挖掘竞品的**产品思路和战略重点**，而不是单纯列功能数量
- 用自然的中文段落，不要用 Markdown 格式

## YouWare 数据：
- 功能更新总数: {youware_data['feature_count']} 个
- 覆盖功能领域: {youware_data['tag_count']} 个
- 各领域详情: {json.dumps(youware_data['tag_details'], ensure_ascii=False)}

## 各竞品产品重心分析：
{json.dumps(competitor_focus, ensure_ascii=False, indent=2)}

## YouWare 功能差距详情：
{json.dumps(missing_analysis, ensure_ascii=False, indent=2)}

## 全部竞品数据：
{json.dumps(competitor_data, ensure_ascii=False, indent=2)}

---

请按以下结构撰写分析报告（800-1200字）：

**第一部分：YouWare 功能差距分析**
- 与功能最丰富的竞品相比，差距有多大？具体体现在哪些方面？
- 哪些是"致命短板"（竞品普遍有但我们没有）？
- 用具体的数据说明差距，但要有解读（比如"Integration 只覆盖 6 个，而 Replit 达到 43 个，意味着生态连接能力严重不足"）

**第二部分：竞品战略洞察**
- 分析 2-3 个主要竞品的产品重心和迭代方向（根据他们的功能分布推断）
- 他们在押注什么方向？（比如某个产品明显偏重企业级功能、某个偏重 AI 模型多样性）
- 这对行业意味着什么？

**第三部分：YouWare 相对优势**
- 客观分析 YouWare 做得比竞品好的地方（如果有）
- 这些优势是否具有战略价值？

请直接输出分析内容："""
    
    result = call_llm(prompt, config, max_tokens=3000)
    return result.strip() if result else "总结生成失败"


def generate_tag_summary(tag_name: str, tag_info: dict, products: dict, coverage: dict, config: dict) -> str:
    """生成单个标签的概览 - 深度业务分析版"""
    # 获取该标签的所有 subtag
    all_subtags = [s.get("name", "") for s in tag_info.get("subtags", [])]
    total_subtags = len(all_subtags) if all_subtags else 1
    
    # 收集该标签下各产品的情况
    tag_data = {}
    youware_subtags = []
    youware_feature_count = 0
    competitor_subtags = {}
    competitor_features = {}
    leader_name = ""
    leader_count = 0
    
    for name, product in products.items():
        product_coverage = coverage.get(name, {})
        if tag_name in product_coverage:
            subtags = product_coverage[tag_name]["subtags"]
            feature_count = product_coverage[tag_name]["count"]
            tag_data[name] = {
                "is_self": product.get("is_self", False),
                "feature_count": feature_count,
                "subtags_covered": len(subtags),
                "subtags_total": total_subtags,
                "subtags": subtags
            }
            
            if product.get("is_self"):
                youware_subtags = subtags
                youware_feature_count = feature_count
            else:
                competitor_subtags[name] = subtags
                competitor_features[name] = feature_count
                if feature_count > leader_count:
                    leader_count = feature_count
                    leader_name = name
    
    if not tag_data:
        return ""
    
    # 检查 YouWare 是否有这个标签
    youware_has_tag = any(v.get("is_self") for v in tag_data.values())
    
    # 找出 YouWare 缺失但竞品有的 subtag
    missing_subtags = set()
    if youware_has_tag:
        youware_set = set(youware_subtags)
        for comp_name, comp_subtags in competitor_subtags.items():
            missing_subtags.update(set(comp_subtags) - youware_set)
    else:
        # YouWare 完全没有这个标签，收集所有竞品的 subtag
        for comp_subtags in competitor_subtags.values():
            missing_subtags.update(comp_subtags)
    
    # 计算差距程度
    gap_description = ""
    if leader_name and leader_count > 0:
        if youware_has_tag:
            gap_ratio = youware_feature_count / leader_count if leader_count > 0 else 0
            if gap_ratio < 0.3:
                gap_description = "严重落后"
            elif gap_ratio < 0.6:
                gap_description = "明显落后"
            elif gap_ratio < 0.9:
                gap_description = "略有差距"
            else:
                gap_description = "基本持平或领先"
        else:
            gap_description = "完全缺失"
    
    prompt = f"""分析 "{tag_name}" 功能领域下 YouWare 与竞品的对比情况。

⚠️ 要求：只分析现状，**不要给任何建议**。用简洁的中文，不要用 Markdown。

## 数据概览：
- YouWare 功能数: {youware_feature_count if youware_has_tag else 0}
- YouWare subtag 覆盖: {len(youware_subtags)}/{total_subtags}
- 领先竞品: {leader_name} ({leader_count}个功能)
- 差距程度: {gap_description}

## 各产品详情：
{json.dumps(tag_data, ensure_ascii=False, indent=2)}

## 该领域所有可能的子功能：
{', '.join(all_subtags) if all_subtags else '无子分类'}

## YouWare 缺失的子功能：
{', '.join(missing_subtags) if missing_subtags else '无缺失'}

请输出 3-5 句话的分析：
1. YouWare 在此领域的位置（领先/持平/落后/缺失）
2. 与领先者的具体差距体现在哪些方面
3. 这些缺失对产品竞争力的影响

{"特别注意：YouWare 在此领域完全缺失，需分析这意味着什么。" if not youware_has_tag else ""}
{"如果 YouWare 在此领域表现较好，客观说明优势。" if gap_description == "基本持平或领先" else ""}"""
    
    result = call_llm(prompt, config, max_tokens=600)
    return result.strip() if result else ""


def generate_all_summaries():
    """生成所有总结 - 深度业务分析版"""
    print("=" * 60)
    print("AI 深度竞品分析报告生成")
    print("=" * 60)
    
    # 加载数据
    config = load_config()
    tags = load_tags()
    products = load_all_products()
    coverage = analyze_tag_coverage(products, tags)
    
    print(f"✓ 加载了 {len(products)} 个产品")
    print(f"✓ 加载了 {len(tags)} 个功能领域")
    
    # 统计 YouWare 和竞品
    youware_count = 0
    competitor_counts = {}
    for name, product in products.items():
        if product.get("is_self"):
            youware_count = product["feature_count"]
        else:
            competitor_counts[name] = product["feature_count"]
    
    print(f"\n📊 数据概览:")
    print(f"   YouWare: {youware_count} 个功能")
    for name, count in sorted(competitor_counts.items(), key=lambda x: -x[1])[:3]:
        print(f"   {name}: {count} 个功能")
    
    print("\n" + "=" * 60)
    print("正在生成深度分析报告（预计需要 2-3 分钟）...")
    print("=" * 60)
    
    # 生成 Matrix 概览（传递 tags 用于计算 subtag 总数）
    matrix_overview = generate_matrix_overview(products, coverage, tags, config)
    print(f"\n✓ Matrix 总体分析完成，共 {len(matrix_overview)} 字符")
    print("-" * 40)
    print(matrix_overview[:500] + "..." if len(matrix_overview) > 500 else matrix_overview)
    print("-" * 40)
    
    # 生成每个标签的概览
    tag_summaries = {}
    total_tags = len([t for t in tags if t.get("name")])
    current = 0
    
    for tag in tags:
        tag_name = tag.get("name", "")
        if not tag_name:
            continue
        
        current += 1
        print(f"\n[{current}/{total_tags}] 分析 {tag_name} 领域...")
        summary = generate_tag_summary(tag_name, tag, products, coverage, config)
        if summary:
            tag_summaries[tag_name] = summary
            # 只显示前80个字符
            preview = summary.replace('\n', ' ')[:80]
            print(f"    → {preview}...")
    
    # 保存结果
    result = {
        "last_updated": datetime.now().isoformat(),
        "matrix_overview": matrix_overview,
        "tag_summaries": tag_summaries
    }
    
    summary_path = get_project_root() / "info" / "summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=4)
    
    print("\n" + "=" * 60)
    print(f"✅ 分析报告已保存: {summary_path}")
    print(f"   - Matrix 总体分析: {len(matrix_overview)} 字符")
    print(f"   - 功能领域分析: {len(tag_summaries)} 个")
    print("=" * 60)
    
    return result


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="AI 总结对比生成脚本")
    parser.add_argument(
        "--tag",
        type=str,
        help="只生成指定标签的概览"
    )
    parser.add_argument(
        "--matrix-only",
        action="store_true",
        help="只生成 Matrix 概览"
    )
    
    args = parser.parse_args()
    
    if args.tag:
        # 只生成指定标签
        config = load_config()
        tags = load_tags()
        products = load_all_products()
        coverage = analyze_tag_coverage(products, tags)
        
        # 找到对应的 tag 信息
        tag_info = next((t for t in tags if t.get("name") == args.tag), {})
        summary = generate_tag_summary(args.tag, tag_info, products, coverage, config)
        print(f"{args.tag}: {summary}")
    elif args.matrix_only:
        # 只生成 Matrix 概览
        config = load_config()
        tags = load_tags()
        products = load_all_products()
        coverage = analyze_tag_coverage(products, tags)
        
        overview = generate_matrix_overview(products, coverage, tags, config)
        print(f"Matrix 概览:\n{overview}")
    else:
        # 生成所有
        generate_all_summaries()


if __name__ == "__main__":
    main()
