#!/usr/bin/env python3
"""
保险核心指标计算工具
支持：IRR、回本年限、杠杆倍数、保障缺口、保费占比、医疗险场景分析

用法:
  python3 calc_insurance.py irr --premium 10000 --years 10 --cash-value 120000
  python3 calc_insurance.py breakeven --premium 10000 --years 10 --cash-values 95000,102000,110000
  python3 calc_insurance.py leverage --premium 5000 --years 20 --coverage 500000
  python3 calc_insurance.py gap --income 200000 --existing 300000 --type critical
  python3 calc_insurance.py medical --premium 500 --deductible 10000
  python3 calc_insurance.py ratio --income 200000 --total-premium 15000
"""

import sys
import json
import argparse


def calc_irr(premium, years, cash_value):
    """计算增额终身寿/年金险的IRR（内部收益率）"""
    # 用Newton法求IRR，初始猜测3%
    r = 0.03
    for _ in range(1000):
        npv = sum(premium / (1 + r) ** (i + 1) for i in range(years)) - cash_value / (1 + r) ** years
        # NPV对r的导数
        dnpv = sum(-premium * (i + 1) / (1 + r) ** (i + 2) for i in range(years)) + cash_value * years / (1 + r) ** (years + 1)
        if abs(dnpv) < 1e-12:
            break
        r_new = r - npv / dnpv
        if abs(r_new - r) < 1e-10:
            return r_new
        r = r_new
        # 防止发散
        if r < -0.5 or r > 0.5:
            r = 0.03
            break
    # Newton法失败时用二分法（限制在合理范围）
    low, high = -0.1, 0.3
    for _ in range(1000):
        mid = (low + high) / 2
        npv = sum(premium / (1 + mid) ** (i + 1) for i in range(years)) - cash_value / (1 + mid) ** years
        if npv > 0:
            high = mid
        else:
            low = mid
    return mid


def calc_annuity_irr(premium, pay_years, annual_payout, payout_start, payout_years):
    """计算年金险IRR"""
    low, high = -0.3, 0.5
    for _ in range(1000):
        mid = (low + high) / 2
        npv = -sum(premium / (1 + mid) ** (i + 1) for i in range(pay_years))
        npv += sum(annual_payout / (1 + mid) ** (payout_start + i) for i in range(payout_years))
        if npv > 0:
            low = mid
        else:
            high = mid
    return mid


def calc_breakeven(premium, years, cash_values_by_year):
    """计算回本年限：现金价值超过总保费的年份"""
    total_premium = premium * years
    for year, cv in enumerate(cash_values_by_year, 1):
        if cv >= total_premium:
            return {"breakeven_year": year, "total_premium": total_premium, "cash_value_at_breakeven": cv}
    return {"breakeven_year": None, "total_premium": total_premium, "note": "在给定年限内未回本"}


def calc_leverage(premium_per_year, pay_years, coverage):
    """计算杠杆倍数：保额 ÷ 总保费"""
    total_premium = premium_per_year * pay_years
    return {
        "total_premium": total_premium,
        "coverage": coverage,
        "leverage_ratio": round(coverage / total_premium, 2),
        "interpretation": f"每花1元保费，撬动{round(coverage / total_premium, 1)}元保障"
    }


def calc_coverage_gap(income, existing_coverage, coverage_type="critical"):
    """
    计算保障缺口
    coverage_type: critical(重疾), life(寿险), medical(医疗)
    """
    multipliers = {
        "critical": {"recommended_years": 3, "note": "重疾保额建议覆盖3-5年年收入"},
        "life": {"recommended_years": 10, "note": "寿险保额建议覆盖10-20年年收入（含房贷等负债）"},
        "medical": {"recommended_years": 0, "note": "医疗险主要看免赔额和续保方式，不以保额为核心"},
    }
    m = multipliers.get(coverage_type, multipliers["critical"])
    recommended = income * m["recommended_years"]
    gap = max(0, recommended - existing_coverage)
    return {
        "income": income,
        "existing_coverage": existing_coverage,
        "recommended_coverage": recommended,
        "gap": gap,
        "note": m["note"],
    }


def calc_premium_ratio(income, total_annual_premium):
    """计算保费占收入比例"""
    ratio = total_annual_premium / income
    if ratio < 0.03:
        level = "偏低，保障可能不足"
    elif ratio <= 0.10:
        level = "合理范围"
    elif ratio <= 0.15:
        level = "偏高，注意缴费压力"
    else:
        level = "过高，可能影响生活质量"
    return {
        "income": income,
        "total_premium": total_annual_premium,
        "ratio": round(ratio * 100, 1),
        "level": level,
        "recommendation": "建议保费占家庭年收入的5-10%",
    }


def calc_medical_scenario(premium, deductible):
    """医疗险不同场景下的实际花费分析"""
    scenarios = [
        {"name": "日常门诊", "expense": 1500, "ssi_cover": 800, "inpatient": False},
        {"name": "小病住院", "expense": 20000, "ssi_cover": 13000, "inpatient": True},
        {"name": "中等住院", "expense": 50000, "ssi_cover": 32000, "inpatient": True},
        {"name": "大病住院", "expense": 300000, "ssi_cover": 165000, "inpatient": True},
        {"name": "重病长期治疗", "expense": 800000, "ssi_cover": 400000, "inpatient": True},
    ]
    results = []
    for s in scenarios:
        self_pay_after_ssi = s["expense"] - s["ssi_cover"]
        if s["inpatient"]:
            insurance_pay = max(0, self_pay_after_ssi - deductible)
            actual_oop = self_pay_after_ssi - insurance_pay
        else:
            insurance_pay = 0
            actual_oop = self_pay_after_ssi
        results.append({
            "scenario": s["name"],
            "total_expense": s["expense"],
            "ssi_covered": s["ssi_cover"],
            "self_pay_after_ssi": self_pay_after_ssi,
            "insurance_paid": insurance_pay,
            "actual_out_of_pocket": actual_oop,
            "total_cost_with_premium": premium + actual_oop,
        })
    return results


def main():
    parser = argparse.ArgumentParser(description="保险核心指标计算")
    sub = parser.add_subparsers(dest="command")

    # IRR
    p = sub.add_parser("irr", help="计算IRR")
    p.add_argument("--premium", type=float, required=True)
    p.add_argument("--years", type=int, required=True)
    p.add_argument("--cash-value", type=float, required=True)

    # 回本年限
    p = sub.add_parser("breakeven", help="计算回本年限")
    p.add_argument("--premium", type=float, required=True)
    p.add_argument("--years", type=int, required=True)
    p.add_argument("--cash-values", type=str, required=True, help="逗号分隔的各年末现金价值")

    # 杠杆倍数
    p = sub.add_parser("leverage", help="计算杠杆倍数")
    p.add_argument("--premium", type=float, required=True)
    p.add_argument("--years", type=int, required=True)
    p.add_argument("--coverage", type=float, required=True)

    # 保障缺口
    p = sub.add_parser("gap", help="计算保障缺口")
    p.add_argument("--income", type=float, required=True)
    p.add_argument("--existing", type=float, required=True)
    p.add_argument("--type", choices=["critical", "life", "medical"], default="critical")

    # 保费占比
    p = sub.add_parser("ratio", help="计算保费占比")
    p.add_argument("--income", type=float, required=True)
    p.add_argument("--premium", type=float, required=True)

    # 医疗险场景分析
    p = sub.add_parser("medical", help="医疗险场景分析")
    p.add_argument("--premium", type=float, required=True)
    p.add_argument("--deductible", type=float, default=10000)

    args = parser.parse_args()

    if args.command == "irr":
        irr = calc_irr(args.premium, args.years, args.cash_value)
        total = args.premium * args.years
        print(json.dumps({
            "type": "IRR计算",
            "annual_premium": args.premium,
            "years": args.years,
            "total_premium": total,
            "cash_value": args.cash_value,
            "gain": args.cash_value - total,
            "irr": round(irr, 4),
            "irr_pct": f"{irr*100:.2f}%",
        }, ensure_ascii=False, indent=2))

    elif args.command == "breakeven":
        cvs = [float(x) for x in args.cash_values.split(",")]
        result = calc_breakeven(args.premium, args.years, cvs)
        result["type"] = "回本年限"
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args.command == "leverage":
        result = calc_leverage(args.premium, args.years, args.coverage)
        result["type"] = "杠杆倍数"
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args.command == "gap":
        result = calc_coverage_gap(args.income, args.existing, args.type)
        result["type"] = "保障缺口"
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args.command == "ratio":
        result = calc_premium_ratio(args.income, args.premium)
        result["type"] = "保费占比"
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args.command == "medical":
        results = calc_medical_scenario(args.premium, args.deductible)
        print(json.dumps({
            "type": "医疗险场景分析",
            "annual_premium": args.premium,
            "deductible": args.deductible,
            "scenarios": results,
        }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
