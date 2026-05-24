#!/usr/bin/env python3
"""
Calcula WSJF (Weighted Shortest Job First).
Usage: python wsjf-calculator.py --business-value 8 --risk-reduction 5 --time-criticality 7 --job-size 40
"""
import argparse

def calc_wsjf(bv, rr, tc, js):
    cod = bv + rr + tc
    return cod / js

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--business-value", type=int, required=True)
    p.add_argument("--risk-reduction", type=int, required=True)
    p.add_argument("--time-criticality", type=int, required=True)
    p.add_argument("--job-size", type=float, required=True)
    args = p.parse_args()
    score = calc_wsjf(args.business_value, args.risk_reduction, args.time_criticality, args.job_size)
    print(f"WSJF Score: {score:.2f}")
    print(f"Cost of Delay: {args.business_value + args.risk_reduction + args.time_criticality}")
    print(f"Job Size: {args.job_size}h")
