"""Probe Groww __NEXT_DATA__ structure."""
from __future__ import annotations

import json
import re
import urllib.request
from pathlib import Path

URL = "https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth"
OUT = Path(__file__).resolve().parents[1] / "data" / "probe_next_data_keys.json"


def find_keys(obj, needles, path="", depth=0):
    hits = []
    if depth > 8:
        return hits
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = f"{path}.{k}" if path else str(k)
            if any(n in str(k).lower() for n in needles):
                hits.append({"path": p, "type": type(v).__name__, "sample": str(v)[:200]})
            if isinstance(v, (dict, list)):
                hits.extend(find_keys(v, needles, p, depth + 1))
    elif isinstance(obj, list):
        for i, v in enumerate(obj[:40]):
            hits.extend(find_keys(v, needles, f"{path}[{i}]", depth + 1))
    return hits


def main() -> None:
    req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0 FactsDeskIngest/0.1"})
    html = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")
    m = re.search(r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if not m:
        raise SystemExit("no __NEXT_DATA__")
    data = json.loads(m.group(1))
    page = data["props"]["pageProps"]
    needles = [
        "expense",
        "exit",
        "sip",
        "min",
        "risk",
        "benchmark",
        "aum",
        "category",
        "manager",
        "nav",
        "lock",
        "scheme",
        "fund",
    ]
    hits = find_keys(page, needles)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"page_keys": list(page.keys()), "hits": hits[:200]}, indent=2), encoding="utf-8")
    print("page_keys", list(page.keys()))
    print("hits", len(hits))
    for h in hits[:60]:
        print(h["path"], "=>", h["type"], h["sample"])


if __name__ == "__main__":
    main()
