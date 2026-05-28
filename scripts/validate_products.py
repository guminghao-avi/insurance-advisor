#!/usr/bin/env python3
"""
产品数据校验工具
检查产品库的字段完整性和格式一致性。

用法:
  python3 validate_products.py           # 校验所有文件
  python3 validate_products.py medical   # 校验指定文件
"""

import json
import os
import sys

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

# 每个险种必须有的字段
REQUIRED_FIELDS = {
    "medical": ["name", "company", "category", "age_range", "key_features", "tags"],
    "critical-illness": ["name", "company", "category", "age_range", "premium_reference", "key_features", "tags"],
    "accident": ["name", "company", "category", "age_range", "key_features", "tags"],
    "life": ["name", "company", "category", "age_range", "key_features", "tags"],
    "investment": ["name", "company", "category", "key_features", "tags"],
    "hongkong": ["name", "company", "category", "key_features", "tags"],
}

# 可选但推荐有的字段
RECOMMENDED_FIELDS = ["premium_reference", "limitations", "suitable_for", "rating"]


def validate_file(filepath, category):
    """校验单个产品文件"""
    issues = []
    warnings = []

    try:
        with open(filepath) as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        return [f"JSON解析失败: {e}"], []

    products = data.get("products", [])
    if not products:
        issues.append("products 数组为空")
        return issues, warnings

    required = REQUIRED_FIELDS.get(category, REQUIRED_FIELDS["medical"])

    for i, p in enumerate(products):
        name = p.get("name", f"产品#{i+1}")

        # 检查必须字段
        for field in required:
            if field not in p or not p[field]:
                issues.append(f"[{name}] 缺少必须字段: {field}")

        # 检查推荐字段
        for field in RECOMMENDED_FIELDS:
            if field not in p or not p[field]:
                warnings.append(f"[{name}] 缺少推荐字段: {field}")

        # 检查tags格式
        tags = p.get("tags", [])
        if not isinstance(tags, list):
            issues.append(f"[{name}] tags 应为数组，实际为 {type(tags).__name__}")
        elif len(tags) == 0:
            warnings.append(f"[{name}] tags 为空")

        # 检查key_features格式
        features = p.get("key_features", [])
        if not isinstance(features, list):
            issues.append(f"[{name}] key_features 应为数组")
        elif len(features) == 0:
            warnings.append(f"[{name}] key_features 为空")

        # 检查rating范围
        rating = p.get("rating")
        if rating is not None:
            if not isinstance(rating, (int, float)) or rating < 0 or rating > 5:
                issues.append(f"[{name}] rating 应在 0-5 之间，实际为 {rating}")

        # 检查age_range格式
        age_range = p.get("age_range", "")
        if age_range and not any(c in age_range for c in ["岁", "天", "周"]):
            warnings.append(f"[{name}] age_range 格式可能不标准: {age_range}")

    return issues, warnings


def main():
    if len(sys.argv) > 1:
        categories = sys.argv[1:]
    else:
        categories = ["medical", "critical-illness", "accident", "life", "investment", "hongkong"]

    total_issues = 0
    total_warnings = 0
    total_products = 0

    for cat in categories:
        filepath = os.path.join(DATA_DIR, f"{cat}.json")
        if not os.path.exists(filepath):
            print(f"✗ {cat}.json: 文件不存在")
            continue

        with open(filepath) as f:
            data = json.load(f)
        count = len(data.get("products", []))
        total_products += count

        issues, warnings = validate_file(filepath, cat)

        if not issues and not warnings:
            print(f"✓ {cat}.json: {count}款产品，无问题")
        else:
            print(f"{'✗' if issues else '△'} {cat}.json: {count}款产品，{len(issues)}个问题，{len(warnings)}个警告")
            for issue in issues:
                print(f"    ✗ {issue}")
            for warning in warnings:
                print(f"    △ {warning}")

        total_issues += len(issues)
        total_warnings += len(warnings)

    print(f"\n{'='*40}")
    print(f"总计: {total_products}款产品，{total_issues}个问题，{total_warnings}个警告")
    if total_issues == 0:
        print("校验通过 ✓")


if __name__ == "__main__":
    main()
