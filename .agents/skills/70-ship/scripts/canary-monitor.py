#!/usr/bin/env python3
"""
Monitoramento pós-deploy (canary).
"""
import argparse, time

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--feature", required=True)
    p.add_argument("--duration", type=int, default=15)
    args = p.parse_args()
    print(f"Monitoring {args.feature} for {args.duration} minutes...")
    print("[Integrar com Datadog / New Relic / Prometheus]")
