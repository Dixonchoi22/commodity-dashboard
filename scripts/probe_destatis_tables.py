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

print("== catalogue: variables CC13*", flush=True)
vars10 = []
try:
    j = json.loads(post("catalogue/variables", selection="CC13*", area="all", searchcriterion="code", pagelength="100", language="en"))
    for v in j.get("List", []):
        print(" ", v.get("Code"), "|", v.get("Content"), "|", v.get("Type"), "| values:", v.get("Values"), flush=True)
        if "10" in (v.get("Content") or "") or "10" in (v.get("Code") or ""):
            vars10.append(v.get("Code"))
except Exception as e:  # noqa: BLE001
    print("variables failed:", type(e).__name__, str(e)[:300], flush=True)

def summarize(label, data):
    if data.startswith(b"PK"):
        z = zipfile.ZipFile(io.BytesIO(data)); data = z.read(z.namelist()[0])
    text = data.decode("utf-8-sig", "replace")
    if "statistics_code" not in text[:300]:
        print(f"  [{label}] not csv:", text[:240].replace("\n", " "), flush=True); return None
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
    print(f"  [{label}] rows={len(rows)} codes={len(codes)} digits={dict(sorted(lens.items()))} vars={sorted(vars_)}", flush=True)
    print("     has CC13-0213100100:", "CC13-0213100100" in codes, "| has CC13-0111101100:", "CC13-0111101100" in codes, flush=True)
    return rows

print("\n== attempts with the 10-digit variable(s):", vars10, flush=True)
for v in ["CC13Z1", "CC13B1"]:
    try:
        data = post("data/tablefile", name=T, area="all", format="ffcsv", language="en", compress="false", job="false", startyear="2026", classifyingvariable1=v)
    except Exception as e:  # noqa: BLE001
        print(f"  [{v}] failed: {type(e).__name__} {str(e)[:120]}", flush=True); continue
    summarize(v, data)
