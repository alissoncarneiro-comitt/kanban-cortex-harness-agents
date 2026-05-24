#!/usr/bin/env python3
"""
Gera Architecture Decision Record (ADR).
"""
import argparse
from datetime import datetime

def generate_adr(title, context, decision, consequences):
    date = datetime.now().strftime("%Y-%m-%d")
    return f"""# ADR: {title}

* Date: {date}
* Status: Proposed

## Context
{context}

## Decision
{decision}

## Consequences
{consequences}
"""

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--title", required=True)
    p.add_argument("--context", required=True)
    p.add_argument("--decision", required=True)
    p.add_argument("--consequences", required=True)
    args = p.parse_args()
    print(generate_adr(args.title, args.context, args.decision, args.consequences))
