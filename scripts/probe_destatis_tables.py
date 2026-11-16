"""One-off probe v2: how to pull ALL codes (incl. 10-digit) monthly from Destatis table 61111-0006.
Never prints the token."""
import csv, io, os, sys, urllib.parse, urllib.request, urllib.error, zipfile, json, collections

TOKEN = os.environ.get("GENESIS_TOKEN", "").strip()
BASE = "https://genesis.destatis.de/genesisWS/rest/2020/"
if not TOKEN:
    sys.exit("no GENESIS_TOKEN")
T = "61111-0006"

def post(path, **kw):
    req = urllib.request.Request(BASE + path, data=urllib.parse.urlencode(kw).encode(), method="POST",
                                 headers={"username": TOKEN, "password": "", "Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return r.read()

print("== metadata of", T)
try:
    m = json.loads(post("metadata/table", name=T, area="all", language="en"))
    obj = m.get("Object", {})
    st = obj.get("Structure", {})
    for part in ("Head", "Columns", "Rows"):
        v = st.get(part)
        if v: print(part, ":", json.dumps(v)[:600])
    for k in ("Columns", "Rows"):
        for item in (st.get(k) or []):
            print(" ", k, item.get("Code"), "|", item.get("Content"), "|", item.get("Type"), "| members:", item.get("Values"))
    print("Content:", obj.get("Content"))
except Exception as e:  # noqa: BLE001
    print("metadata failed:", type(e).__name__, str(e)[:300])

def summarize(label, data):
    if data.startswith(b"PK"):
        data = zipfile.ZipFile(io.BytesIO(data)).read(zipfile.ZipFile(io.BytesIO(data)).namelist()[0])
    text = data.decode("utf-8-sig", "replace")
    if "statistics_code" not in text[:300]:
        print(f"  [{label}] not csv:", text[:240].replace("\n", " ")); return None
    rows = list(csv.DictReader(text.splitlines(), delimiter=";"))
    codes = {}
    vars_ = set()
    for r in rows:
        for i in (1, 2, 3, 4):
            c = r.get(f"{i}_variable_attribute_code") or ""
            if r.get(f"{i}_variable_label"): vars_.add((r.get(f"{i}_variable_code"), r.get(f"{i}_variable_label")))
            if c.startswith("CC13"):
                codes[c] = r.get(f"{i}_variable_attribute_label")
    lens = collections.Counter(len(c) - 5 for c in codes)
    print(f"  [{label}] rows={len(rows)} codes={len(codes)} digits={dict(sorted(lens.items()))} vars={sorted(vars_)}")
    print("     has CC13-0213100100:", "CC13-0213100100" in codes, "| has CC13-0111101100:", "CC13-0111101100" in codes)
    return rows

print("\n== attempts")
for label, kw in [("default", {}),
                  ("cc=*", {"classifyingvariable1": "CC13A2", "classifyingkey1": "*"}),
                  ("A10", {"classifyingvariable1": "CC13A10"}),
                  ("A5", {"classifyingvariable1": "CC13A5"}),
                  ("A5 *", {"classifyingvariable1": "CC13A5", "classifyingkey1": "*"}),
                  ("A10 *", {"classifyingvariable1": "CC13A10", "classifyingkey1": "*"})]:
    try:
        data = post("data/tablefile", name=T, area="all", format="ffcsv", language="en", compress="false", job="false", startyear="2026", **kw)
    except Exception as e:  # noqa: BLE001
        print(f"  [{label}] failed: {type(e).__name__} {str(e)[:120]}"); continue
    summarize(label, data)
