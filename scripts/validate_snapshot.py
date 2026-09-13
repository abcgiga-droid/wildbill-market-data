#!/usr/bin/env python3
"""Validate a generated snapshot before it is ever published."""
import argparse
import hashlib
import json
from pathlib import Path

REQUIRED = {"symbol", "source", "fetched", "candles", "vols", "bars5m", "bars1h"}

def valid_bar(bar, time_type):
    return (isinstance(bar, dict) and isinstance(bar.get("time"), time_type)
            and all(isinstance(bar.get(k), (int, float)) and bar[k] > 0
                    for k in ("open", "high", "low", "close")))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="build/data")
    parser.add_argument("--manifest", default="build/manifest.json")
    args = parser.parse_args()
    data_dir = Path(args.data_dir)
    errors, files = [], []
    for path in sorted(data_dir.glob("*.json")):
        try:
            payload = json.loads(path.read_text())
            missing = REQUIRED - set(payload)
            if missing or not payload["candles"] or not all(valid_bar(x, str) for x in payload["candles"]):
                raise ValueError(f"missing={sorted(missing)} or invalid daily bars")
            if not all(valid_bar(x, int) for x in payload["bars5m"] + payload["bars1h"]):
                raise ValueError("invalid intraday bars")
            files.append({"symbol": payload["symbol"], "file": path.name,
                          "bytes": path.stat().st_size,
                          "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                          "daily_bars": len(payload["candles"])})
        except Exception as exc:
            errors.append(f"{path}: {exc}")
    if errors or not files:
        raise SystemExit("Snapshot validation failed:\n" + "\n".join(errors or ["no JSON files"]))
    manifest = Path(args.manifest)
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps({"schema_version": 1, "symbols": len(files), "files": files},
                                   indent=2, sort_keys=True) + "\n")
    print(f"Validated {len(files)} files and wrote {manifest}")

if __name__ == "__main__":
    main()
