#!/usr/bin/env python3
"""Extract the chart application's bounded price universe into a text file."""
import argparse
import os
import re
import urllib.request
from pathlib import Path

DEFAULT_URL = "https://raw.githubusercontent.com/abcgiga-droid/wildbill-charts/main/app/markets.js"
SYMBOL_RE = re.compile(r'"([A-Z0-9.\\-]{1,10})"')

def symbols_from_markets(text):
    symbols = set()
    for match in re.finditer(r"priceSymbols:\\s*\\[([^]]*)\\]", text):
        symbols.update(SYMBOL_RE.findall(match.group(1)))
    return sorted(symbols)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default=os.getenv("MARKETS_JS_URL", DEFAULT_URL))
    parser.add_argument("--output", default="build/symbols.txt")
    args = parser.parse_args()
    request = urllib.request.Request(args.url, headers={"User-Agent": "wildbill-market-data/1.0"})
    with urllib.request.urlopen(request, timeout=45) as response:
        text = response.read().decode("utf-8")
    symbols = symbols_from_markets(text)
    if not symbols:
        raise SystemExit("No priceSymbols found; refusing to publish an empty universe.")
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\\n".join(symbols) + "\\n", encoding="utf-8")
    print(f"Wrote {len(symbols)} symbols to {output}")

if __name__ == "__main__":
    main()
