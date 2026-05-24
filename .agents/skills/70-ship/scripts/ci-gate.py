#!/usr/bin/env python3
"""
Aguarda CI verde.
"""
import argparse, time

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--pr", required=True)
    args = p.parse_args()
    print(f"Waiting for CI on PR #{args.pr}...")
    print("[Integrar com GitHub Actions / GitLab CI API]")
