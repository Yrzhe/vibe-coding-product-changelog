#!/usr/bin/env python3
"""
修复存量数据中的问题
"""

import json
import re
from pathlib import Path


def fix_replit_dates():
    """修复 replit.json 中的日期问题"""
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    storage_dir = project_root / "storage"
    
    replit_path = storage_dir / "replit.json"
    
    if not replit_path.exists():
        print("replit.json 不存在")
        return
    
    with open(replit_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    if len(data) < 2:
        return
    
    features = data[1].get("features", [])
    fixed_count = 0
    removed_count = 0
    
    # 过滤掉无效条目并修复日期
    valid_features = []
    
    for feat in features:
        time_val = feat.get("time", "")
        title = feat.get("title", "")
        
        # 跳过无效条目
        if title in ["Matt Palmer", "Head of Developer Relations"]:
            removed_count += 1
            continue
        
        # 检查日期是否有效
        if not time_val or not re.match(r'\d{4}-\d{2}-\d{2}', time_val):
            # 尝试从标题或描述中推断日期
            # 如果无法修复，设置为空
            if time_val == "Changelog":
                feat["time"] = ""
                fixed_count += 1
        
        valid_features.append(feat)
    
    data[1]["features"] = valid_features
    
    with open(replit_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    
    print(f"replit.json: 修复 {fixed_count} 条日期，移除 {removed_count} 条无效条目")
    print(f"  剩余 {len(valid_features)} 条有效功能更新")


def check_all_data():
    """检查所有数据文件的状态"""
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    storage_dir = project_root / "storage"
    
    print("\n" + "=" * 60)
    print("数据质量检查报告")
    print("=" * 60)
    
    total_features = 0
    
    for json_file in sorted(storage_dir.glob("*.json")):
        if json_file.name == "example.json":
            continue
        
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            if len(data) < 2:
                print(f"\n{json_file.name}: ❌ 数据结构异常")
                continue
            
            features = data[1].get("features", [])
            
            # 统计
            total = len(features)
            with_date = sum(1 for f in features if f.get("time") and re.match(r'\d{4}-\d{2}-\d{2}', f.get("time", "")))
            with_tags = sum(1 for f in features if f.get("tags") and len(f.get("tags", [])) > 0)
            
            if total == 0:
                status = "❌ 无数据"
            elif with_date < total * 0.5:
                status = "⚠️ 日期缺失"
            else:
                status = "✅ 正常"
            
            print(f"\n{json_file.name}: {status}")
            print(f"  总数: {total} 条")
            print(f"  有日期: {with_date} 条 ({with_date*100//max(total,1)}%)")
            print(f"  已打标: {with_tags} 条 ({with_tags*100//max(total,1)}%)")
            
            total_features += total
            
        except Exception as e:
            print(f"\n{json_file.name}: ❌ 读取失败 - {e}")
    
    print(f"\n{'=' * 60}")
    print(f"总计: {total_features} 条功能更新")


def main():
    print("=" * 60)
    print("数据修复脚本")
    print("=" * 60)
    
    # 修复 replit 日期
    fix_replit_dates()
    
    # 检查所有数据
    check_all_data()


if __name__ == "__main__":
    main()
