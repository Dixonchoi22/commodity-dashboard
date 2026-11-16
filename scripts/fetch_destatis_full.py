"""Destatis 61111-0006 (CPI Germany, months, COICOP 2-/3-/4-/5-/10-digit codes) -> data/destatis_full.json

The 10-digit national items (e.g. CC13-0111101100 Rice, CC13-0213100100 Pilsner) live in the variable CC13Z1
(687 values, every code padded to 10 digits).  Only food (CC13-01...) and alcohol (CC13-02...) are kept.
Needs GENESIS_TOKEN.  Pulled in year chunks so no single synchronous download is too large.
    GENESIS_TOKEN=... python3 scripts/fetch_destatis_full.py
"""
from __future__ import annotations
import csv, io, json, os, re, sys, urllib.error, urllib.parse, urllib.request, zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "destatis_full.json"
URL = "https://genesis.destatis.de/genesisWS/rest/2020/data/tablefile"
TABLE = "61111-0006"
CHUNKS = [(y, y) for y in range(2015, 2027)]   # one year per call: 5 years at once is 'too big for dialogue-processing'


def pull(token: str, y0: int, y1: int) -> bytes:
    body = urllib.parse.urlencode({
        "name": TABLE, "area": "all", "format": "ffcsv", "language": "en", "compress": "false", "job": "false",
        "startyear": str(y0), "endyear": str(y1), "classifyingvariable1": "CC13Z1",
    }).encode()
    req = urllib.request.Request(URL, data=body, method="POST", headers={
        "username": token, "password": "", "Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=420) as r:
        data = r.read()
    if data.startswith(b"PK"):
        z = zipfile.ZipFile(io.BytesIO(data)); data = z.read(z.namelist()[0])
    return data


def main() -> None:
    token = os.environ.get("GENESIS_TOKEN", "").strip()
    if not token:
        sys.exit("GENESIS_TOKEN is not set")
    labels: dict[str, str] = {}
    vals: dict[str, dict[str, float]] = {}
    for y0, y1 in CHUNKS:
        try:
            text = pull(token, y0, y1).decode("utf-8-sig", "replace")
        except (urllib.error.URLError, TimeoutError) as e:
            print(f"  {y0}-{y1}: failed ({type(e).__name__}: {str(e)[:100]})", flush=True)
            continue
        if "statistics_code" not in text[:300]:
            print(f"  {y0}-{y1}: not a flat csv: {text[:160]!r}", flush=True)
            continue
        n = 0
        for r in csv.DictReader(text.splitlines(), delimiter=";"):
            code = ""
            label = ""
            for i in (1, 2, 3, 4):
                c = r.get(f"{i}_variable_attribute_code") or ""
                if c.startswith("CC13-"):
                    code, label = c, (r.get(f"{i}_variable_attribute_label") or "").strip()
            mm = re.match(r"MONAT(\d\d)", r.get("1_variable_attribute_code") or "")
            if not code or not mm or not (code.startswith("CC13-01") or code.startswith("CC13-02")):
                continue
            try:
                v = float((r.get("value") or "").replace(",", "."))
            except ValueError:
                continue
            ym = f"{int(r['time']):04d}-{mm.group(1)}"
            labels[code] = label
            vals.setdefault(code, {})[ym] = v
            n += 1
        print(f"  {y0}-{y1}: {n} observations, {len(vals)} codes so far", flush=True)
    if not vals:
        sys.exit("no data pulled - keeping the previous file")
    months = sorted({m for s in vals.values() for m in s})
    series = [{"code": c, "label": labels[c], "vals": [vals[c].get(m) for m in months]} for c in sorted(vals, key=lambda k: k[5:])]
    OUT.write_text(json.dumps({"source": "Destatis Genesis Online - table 61111-0006", "base": "2020 = 100",
                               "months": months, "series": series}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}: {len(series)} codes, {months[0]}..{months[-1]}, {OUT.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
