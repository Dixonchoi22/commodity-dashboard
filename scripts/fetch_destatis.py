"""Fetch German CPI data from Destatis Genesis Online (table 61111-0004).

Destatis publishes German Verbraucherpreisindex (CPI) ~5–7 days after
month end — much fresher than Eurostat's prc_hicp_midx, which lags
3-4 months for full COICOP detail. The data we want is in:

    Table 61111-0004
    "Consumer price index: Germany, months, individual consumption by
     purpose (COICOP 2–5-digit hierarchy)"

Authentication
--------------
Destatis Genesis Online requires a free account. Register at:

    https://www-genesis.destatis.de/datenbank/online/registration

Then export the credentials as environment variables before running:

    export DESTATIS_USER=your_username
    export DESTATIS_PASS=your_password
    python scripts/fetch_destatis.py 2026-04

Output: data/{period}/destatis.json

If credentials are not set the script prints the registration URL and
exits with a non-zero status — the rest of the pipeline keeps working
because build_html.py treats destatis.json as optional.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENDPOINT = "https://www-genesis.destatis.de/genesisWS/rest/2020/data/table"
TABLE = "61111-0004"


def fetch_table(user: str, password: str, year_start: int) -> dict:
    payload = urllib.parse.urlencode({
        "username": user,
        "password": password,
        "name": TABLE,
        "format": "json",
        "startyear": str(year_start),
        "language": "en",
    }).encode()
    req = urllib.request.Request(ENDPOINT, data=payload, method="POST")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit("usage: python scripts/fetch_destatis.py <period-slug>")
    period = sys.argv[1]

    user = os.environ.get("DESTATIS_USER", "").strip()
    password = os.environ.get("DESTATIS_PASS", "").strip()
    if not (user and password):
        print("=" * 70)
        print("Destatis fetcher skipped — credentials not set.")
        print()
        print("Register a free account at:")
        print("  https://www-genesis.destatis.de/datenbank/online/registration")
        print()
        print("Then export your credentials:")
        print("  export DESTATIS_USER=<your-username>")
        print("  export DESTATIS_PASS=<your-password>")
        print()
        print("And re-run:  python scripts/fetch_destatis.py", period)
        print("=" * 70)
        sys.exit(2)

    out_path = ROOT / "data" / period / "destatis.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Fetching Destatis table {TABLE} (German CPI by COICOP)...")
    raw = fetch_table(user, password, year_start=2024)

    # Persist the raw response as-is. build_html.py / a follow-up script
    # can normalise it once we've inspected the response shape end-to-end.
    out_path.write_text(json.dumps(raw, indent=2))
    status = raw.get("Status", {})
    print(f"Wrote {out_path.relative_to(ROOT)} ({len(json.dumps(raw))} bytes)")
    print(f"  status: {status.get('Code')} {status.get('Content')}")


if __name__ == "__main__":
    main()
