"""One-off probe: which Destatis CPI tables carry the 10-digit CC13 codes monthly?
Prints table codes/names from the Genesis catalogue and, for each CPI table, the code lengths found.
Never prints the token."""
import csv, io, os, sys, urllib.parse, urllib.request, urllib.error, zipfile, json, collections

TOKEN = os.environ.get("GENESIS_TOKEN", "").strip()
BASE = "https://genesis.destatis.de/genesisWS/rest/2020/"
if not TOKEN:
    sys.exit("no GENESIS_TOKEN")

def post(path, **kw):
    req = urllib.request.Request(BASE + path, data=urllib.parse.urlencode(kw).encode(), method="POST",
                                 headers={"username": TOKEN, "password": "", "Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=180) as r:
        return r.read()

print("== catalogue: tables matching 61111*")
try:
    raw = post("catalogue/tables", selection="61111*", area="all", searchcriterion="code", pagelength="100", language="en")
    j = json.loads(raw)
    for t in j.get("List", []):
        print(t.get("Code"), "|", t.get("Content"), "|", t.get("Time", ""))
except Exception as e:  # noqa: BLE001
    print("catalogue failed:", type(e).__name__, str(e)[:200])

for code in ["61111-0002", "61111-0004", "61111-0006", "61111-0007", "61111-0010", "61111-0011", "61111-0012", "61111-0013"]:
    print("\n== table", code)
    try:
        data = post("data/tablefile", name=code, area="all", format="ffcsv", language="en", compress="false", job="false", startyear="2025")
    except urllib.error.HTTPError as e:
        print("  HTTP", e.code); continue
    except Exception as e:  # noqa: BLE001
        print("  failed:", type(e).__name__, str(e)[:150]); continue
    if data.startswith(b"PK"):
        z = zipfile.ZipFile(io.BytesIO(data)); data = z.read(z.namelist()[0])
    text = data.decode("utf-8-sig", "replace")
    if "statistics_code" not in text[:300]:
        print("  not a flat csv:", text[:200].replace("\n", " ")); continue
    rows = list(csv.DictReader(text.splitlines(), delimiter=";"))
    print("  rows:", len(rows), "| first row label:", rows[0].get("statistics_label"))
    cols = [k for k in rows[0] if k.endswith("variable_code") or k.endswith("variable_label")]
    print("  variables:", {rows[0][k] for k in cols if k.endswith('variable_label')})
    codes = {}
    for r in rows:
        for i in (1, 2, 3):
            c = (r.get(f"{i}_variable_attribute_code") or "")
            if c.startswith("CC13"):
                codes[c] = r.get(f"{i}_variable_attribute_label")
    lens = collections.Counter(len(c) - 5 for c in codes)
    print("  CC13 codes:", len(codes), "| digits distribution:", dict(sorted(lens.items())))
    ten = [c for c in codes if len(c) == 15]
    print("  10-digit sample:", [(c, codes[c]) for c in ten[:5]], "| has CC13-0213100100:", "CC13-0213100100" in codes)
    months = sorted({(r.get("time"), r.get("1_variable_attribute_code")) for r in rows})
    print("  periods seen (first/last):", months[:1], months[-1:])
