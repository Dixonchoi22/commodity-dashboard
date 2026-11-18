"""Build the monthly Germany CPI Excel and e-mail it when Destatis has published a new month.

Data: data/destatis_full.json (Destatis 61111-0004 + 61111-0006, CPI 2020 = 100, public data only).
Layout: Typ | Code | Bezeichnung | one column per month (index only), rows in the order of
data/germany_email_layout.tsv (the code list supplied by the requester).

Sends only when the newest month with data is later than data/germany_email_state.json["last_sent_month"].
Mail settings come from environment variables (GitHub Actions secrets) - nothing is hard-coded:
    SMTP_HOST, SMTP_PORT (587 = STARTTLS, 465 = SSL; default 587), SMTP_USER, SMTP_PASSWORD,
    MAIL_FROM (default SMTP_USER), MAIL_TO (default dbeare@gategroup.com)
Without SMTP_HOST the script only builds the file and says so (exit 0).

    python3 scripts/send_germany_monthly.py --dry-run --out germany.xlsx   # build only, no mail, no state change
    python3 scripts/send_germany_monthly.py --force                        # send even if this month was already sent
"""
from __future__ import annotations

import argparse
import json
import os
import smtplib
import ssl
import sys
from email.message import EmailMessage
from pathlib import Path

import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "destatis_full.json"
LAYOUT = ROOT / "data" / "germany_email_layout.tsv"
STATE = ROOT / "data" / "germany_email_state.json"
DEFAULT_TO = "dbeare@gategroup.com"


def load():
    d = json.loads(DATA.read_text(encoding="utf-8"))
    series = {s["code"]: s for s in d["series"]}
    months = d["months"]
    rows = []
    for line in LAYOUT.read_text(encoding="utf-8").splitlines()[1:]:
        if not line.strip():
            continue
        typ, code, name = (line.split("\t") + ["", ""])[:3]
        rows.append((typ, code, name))
    return months, series, rows


def latest_month(months, series, rows):
    best = None
    for _, code, _ in rows:
        s = series.get(code)
        if not s:
            continue
        for m, v in zip(months, s["vals"]):
            if v is not None and (best is None or m > best):
                best = m
    return best


def build_xlsx(path: Path, months, series, rows):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Destatis CPI"
    head = ["Typ", "Code", "Bezeichnung"] + [f"Index {m}" for m in months]
    ws.append(head)
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="000064")
        c.alignment = Alignment(horizontal="center", vertical="center")
    missing, stale = [], []
    last_m = latest_month(months, series, rows)
    for typ, code, name in rows:
        s = series.get(code)
        if not s:
            missing.append(code)
            ws.append([typ, code, name or ""] + [None] * len(months))
            continue
        vals = list(s["vals"])
        label = name or s.get("label") or ""
        ws.append([typ, code, label] + vals)
        have = [m for m, v in zip(months, vals) if v is not None]
        if have and have[-1] < last_m:
            stale.append((code, label, have[-1]))
    ws.freeze_panes = "D2"
    ws.column_dimensions["A"].width = 12
    ws.column_dimensions["B"].width = 18
    ws.column_dimensions["C"].width = 52
    for i in range(4, 4 + len(months)):
        ws.column_dimensions[get_column_letter(i)].width = 13
    about = wb.create_sheet("About")
    for r in [
        ["Germany CPI - food, beverages, alcohol and tobacco (Destatis, CPI 2020 = 100)"],
        ["Source: Statistisches Bundesamt (Destatis) Genesis-Online, tables 61111-0004 (2-5 digit) and 61111-0006 (10-digit items)."],
        ["Values are index levels only; month-on-month and year-on-year changes are not included."],
        ["2-5 digit codes run from 2015-01; 10-digit items from 2020-01."],
        [f"Latest month with data: {last_m}"],
    ]:
        about.append(r)
    about["A1"].font = Font(bold=True)
    about.column_dimensions["A"].width = 110
    wb.save(path)
    return last_m, missing, stale


def send(path: Path, month: str, missing, stale, n_rows: int):
    host = os.environ.get("SMTP_HOST", "").strip()
    if not host:
        print("SMTP_HOST is not set - file built, no e-mail sent.")
        return False
    port = int(os.environ.get("SMTP_PORT") or 587)
    user = os.environ.get("SMTP_USER", "")
    pwd = os.environ.get("SMTP_PASSWORD", "")
    sender = os.environ.get("MAIL_FROM") or user
    to = [a.strip() for a in (os.environ.get("MAIL_TO") or DEFAULT_TO).split(",") if a.strip()]
    if not sender or not to:
        raise SystemExit("MAIL_FROM / SMTP_USER and MAIL_TO must not be empty")
    lines = [
        f"Hello,",
        "",
        f"Destatis has published the German consumer price index for {month}. The attached Excel contains the",
        f"monthly index for the {n_rows} codes on the agreed list (food, beverages, alcohol, tobacco),",
        "one column per month, 2015-01 to the latest month (10-digit items from 2020-01).",
        "",
        "Source: Destatis Genesis-Online, tables 61111-0004 and 61111-0006 (CPI, 2020 = 100). Index levels only.",
    ]
    if stale:
        lines += ["", "No data after the month shown for these items (Destatis returns no values for them):"]
        lines += [f"  - {c}  {l}  (last month with data: {m})" for c, l, m in stale]
    if missing:
        lines += ["", "Not found in the Destatis download: " + ", ".join(missing)]
    lines += ["", "This message is sent automatically when a new month appears."]
    msg = EmailMessage()
    msg["Subject"] = f"Germany CPI data - {month}"
    msg["From"] = sender
    msg["To"] = ", ".join(to)
    msg.set_content("\n".join(lines))
    msg.add_attachment(path.read_bytes(), maintype="application",
                       subtype="vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                       filename=f"germany_cpi_{month}.xlsx")
    ctx = ssl.create_default_context()
    if port == 465:
        with smtplib.SMTP_SSL(host, port, context=ctx, timeout=60) as s:
            if user:
                s.login(user, pwd)
            s.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=60) as s:
            s.starttls(context=ctx)
            if user:
                s.login(user, pwd)
            s.send_message(msg)
    print(f"sent germany_cpi_{month}.xlsx to {', '.join(to)}")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--out", default=str(ROOT / "germany_cpi.xlsx"))
    a = ap.parse_args()
    months, series, rows = load()
    out = Path(a.out)
    month, missing, stale = build_xlsx(out, months, series, rows)
    print(f"built {out}: {len(rows)} codes, {months[0]}..{months[-1]}, latest data {month}; "
          f"missing {len(missing)}, ending early {len(stale)}")
    if a.dry_run:
        return
    state = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}
    last = state.get("last_sent_month")
    if not a.force and last and month <= last:
        print(f"{month} already sent (last sent {last}) - nothing to do.")
        return
    if send(out, month, missing, stale, len(rows)):
        STATE.write_text(json.dumps({"last_sent_month": month}) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
