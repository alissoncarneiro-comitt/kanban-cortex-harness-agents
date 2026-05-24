#!/usr/bin/env python3
"""
Gera teste de regressão a partir de descrição de bug.
"""
import argparse

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--bug", required=True)
    p.add_argument("--feature", required=True)
    args = p.parse_args()
    test_name = args.bug.lower().replace(" ", "_")[:30]
    print(f"Generated test: tests/regression/{args.feature}_{test_name}.test.ts")
    print("[Template de teste gerado — implementar reprodução do bug]")
