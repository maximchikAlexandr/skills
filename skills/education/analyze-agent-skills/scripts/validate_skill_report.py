#!/usr/bin/env python3
from pathlib import Path
import argparse
p=argparse.ArgumentParser();p.add_argument("report",type=Path);a=p.parse_args()
t=a.report.read_text(encoding="utf-8")
required=("1. Краткое summary","2. Анатомия skill","3. Behavior contract","4. Scenario matrix","Content-Security-Policy","noindex,nofollow,noarchive")
errors=[f"missing: {x}" for x in required if x not in t]
if "{{" in t or "}}" in t: errors.append("unresolved template token")
if any(x in t.lower() for x in ("<script","<iframe","onload=","onclick=")): errors.append("active content forbidden")
if errors: raise SystemExit("\n".join(errors))
print("skill report valid")

