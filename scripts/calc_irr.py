#!/usr/bin/env python3
"""
保险产品IRR/ROI计算工具
支持：增额终身寿IRR、年金险IRR、医疗险性价比对比

用法:
  python3 calc_irr.py --type endowment --premium 10000 --years 10 --cash-value 120000
  python3 calc_irr.py --type annuity --premium 50000 --years 5 --annual-payout 8000 --payout-years 30
  python3 calc_irr.py --type medical --premium 500 --deductible 10000 --coverage 6000000
"""

import sys
import argparse
import math


def calc_irr(premium, years, cash_value):
    """
    计算增额终身寿IRR
    premium: 年缴保费
    years: 缴费年限
    cash_value: 第N年末现金价值
    """
    # 用二分法求IRR
    low, high = -0.5, 1.0
    for _ in range(1000):
        mid = (low + high) / 2
        # 计算现值
        pv = 0
        for i in range(years):
            pv += premium / (1 + mid) ** (i + 1)
        pv -= cash_value / (1 + mid) ** years
        if pv > 0:
            low = mid
        else:
            high = mid
    return mid


def calc_annuity_irr(premium, pay_years, annual_payout, payout_start_year, payout_years):
    """
    计算年金险IRR
    premium: 年缴保费
    pay_years: 缴费年限
    annual_payout: 每年领取金额
    payout_start_year: 开始领取年份（第几年开始）
    payout_years: 领取年数
    """
    low, high = -0.3, 0.5
    for _ in range(1000):
        mid = (low + high) / 2
        npv = 0
        # 缴费期现金流（负）
        for i in range(pay_years):
            npv -= premium / (1 + mid) ** (i + 1)
        # 领取期现金流（正）
        for i in range(payout_years):
            year = payout_start_year + i
            npv += annual_payout / (1 + mid) ** year
        if npv > 0:
            low = mid
        else:
            high = mid
    return mid


def calc_medical_value(premium, deductible, coverage, scenarios=None):
    """
    计算医疗险不同场景下的实际花费
    premium: 年保费
    deductible: 免赔额
    coverage: 保额
    scenarios: 使用场景列表
    """
    if scenarios is None:
        scenarios = [
            {"name": "轻度（门诊1-2次）", "expense": 1500, "ssi_cover": 1000, "covered": False},
            {"name": "中度（住院1次）", "expense": 40000, "ssi_cover": 26000, "covered": True},
            {"name": "重度（大病住院）", "expense": 300000, "ssi_cover": 165000, "covered": True},
        ]

    results = []
    for s in scenarios:
        out_of_pocket_ssi = s["expense"] - s["ssi_cover"]  # 社保报销后自付
        if s["covered"]:
            insurance_pay = max(0, out_of_pocket_ssi - deductible)
            actual_oop = out_of_pocket_ssi - insurance_pay
        else:
            insurance_pay = 0
            actual_oop = out_of_pocket_ssi

        total_cost = premium + actual_oop
        results.append({
            "scenario": s["name"],
            "total_expense": s["expense"],
            "ssi_covered": s["ssi_cover"],
            "self_pay": out_of_pocket_ssi,
            "insurance_paid": insurance_pay,
            "actual_out_of_pocket": actual_oop,
            "total_cost_with_premium": total_cost,
        })
    return results


def compare_products(products):
    """
    对比多款产品的IRR或性价比
    products: [{"name": str, "premium": float, "years": int, "cash_value": float}, ...]
    """
    results = []
    for p in products:
        if "cash_value" in p:
            irr = calc_irr(p["premium"], p["years"], p["cash_value"])
            results.append({
                "name": p["name"],
                "irr": irr,
                "irr_pct": f"{irr*100:.2f}%",
                "total_premium": p["premium"] * p["years"],
                "cash_value": p["cash_value"],
                "gain": p["cash_value"] - p["premium"] * p["years"],
            })
    results.sort(key=lambda x: x["irr"], reverse=True)
    return results


def main():
    parser = argparse.ArgumentParser(description="保险产品IRR/ROI计算")
    parser.add_argument("--type", choices=["endowment", "annuity", "medical", "compare"], required=True)
    parser.add_argument("--premium", type=float, help="年缴保费")
    parser.add_argument("--years", type=int, help="缴费年限")
    parser.add_argument("--cash-value", type=float, help="现金价值")
    parser.add_argument("--annual-payout", type=float, help="年金每年领取")
    parser.add_argument("--payout-years", type=int, help="领取年数")
    parser.add_argument("--payout-start", type=int, default=1, help="开始领取年份")
    parser.add_argument("--deductible", type=float, default=10000, help="免赔额")
    parser.add_argument("--coverage", type=float, default=6000000, help="保额")

    args = parser.parse_args()
    import json

    if args.type == "endowment":
        irr = calc_irr(args.premium, args.years, args.cash_value)
        total = args.premium * args.years
        gain = args.cash_value - total
        print(json.dumps({
            "type": "增额终身寿IRR",
            "annual_premium": args.premium,
            "years": args.years,
            "total_premium": total,
            "cash_value": args.cash_value,
            "gain": gain,
            "irr": round(irr, 4),
            "irr_pct": f"{irr*100:.2f}%",
        }, ensure_ascii=False, indent=2))

    elif args.type == "annuity":
        irr = calc_annuity_irr(args.premium, args.years, args.annual_payout, args.payout_start, args.payout_years)
        total_paid = args.premium * args.years
        total_received = args.annual_payout * args.payout_years
        print(json.dumps({
            "type": "年金险IRR",
            "annual_premium": args.premium,
            "pay_years": args.years,
            "total_paid": total_paid,
            "annual_payout": args.annual_payout,
            "payout_years": args.payout_years,
            "total_received": total_received,
            "irr": round(irr, 4),
            "irr_pct": f"{irr*100:.2f}%",
        }, ensure_ascii=False, indent=2))

    elif args.type == "medical":
        results = calc_medical_value(args.premium, args.deductible, args.coverage)
        print(json.dumps({
            "type": "医疗险性价比分析",
            "annual_premium": args.premium,
            "deductible": args.deductible,
            "coverage": args.coverage,
            "scenarios": results,
        }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
