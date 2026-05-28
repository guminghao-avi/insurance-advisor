#!/usr/bin/env python3
"""
产品筛选工具
按条件从产品库中筛选匹配的产品。

用法:
  python3 search_products.py --category medical --tag 保证续保
  python3 search_products.py --category critical-illness --tag 少儿
  python3 search_products.py --keyword 免健告
  python3 search_products.py --category medical --max-deductible 0
  python3 search_products.py --category life --tag 定期寿
"""

import json
import os
import argparse
import sys

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


def load_products(category=None):
    """加载产品数据"""
    products = []
    if category:
        path = os.path.join(DATA_DIR, f"{category}.json")
        if os.path.exists(path):
            with open(path) as f:
                data = json.load(f)
                for p in data.get("products", []):
                    p["_source_file"] = f"{category}.json"
                    products.append(p)
    else:
        for f in os.listdir(DATA_DIR):
            if f.endswith(".json") and f != "metadata.json":
                with open(os.path.join(DATA_DIR, f)) as fh:
                    data = json.load(fh)
                    for p in data.get("products", []):
                        p["_source_file"] = f
                        products.append(p)
    return products


def search_products(category=None, keyword=None, tag=None, max_deductible=None, max_premium=None, age=None):
    """按条件筛选产品"""
    products = load_products(category)
    results = []

    for p in products:
        # 关键词搜索（名称、公司、特征、适宜人群）
        if keyword:
            text = " ".join([
                p.get("name", ""),
                p.get("company", ""),
                " ".join(p.get("key_features", [])),
                " ".join(p.get("suitable_for", [])),
                " ".join(p.get("tags", [])),
                p.get("category", ""),
            ])
            if keyword.lower() not in text.lower():
                continue

        # 标签筛选
        if tag:
            tags = [str(t).lower() for t in p.get("tags", [])]
            if tag.lower() not in tags:
                continue

        # 免赔额筛选（医疗险）
        if max_deductible is not None:
            deductible = p.get("deductible")
            if deductible is None:
                continue
            if isinstance(deductible, (int, float)) and deductible > max_deductible:
                continue

        # 年龄筛选
        if age:
            age_range = p.get("age_range", "")
            # 简单解析：检查年龄是否在范围内
            if age_range and not _age_in_range(age, age_range):
                continue

        results.append(p)

    return results


def _age_in_range(age, age_range):
    """简单判断年龄是否在范围内"""
    import re
    # 匹配 "0-60岁" 或 "18-65岁" 等格式
    m = re.search(r'(\d+)\s*[-~]\s*(\d+)', age_range)
    if m:
        low, high = int(m.group(1)), int(m.group(2))
        return low <= age <= high
    # 匹配 "0-17岁" 等
    m2 = re.search(r'(\d+)', age_range)
    if m2:
        return age <= int(m2.group(1))
    return True


def format_results(results, verbose=False):
    """格式化输出结果"""
    if not results:
        print("未找到匹配的产品。")
        return

    print(f"找到 {len(results)} 款匹配产品：\n")
    for i, p in enumerate(results, 1):
        name = p.get("name", "未知")
        company = p.get("company", "未知")
        category = p.get("category", p.get("_source_file", ""))
        tags = ", ".join(str(t) for t in p.get("tags", []))

        print(f"  {i}. {name}（{company}）")
        print(f"     分类: {category} | 标签: {tags}")

        if p.get("age_range"):
            print(f"     投保年龄: {p['age_range']}")
        if p.get("premium_reference"):
            print(f"     保费参考: {p['premium_reference']}")
        if p.get("deductible") is not None:
            print(f"     免赔额: {p['deductible']}元")
        if p.get("coverage_amount"):
            print(f"     保额: {p['coverage_amount']}")
        if p.get("irr_reference"):
            print(f"     IRR参考: {p['irr_reference']}")
        if p.get("key_features"):
            features = p["key_features"][:3]
            print(f"     亮点: {' | '.join(features)}")

        print()


def main():
    parser = argparse.ArgumentParser(description="保险产品筛选工具")
    parser.add_argument("--category", "-c", help="险种: medical/critical-illness/accident/life/investment/hongkong")
    parser.add_argument("--keyword", "-k", help="关键词搜索")
    parser.add_argument("--tag", "-t", help="标签筛选")
    parser.add_argument("--max-deductible", type=float, help="最大免赔额")
    parser.add_argument("--max-premium", type=float, help="最大年保费")
    parser.add_argument("--age", type=int, help="被保险人年龄")
    parser.add_argument("--json", action="store_true", help="输出JSON格式")

    args = parser.parse_args()
    results = search_products(
        category=args.category,
        keyword=args.keyword,
        tag=args.tag,
        max_deductible=args.max_deductible,
        age=args.age,
    )

    if args.json:
        # 去掉内部字段
        for r in results:
            r.pop("_source_file", None)
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        format_results(results)


if __name__ == "__main__":
    main()
