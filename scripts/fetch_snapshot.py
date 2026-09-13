#!/usr/bin/env python3
"""Fetch normalized OHLCV snapshot files, preserving prior intraday archives."""
import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yfinance as yf

ALIASES = {"BF.B": "BF-B", "BRK.B": "BRK-B", "SQ": "XYZ"}
UP, DOWN = "rgba(38,166,154,0.5)", "rgba(239,83,80,0.5)"

def as_utc_epoch(value):
    stamp = pd.Timestamp(value)
    if stamp.tzinfo is None:
        stamp = stamp.tz_localize("UTC")
    else:
        stamp = stamp.tz_convert("UTC")
    return int(stamp.timestamp())

def bars(frame):
    output = []
    if frame is None or frame.empty:
        return output
    for timestamp, row in frame.iterrows():
        try:
            o, h, l, c = (float(row[key]) for key in ("Open", "High", "Low", "Close"))
            volume = int(row.get("Volume", 0) or 0)
        except (KeyError, TypeError, ValueError):
            continue
        if o > 0 and h > 0 and l > 0 and c > 0:
            output.append({"time": as_utc_epoch(timestamp), "open": round(o, 2),
                           "high": round(h, 2), "low": round(l, 2),
                           "close": round(c, 2), "volume": volume})
    return output

def merge(old, new):
    by_time = {item["time"]: item for item in (old or [])}
    by_time.update({item["time"]: item for item in (new or [])})
    return [by_time[key] for key in sorted(by_time)]

def previous(path):
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}

def fetch(symbol, include_intraday):
    ticker = yf.Ticker(ALIASES.get(symbol, symbol))
    daily = ticker.history(period="5y", interval="1d", auto_adjust=False)
    if daily is None or daily.empty:
        raise RuntimeError("empty daily history")
    candles, vols = [], []
    for timestamp, row in daily.iterrows():
        try:
            o, h, l, c = (float(row[key]) for key in ("Open", "High", "Low", "Close"))
            volume = int(row.get("Volume", 0) or 0)
        except (KeyError, TypeError, ValueError):
            continue
        if o > 0 and h > 0 and l > 0 and c > 0:
            day = pd.Timestamp(timestamp).strftime("%Y-%m-%d")
            candles.append({"time": day, "open": round(o, 2), "high": round(h, 2),
                            "low": round(l, 2), "close": round(c, 2)})
            vols.append({"time": day, "value": volume, "color": UP if c >= o else DOWN})
    if len(candles) < 30:
        raise RuntimeError(f"too few daily bars ({len(candles)})")
    five_minute, hourly = [], []
    if include_intraday:
        try:
            five_minute = bars(ticker.history(period="60d", interval="5m", auto_adjust=False))
        except Exception as exc:
            print(f"  {symbol} 5m unavailable: {exc}")
        try:
            hourly = bars(ticker.history(period="730d", interval="1h", auto_adjust=False))
        except Exception as exc:
            print(f"  {symbol} 1h unavailable: {exc}")
    return candles, vols, five_minute, hourly

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbols-file", default="build/symbols.txt")
    parser.add_argument("--output-dir", default="build/data")
    parser.add_argument("--previous-dir", default="previous/data")
    parser.add_argument("--daily-only", action="store_true")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--min-success-rate", type=float, default=0.95)
    args = parser.parse_args()
    symbols = [line.strip().upper() for line in Path(args.symbols_file).read_text().splitlines()
               if line.strip() and not line.startswith("#")]
    if args.limit:
        symbols = symbols[:args.limit]
    if not symbols:
        raise SystemExit("No symbols supplied.")
    output_dir, previous_dir = Path(args.output_dir), Path(args.previous_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    failed = []
    for number, symbol in enumerate(symbols, 1):
        prior = previous(previous_dir / f"{symbol}.json")
        try:
            candles, vols, fresh5m, fresh1h = fetch(symbol, not args.daily_only)
            payload = {"symbol": symbol, "source": "yfinance",
                       "fetched": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                       "candles": candles, "vols": vols,
                       "bars5m": merge(prior.get("bars5m"), fresh5m),
                       "bars1h": merge(prior.get("bars1h"), fresh1h)}
            target = output_dir / f"{symbol}.json"
            temporary = target.with_suffix(".json.tmp")
            temporary.write_text(json.dumps(payload, separators=(",", ":")))
            temporary.replace(target)
            print(f"[{number}/{len(symbols)}] {symbol} daily={len(candles)}"
                  f" 5m={len(payload['bars5m'])} 1h={len(payload['bars1h'])}")
        except Exception as exc:
            failed.append(symbol)
            print(f"[{number}/{len(symbols)}] {symbol} FAILED: {exc}")
        time.sleep(1)
    rate = (len(symbols) - len(failed)) / len(symbols)
    report = {"requested": len(symbols), "succeeded": len(symbols) - len(failed),
              "failed": failed, "success_rate": rate}
    Path("build/fetch-report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))
    if rate < args.min_success_rate:
        raise SystemExit(f"success rate {rate:.1%} is below {args.min_success_rate:.1%}")

if __name__ == "__main__":
    main()
