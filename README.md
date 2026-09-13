# Wildbill Market Data

Independent market-data pipeline for [wildbill-charts](https://github.com/abcgiga-droid/wildbill-charts).

It owns symbol discovery, collection, normalization, validation, versioned snapshot publication, and the initial transfer of snapshots to the chart-hosting VM. The chart application remains a read-only consumer of `/data/`.

## Data flow

```text
wildbill-charts/app/markets.js
        │ priceSymbols
        ▼
sync_symbols.py → fetch_snapshot.py → build/data/*.json + build/manifest.json
                                         │ validate
                                         ▼
                         GitHub Actions → SSH/rsync → VM releases/<id>
                                                           │ atomic symlink
                                                           ▼
                                                     /srv/wildbill-data/current
```

## Quick start

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python scripts/sync_symbols.py
python scripts/fetch_snapshot.py --symbols-file build/symbols.txt
python scripts/validate_snapshot.py
```

Collection uses `yfinance` for now, matching the existing chart project. Do not treat this source as licensed for public/commercial redistribution without separately confirming the provider terms and replacing the adapter where necessary.

## VM publishing

The workflow at `.github/workflows/refresh-and-publish.yml` can run manually or daily. Add these repository secrets before enabling VM publishing:

- `DEPLOY_HOST` — VM hostname or IP
- `DEPLOY_USER` — restricted SSH deployment user
- `DEPLOY_SSH_KEY` — private key for that user
- `DEPLOY_PATH` — absolute data root, e.g. `/srv/wildbill-data`
- `DEPLOY_KNOWN_HOSTS` — the VM's pinned SSH host-key line from `ssh-keyscan -H HOST`

The workflow uploads each run to `$DEPLOY_PATH/releases/<run-id>` and switches `$DEPLOY_PATH/current` only after the upload succeeds. Configure nginx to serve `$DEPLOY_PATH/current/data/` at `/data/`; see `deploy/nginx-data.conf`.

## Repository policy

Generated data (`build/`) and secrets never belong in Git. Each published snapshot includes source, fetch timestamp, symbol count, and per-file checksums in `manifest.json`.
