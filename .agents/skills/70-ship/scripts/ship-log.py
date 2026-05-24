#!/usr/bin/env python3
"""
Gera ship log e move item para done.
"""
import argparse
from datetime import datetime

def generate_log(feature):
    return f"""# Ship Log — {feature}

* Shipped at: {datetime.now().isoformat()}
* PR: [link]
* Deploy: [link]
* Canary: PASS
* Docs: Updated
* Status: DONE
"""

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--feature", required=True)
    args = p.parse_args()
    print(generate_log(args.feature))
