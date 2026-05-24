#!/usr/bin/env python3
"""
Atualiza documentação seguindo Diataxis.
"""
import argparse

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--feature", required=True)
    args = p.parse_args()
    print(f"Updating docs for {args.feature}")
    print("Checking docs/ for stale content...")
    print("[Integrar com diff checker e Diataxis mapper]")
