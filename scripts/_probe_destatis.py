"""ONE-OFF probe (delete after use): which 10-digit CPI items exist in 2024 vs 2025/2026 in Destatis 61111-0006?"""
import csv, os, re, sys
sys.path.insert(0, os.path.dirname(__file__))
import fetch_destatis_full as f

tok = os.environ["GENESIS_TOKEN"].strip()
yrs = {}
for y in (2024, 2025, 2026):
    text = f.pull(tok, "61111-0006", "CC13Z1", y, y).decode("utf-8-sig", "replace")
    print(y, "csv" if "statistics_code" in text[:300] else "NOT CSV: " + text[:200])
    codes = {}
    for r in csv.DictReader(text.splitlines(), delimiter=";"):
        for i in (1, 2, 3, 4):
            c = r.get(f"{i}_variable_attribute_code") or ""
            if c.startswith("CC13-0") and len(c) == 15 and (r.get("value") or "").strip() not in ("", "...", "-", "."):
                codes[c] = (r.get(f"{i}_variable_attribute_label") or "").strip()
    yrs[y] = codes
    print(y, "10-digit codes with values:", len(codes))
lost = sorted(set(yrs[2024]) - set(yrs[2025]))
new = sorted(set(yrs[2025]) - set(yrs[2024]))
print("\nIN 2024 BUT NOT 2025 (%d):" % len(lost))
for c in lost: print(" ", c, yrs[2024][c])
print("\nIN 2025 BUT NOT 2024 (%d):" % len(new))
for c in new: print(" ", c, yrs[2025][c])
print("\n2026 codes:", len(yrs[2026]))
for c in ["CC13-0112710300","CC13-0112721100","CC13-0113100200","CC13-0117149200","CC13-0121121100","CC13-0122320300"]:
    print(c, {y: (c in yrs[y]) for y in yrs})
