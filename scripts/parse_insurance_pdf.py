#!/usr/bin/env python3
"""
保险条款PDF自动解析脚本 v2
支持条款PDF + 费率表PDF的联合解析。

用法:
  python3 parse_insurance_pdf.py <条款PDF> [费率表PDF]
  python3 parse_insurance_pdf.py --dir <目录>  (批量解析目录下所有PDF)

输出: JSON格式的结构化产品信息
"""

import sys
import os
import re
import json
import fitz  # pymupdf


def extract_text(pdf_path):
    doc = fitz.open(pdf_path)
    text = ""
    for page in doc:
        text += page.get_text()
    doc.close()
    return text


def extract_field(text, patterns, default="未提取到"):
    for pattern in patterns:
        match = re.search(pattern, text, re.DOTALL)
        if match:
            return match.group(1).strip()
    return default


def parse_terms_pdf(pdf_path):
    """解析条款/投保须知PDF"""
    text = extract_text(pdf_path)
    result = {
        "source_file": os.path.basename(pdf_path),
        "raw_text_length": len(text),
    }

    # === 基本信息 ===
    result["name"] = extract_field(text, [
        r"本产品名称为(.+?)[，,。\n]",
        r"产品名称[：:](.+?)[，,。\n]",
    ])

    result["company"] = extract_field(text, [
        r"由(.+?)承保",
        r"承保公司[：:](.+?)[，,。\n]",
    ])

    result["age_range"] = extract_field(text, [
        r"被保险人年龄[：:].*?(\d+\s*[天岁周岁]+\s*[至到~-]\s*\d+\s*[岁周岁]+)",
        r"首次投保时年龄.*?(\d+\s*[天岁周岁]+\s*[至到~-]\s*\d+\s*[岁周岁]+)",
    ])

    renewal_age = extract_field(text, [
        r"可连续投保至(\d+)\s*[岁周岁]",
        r"续保.*?至(\d+)\s*[岁周岁]",
        r"最高续保年龄[：:](\d+)",
    ], default=None)
    if renewal_age and renewal_age != "未提取到":
        result["max_renewal_age"] = renewal_age

    result["insurance_period"] = extract_field(text, [
        r"保险期间[：:](.+?)[，,。\n]",
        r"本产品保险期间[：:](.+?)[，,。\n]",
    ])

    result["waiting_period"] = extract_field(text, [
        r"等待期[为有]?\s*(\d+)\s*天",
        r"等待期[：:](\d+)\s*天",
    ])

    # === 免赔额 ===
    dm = re.search(r"免赔额[为是]?\s*([\d,]+)\s*万[元]?/年", text)
    if dm:
        result["deductible"] = int(dm.group(1).replace(",", "")) * 10000
    else:
        dm2 = re.search(r"免赔额[为是]?\s*([\d,]+)\s*元/年", text)
        if dm2:
            result["deductible"] = int(dm2.group(1).replace(",", ""))

    # === 保额 ===
    cm = re.search(r"累计给付上限[为是]?\s*(\d+)\s*万", text)
    if cm:
        result["coverage_amount"] = int(cm.group(1)) * 10000
    else:
        cm2 = re.search(r"总保额[为是]?\s*(\d+)\s*万", text)
        if cm2:
            result["coverage_amount"] = int(cm2.group(1)) * 10000

    # === 赔付比例 ===
    result["reimbursement_rate"] = extract_field(text, [
        r"赔付比例[：:]?\s*(\d+%)",
        r"按\s*(\d+%)\s*的比例给付",
        r"按(\d+%)\s*进行赔付",
    ])

    # === 保证续保 ===
    if "保证续保" in text:
        if "不保证续保" in text or "非保证续保" in text:
            result["guaranteed_renewal"] = False
        else:
            ym = re.search(r"保证续保\s*(\d+)\s*年", text)
            if ym:
                result["guaranteed_renewal"] = True
                result["guaranteed_renewal_years"] = int(ym.group(1))
            else:
                result["guaranteed_renewal"] = "需人工确认"
    else:
        result["guaranteed_renewal"] = False

    # === 保障内容提取 ===
    coverage = {}

    # 住院
    if re.search(r"住院医疗|住院费用|住院保险", text):
        coverage["住院"] = True
        # 住院前后门急诊
        pre_match = re.search(r"住院前(\d+).*?出院后(\d+)", text)
        if pre_match:
            coverage["住院前后门急诊"] = f"住院前{pre_match.group(1)}天+出院后{pre_match.group(2)}天"

    # 门诊
    if re.search(r"门诊医疗|门急诊|门诊手术", text):
        coverage["门诊"] = True
        outpatient_limit = re.search(r"门诊.*?[限额以].*?(\d+)\s*[万]?元", text)
        if outpatient_limit:
            coverage["门诊限额"] = outpatient_limit.group(0)

    # 特药
    drug_match = re.search(r"(\d+)\s*种.*?特[药药品]", text)
    if drug_match:
        coverage["特药种类"] = int(drug_match.group(1))

    # CAR-T
    if "CAR-T" in text or "car-t" in text.lower() or "阿基仑赛" in text or "瑞基奥仑赛" in text:
        coverage["含CAR-T"] = True

    # 外购药
    if re.search(r"外购药|院外购药|院外药", text):
        coverage["外购药"] = True

    # 质子重离子
    proton_match = re.search(r"质子重离子.*?保额\s*(\d+)\s*万", text)
    if proton_match:
        coverage["质子重离子保额"] = int(proton_match.group(1)) * 10000
    elif "质子重离子" in text:
        coverage["质子重离子"] = True

    # 特需/国际部
    if re.search(r"特需.*?[医部]|国际部|VIP部", text):
        coverage["特需国际部"] = True

    # 私立医院
    if re.search(r"私立医院|民营医院|民营医疗", text):
        coverage["私立医院"] = True
        priv_count = re.search(r"(\d+)\s*家.*?(?:私立|民营)", text)
        if priv_count:
            coverage["私立医院数量"] = int(priv_count.group(1))

    # 康复
    if re.search(r"康复住院|康复治疗|康复医疗", text):
        coverage["康复保障"] = True

    # 住院津贴
    if re.search(r"住院津贴|住院护工", text):
        coverage["住院津贴"] = True
        daily_match = re.search(r"(\d+)\s*元/天", text)
        if daily_match:
            coverage["住院津贴金额"] = f"{daily_match.group(1)}元/天"

    # 增值服务
    services = []
    service_keywords = {
        "绿通": "就医绿通",
        "垫付": "医疗垫付",
        "直付": "直付服务",
        "在线问诊": "在线问诊",
        "视频问诊": "视频问诊",
        "送药上门": "送药上门",
        "基因检测": "基因检测",
        "术后护理": "术后护理",
        "二次诊疗": "二次诊疗",
    }
    for kw, name in service_keywords.items():
        if kw in text:
            services.append(name)
    if services:
        coverage["增值服务"] = services

    result["coverage"] = coverage

    # === 就诊医院范围 ===
    hospital = extract_field(text, [
        r"就诊医院[：:](.+?)[。\n]",
        r"医院范围[：:](.+?)[。\n]",
        r"限.*?(二级.*?医院.*?普通部)",
    ], default=None)
    if hospital and hospital != "未提取到":
        result["hospital_scope"] = hospital[:200]

    # === 责任免除（提取关键项）===
    exclusions = []
    exclusion_keywords = [
        "既往症", "等待期", "精神", "遗传", "先天", "整形", "美容",
        "怀孕", "流产", "分娩", "牙科", "视力矫正", "高风险运动",
        "艾滋病", "战争", "核辐射", "自伤", "自杀", "犯罪",
    ]
    for kw in exclusion_keywords:
        if kw in text:
            exclusions.append(kw)
    result["exclusion_keywords"] = exclusions

    # === 既往症处理 ===
    if "既往症" in text:
        if re.search(r"既往症.*?可赔|既往症.*?保障|一般既往症", text):
            result["pre_existing_conditions"] = "可保可赔"
        elif re.search(r"既往症.*?不承担|既往症.*?免责|既往症.*?除外", text):
            result["pre_existing_conditions"] = "免责"
        else:
            result["pre_existing_conditions"] = "需人工确认"

    return result


def parse_feerate_pdf(pdf_path):
    """解析费率表PDF，提取各年龄段保费"""
    text = extract_text(pdf_path)
    result = {
        "feerate_source": os.path.basename(pdf_path),
    }

    # 提取有社保保费表
    # 格式: [年龄区间] 有社保价格 无社保价格
    feerate_data = {}

    # 匹配模式: [min,max] price_with_ssi price_without_ssi
    rows = re.findall(r'\[(\d+),(\d+)\]\s+([\d.]+)\s+([\d.]+)', text)
    if rows:
        result["feerate_table"] = []
        for row in rows:
            entry = {
                "age_min": int(row[0]),
                "age_max": int(row[1]),
                "premium_with_ssi": float(row[2]),
                "premium_without_ssi": float(row[3]),
            }
            result["feerate_table"].append(entry)

        # 提取关键年龄段保费供快速参考
        key_ages = {30: "[26,30]", 40: "[36,40]", 50: "[46,50]", 60: "[56,60]"}
        result["key_age_premiums"] = {}
        for age, bracket in key_ages.items():
            for entry in result["feerate_table"]:
                if f"[{entry['age_min']},{entry['age_max']}]" == bracket:
                    result["key_age_premiums"][f"{age}岁_有社保"] = entry["premium_with_ssi"]
                    result["key_age_premiums"][f"{age}岁_无社保"] = entry["premium_without_ssi"]
                    break

    # 尝试提取可选加油包保费（如果有多个表格）
    addon_match = re.search(r'可选加油包.*?补充责任', text)
    if addon_match:
        result["has_addons"] = True

    return result


def merge_results(terms_result, feerate_result=None):
    """合并条款解析结果和费率表结果"""
    merged = {**terms_result}
    if feerate_result:
        merged["feerate"] = feerate_result
        if "key_age_premiums" in feerate_result:
            merged["premium_reference"] = feerate_result["key_age_premiums"]
    return merged


def main():
    if len(sys.argv) < 2:
        print("用法:")
        print("  python3 parse_insurance_pdf.py <条款PDF> [费率表PDF]")
        print("  python3 parse_insurance_pdf.py --dir <目录>")
        sys.exit(1)

    if sys.argv[1] == "--dir":
        # 批量模式
        directory = sys.argv[2]
        results = []
        for f in sorted(os.listdir(directory)):
            if f.endswith(".pdf"):
                pdf_path = os.path.join(directory, f)
                try:
                    result = parse_terms_pdf(pdf_path)
                    results.append(result)
                    print(f"✓ {f}", file=sys.stderr)
                except Exception as e:
                    print(f"✗ {f}: {e}", file=sys.stderr)
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        # 单文件模式
        terms_pdf = sys.argv[1]
        feerate_pdf = sys.argv[2] if len(sys.argv) > 2 else None

        terms_result = parse_terms_pdf(terms_pdf)
        feerate_result = parse_feerate_pdf(feerate_pdf) if feerate_pdf else None

        result = merge_results(terms_result, feerate_result)
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
