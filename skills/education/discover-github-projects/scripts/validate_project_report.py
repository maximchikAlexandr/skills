#!/usr/bin/env python3
"""Validate structural invariants of a completed GitHub project report."""

import argparse
import re
from pathlib import Path

REQUIRED = (
    "Executive verdict",
    "Core abstractions",
    "C4",
    "deployment",
    "OS process",
    "Representative operation",
    "use cases",
    "Security",
    "Sources",
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    html = args.report.read_text(encoding="utf-8")
    errors = []
    if re.search(r"\{\{[^}]+\}\}", html):
        errors.append("unresolved template placeholders")
    for heading in REQUIRED:
        if heading.lower() not in html.lower():
            errors.append(f"missing section: {heading}")
    if not re.search(
        r"<svg\b[^>]*role=[\"']img[\"'][^>]*aria-labelledby=", html, re.IGNORECASE
    ):
        errors.append("missing accessible SVG")
    if 'http-equiv="Content-Security-Policy"' not in html:
        errors.append("missing CSP")
    if re.search(r"<script\b|<iframe\b|<form\b", html, re.IGNORECASE):
        errors.append("active content is not allowed")
    if errors:
        print("INVALID\n- " + "\n- ".join(errors))
        return 1
    print("VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
