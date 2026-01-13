#!/usr/bin/env python3
"""
竞品更新监控脚本（增量模式）

工作原理：
1. 备份现有数据（保护已有的 tags）
2. 运行爬虫获取最新数据
3. 合并新旧数据，保留已有的 tags
4. 只对新增条目进行 LLM 打标
5. 定期全量同步检查防止遗漏
"""

import json
import subprocess
import sys
import hashlib
import shutil
from datetime import datetime, timedelta
from pathlib import Path


def get_project_root():
    """获取项目根目录"""
    return Path(__file__).parent.parent


def get_feature_key(feature: dict) -> str:
    """
    生成功能条目的唯一标识
    使用 title 的 hash + time 作为 key
    """
    title = feature.get("title", "")
    time = feature.get("time", "")
    title_hash = hashlib.md5(title.encode()).hexdigest()[:16]
    return f"{title_hash}_{time}"


def load_storage(product_name: str) -> tuple:
    """
    加载产品存储数据
    返回: (data, features, feature_map)
    feature_map: {key: feature} 方便查找和合并
    """
    storage_path = get_project_root() / "storage" / f"{product_name}.json"

    if not storage_path.exists():
        return None, [], {}

    with open(storage_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if len(data) < 2:
        return data, [], {}

    features = data[1].get("features", [])

    # 构建 feature_map
    feature_map = {}
    for f in features:
        key = get_feature_key(f)
        feature_map[key] = f

    return data, features, feature_map


def save_storage(product_name: str, data: list):
    """保存产品数据"""
    storage_path = get_project_root() / "storage" / f"{product_name}.json"
    with open(storage_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


def backup_storage(product_name: str) -> dict:
    """
    备份产品数据，返回 feature_map
    这样即使爬虫覆盖文件，我们也能恢复 tags
    """
    _, _, feature_map = load_storage(product_name)
    return feature_map


def merge_features(old_feature_map: dict, new_features: list) -> tuple:
    """
    合并新旧功能数据
    - 保留旧条目的 tags
    - 识别真正的新增条目

    返回: (merged_features, new_keys)
    """
    merged = []
    new_keys = set()
    seen_keys = set()

    for feature in new_features:
        key = get_feature_key(feature)

        # 避免重复
        if key in seen_keys:
            continue
        seen_keys.add(key)

        if key in old_feature_map:
            # 已存在的条目：保留原有的 tags
            old_feature = old_feature_map[key]
            old_tags = old_feature.get("tags", [])

            # 如果旧条目有 tags，保留它们
            if old_tags and isinstance(old_tags, list) and len(old_tags) > 0:
                feature["tags"] = old_tags
            # 否则标记为需要打标
            elif not feature.get("tags") or len(feature.get("tags", [])) == 0:
                new_keys.add(key)
        else:
            # 新条目
            new_keys.add(key)
            if "tags" not in feature:
                feature["tags"] = []

        merged.append(feature)

    return merged, new_keys


def get_latest_date(product_name: str) -> str:
    """获取产品最新的更新日期"""
    _, features, _ = load_storage(product_name)

    if not features:
        return None

    # 找最新的日期
    dates = [f.get("time", "") for f in features if f.get("time")]
    if not dates:
        return None

    # 按日期排序，取最新的
    try:
        dates.sort(reverse=True)
        return dates[0]
    except:
        return None


def run_crawler(product_name: str) -> bool:
    """
    运行爬虫
    返回: 是否成功
    """
    crawler_path = get_project_root() / "script" / "crawl" / f"{product_name}.py"

    if not crawler_path.exists():
        print(f"  ⚠️ 爬虫脚本不存在: {crawler_path}")
        return False

    try:
        result = subprocess.run(
            [sys.executable, str(crawler_path)],
            capture_output=True,
            text=True,
            timeout=180
        )

        if result.returncode != 0:
            print(f"  ⚠️ 爬虫执行失败: {result.stderr[:200]}")
            return False

        return True

    except subprocess.TimeoutExpired:
        print(f"  ⚠️ 爬虫执行超时")
        return False
    except Exception as e:
        print(f"  ⚠️ 爬虫执行异常: {e}")
        return False


def run_tagging_for_product(product_name: str) -> bool:
    """为指定产品运行打标（只处理没有 tags 的条目）"""
    tag_script = get_project_root() / "script" / "llm_tagger.py"

    if not tag_script.exists():
        print("  ⚠️ 打标脚本不存在")
        return False

    try:
        result = subprocess.run(
            [sys.executable, str(tag_script), "--file", f"{product_name}.json"],
            capture_output=True,
            text=True,
            timeout=600  # 打标可能需要较长时间
        )
        if result.stdout:
            # 只打印关键信息
            for line in result.stdout.split('\n'):
                if '🏷️' in line or '✓' in line or '新增' in line:
                    print(f"     {line}")
        return result.returncode == 0
    except Exception as e:
        print(f"  ⚠️ 打标执行异常: {e}")
        return False


def load_competitors() -> list:
    """加载竞品配置"""
    config_path = get_project_root() / "info" / "competitor.json"

    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_sync_status() -> dict:
    """加载同步状态"""
    status_path = get_project_root() / "info" / "sync_status.json"

    if not status_path.exists():
        return {}

    with open(status_path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_sync_status(status: dict):
    """保存同步状态"""
    status_path = get_project_root() / "info" / "sync_status.json"

    with open(status_path, "w", encoding="utf-8") as f:
        json.dump(status, f, ensure_ascii=False, indent=4)


def save_update_log(updates: dict):
    """保存更新日志"""
    log_dir = get_project_root() / "logs"
    log_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = log_dir / f"update_{timestamp}.json"

    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(updates, f, ensure_ascii=False, indent=4)

    print(f"\n📄 更新日志已保存到: {log_path}")


def monitor_product(name: str, url: str, force_full: bool = False) -> dict:
    """
    监控单个产品

    流程：
    1. 备份现有数据（保存 feature_map）
    2. 运行爬虫（爬虫会覆盖文件）
    3. 合并新旧数据，保留已有的 tags
    4. 只对新增条目打标
    """
    print(f"\n📦 {name}")
    print(f"   URL: {url}")

    # 1. 备份现有数据
    old_data, old_features, old_feature_map = load_storage(name)
    old_count = len(old_features)
    latest_date = get_latest_date(name)

    print(f"   已有: {old_count} 条")
    if latest_date:
        print(f"   最新: {latest_date}")

    # 2. 运行爬虫
    print(f"   正在爬取...")
    crawler_success = run_crawler(name)

    if not crawler_success:
        print(f"   ❌ 爬虫失败，保留原数据")
        return {
            "status": "crawler_failed",
            "old_count": old_count,
            "new_count": 0
        }

    # 3. 加载爬虫爬取的新数据
    new_data, new_features, _ = load_storage(name)

    if not new_features:
        print(f"   ⚠️ 爬虫返回空数据，保留原数据")
        # 恢复原数据
        if old_data:
            save_storage(name, old_data)
        return {
            "status": "empty_result",
            "old_count": old_count,
            "new_count": 0
        }

    # 4. 合并数据，保留已有的 tags
    merged_features, new_keys = merge_features(old_feature_map, new_features)

    # 5. 更新并保存数据
    if new_data and len(new_data) >= 2:
        new_data[1]["features"] = merged_features
        save_storage(name, new_data)

    new_count = len(new_keys)

    result = {
        "status": "success",
        "old_count": old_count,
        "total_count": len(merged_features),
        "new_count": new_count
    }

    if new_count > 0:
        print(f"   🆕 发现 {new_count} 条新功能")

        # 显示新增条目
        for feature in merged_features:
            key = get_feature_key(feature)
            if key in new_keys:
                title = feature.get('title', '')[:50]
                time = feature.get('time', '')
                print(f"      [{time}] {title}...")
                if len([f for f in merged_features if get_feature_key(f) in new_keys]) > 5:
                    remaining = new_count - 5
                    if remaining > 0:
                        print(f"      ... 还有 {remaining} 条")
                    break

        result["new_features"] = [
            {"title": f.get("title", ""), "time": f.get("time", "")}
            for f in merged_features if get_feature_key(f) in new_keys
        ]

        # 6. 为新内容打标
        print(f"   🏷️ 正在为新内容打标...")
        run_tagging_for_product(name)
    else:
        print(f"   ✅ 无新增内容")

    return result


def monitor_all(force_full: bool = False):
    """监控所有竞品"""
    print("=" * 60)
    print("竞品更新监控")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    competitors = load_competitors()
    sync_status = load_sync_status()

    all_updates = {
        "timestamp": datetime.now().isoformat(),
        "updates": {}
    }

    total_new = 0

    for competitor in competitors:
        name = competitor.get("name", "")
        url = competitor.get("url", "")

        if not name:
            continue

        try:
            result = monitor_product(name, url, force_full)
            all_updates["updates"][name] = result
            total_new += result.get("new_count", 0)

            # 更新同步状态
            sync_status[name] = {
                "last_sync": datetime.now().isoformat(),
                "latest_date": get_latest_date(name)
            }
        except Exception as e:
            print(f"   ❌ 监控失败: {e}")
            all_updates["updates"][name] = {
                "status": "failed",
                "error": str(e)
            }

    # 保存同步状态
    save_sync_status(sync_status)

    # 保存日志
    if total_new > 0:
        save_update_log(all_updates)

    print("\n" + "=" * 60)
    print(f"监控完成，共发现 {total_new} 条新功能")
    print("=" * 60)

    return all_updates


def check_full_sync_needed() -> bool:
    """检查是否需要全量同步（每周一次）"""
    sync_status = load_sync_status()

    last_full_sync = sync_status.get("__last_full_sync__")
    if not last_full_sync:
        return True

    try:
        last_full = datetime.fromisoformat(last_full_sync)
        days_since = (datetime.now() - last_full).days
        return days_since >= 7
    except:
        return True


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="竞品更新监控脚本")
    parser.add_argument(
        "--product",
        type=str,
        help="只监控指定产品 (如: v0, lovable, bolt)"
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="强制全量爬取（用于定期完整同步）"
    )
    parser.add_argument(
        "--auto",
        action="store_true",
        help="自动模式：通常增量更新，每周一次全量"
    )

    args = parser.parse_args()

    # 自动模式
    force_full = args.full
    if args.auto and check_full_sync_needed():
        print("⚠️ 距离上次全量同步超过 7 天，执行全量同步")
        force_full = True

        # 更新全量同步时间
        sync_status = load_sync_status()
        sync_status["__last_full_sync__"] = datetime.now().isoformat()
        save_sync_status(sync_status)

    if args.product:
        # 监控单个产品
        competitors = load_competitors()
        competitor = next((c for c in competitors if c.get("name") == args.product), None)

        if not competitor:
            print(f"❌ 未找到产品: {args.product}")
            return

        monitor_product(args.product, competitor.get("url", ""), force_full)
    else:
        # 监控所有产品
        monitor_all(force_full)


if __name__ == "__main__":
    main()
