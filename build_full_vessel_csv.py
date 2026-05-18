import requests
import csv
import re
import time

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Accept-Language": "en-GB,en;q=0.9",
}
DELAY = 2.0

# ---------------------------------------------------------------------
# 1. Pull current GUR shadow-fleet listing (~117 pages × 12 vessels/page)
# ---------------------------------------------------------------------
print("Pulling current GUR shadow-fleet list...", flush=True)
gur_data = {}  # gur_id -> {imo, name, gur_id}

for page in range(1, 200):  # generous upper bound
    url = f"https://war-sanctions.gur.gov.ua/en/transport/shadow-fleet?page={page}"
    r = requests.get(url, headers=HEADERS, timeout=30)
    if r.status_code != 200:
        print(f"  page {page}: HTTP {r.status_code}, stopping"); break

    # Each card = detail link + nearby content. Use sliding window
    # to associate each /shadow-fleet/{id} link with its surrounding IMO and name.
    detail_ids = re.findall(r'/en/transport/shadow-fleet/(\d+)', r.text)
    unique_ids = list(dict.fromkeys(detail_ids))  # preserve order, dedupe

    # Get sections between consecutive detail-link markers as card chunks
    parts = re.split(r'/en/transport/shadow-fleet/\d+', r.text)
    # parts[i+1] is the content after the i-th detail link
    new_count = 0
    for i, gid in enumerate(unique_ids):
        if gid in gur_data: continue
        # Look at ~2KB window after this link for IMO and name
        chunk = parts[i+1][:2000] if i+1 < len(parts) else ""
        imo_m = re.search(r'\b(9\d{6})\b', chunk)
        # Vessel name usually appears in an h2/h3 or a title-styled span
        name_m = re.search(r'(?:title|alt)="([^"]{2,60})"', chunk) or \
                 re.search(r'>\s*([A-Z][A-Z0-9\s\-\.]{2,40})\s*<', chunk)
        if imo_m:
            gur_data[gid] = {
                "gur_id": gid,
                "imo": imo_m.group(1),
                "name": (name_m.group(1).strip() if name_m else "").upper(),
            }
            new_count += 1

    print(f"  page {page}: {new_count} new vessels, cumulative {len(gur_data)}", flush=True)
    if new_count == 0 and page > 2: break
    time.sleep(DELAY)

print(f"\nGUR total: {len(gur_data)} vessels", flush=True)

# ---------------------------------------------------------------------
# 2. Pull FleetLeaks sanctioned-vessel IMO list
# ---------------------------------------------------------------------
print("\nPulling FleetLeaks sanctioned-vessel list...", flush=True)
sanctioned_imos = set()
imo_link_re = re.compile(r'/vessels/imo-(\d{7})/')

for page in range(1, 100):
    url = "https://fleetleaks.com/vessels/" if page == 1 else f"https://fleetleaks.com/vessels/page/{page}/"
    try:
        r = requests.get(url, headers={"User-Agent": HEADERS["User-Agent"]}, timeout=30)
        if r.status_code != 200: break
        imos = set(imo_link_re.findall(r.text))
        new = imos - sanctioned_imos
        if not new and page > 1: break
        sanctioned_imos |= imos
        print(f"  page {page}: {len(imos)} found, cumulative {len(sanctioned_imos)}", flush=True)
        time.sleep(1.5)
    except Exception as e:
        print(f"  page {page} err: {e}"); break

print(f"\nFleetLeaks sanctioned total: {len(sanctioned_imos)}", flush=True)

# ---------------------------------------------------------------------
# 3. Load detected vessels (your 210)
# ---------------------------------------------------------------------
detected_imos = set()
with open("detected_vessels_baltic_feb_oct_2025.csv") as f:
    for row in csv.DictReader(f):
        detected_imos.add(row["imo"].strip())
print(f"\nDetected in Baltic Feb-Oct 2025: {len(detected_imos)} vessels", flush=True)

# Build IMO -> detected-name lookup so we can prefer the cleaner detected list name
detected_names = {}
with open("detected_vessels_baltic_feb_oct_2025.csv") as f:
    for row in csv.DictReader(f):
        if row.get("name"):
            detected_names[row["imo"].strip()] = row["name"].strip()

# ---------------------------------------------------------------------
# 4. Join and write the master CSV
# ---------------------------------------------------------------------
print("\nBuilding master CSV...", flush=True)
rows = []
for gid, v in gur_data.items():
    imo = v["imo"]
    name = detected_names.get(imo) or v["name"] or ""
    rows.append({
        "gur_id": gid,
        "imo": imo,
        "name": name,
        "sanctioned": "yes" if imo in sanctioned_imos else "no",
        "detected_in_baltic": "yes" if imo in detected_imos else "no",
    })

# Sort: detected first, then sanctioned-only, then rest; within group, by name
rows.sort(key=lambda r: (
    0 if r["detected_in_baltic"] == "yes" else (1 if r["sanctioned"] == "yes" else 2),
    r["name"] or "zzz",
    r["imo"]
))

out_path = "gur_vessels_master.csv"
with open(out_path, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["gur_id", "imo", "name",
                                       "sanctioned", "detected_in_baltic"])
    w.writeheader()
    w.writerows(rows)

# ---------------------------------------------------------------------
# 5. Summary
# ---------------------------------------------------------------------
n = len(rows)
n_san = sum(1 for r in rows if r["sanctioned"] == "yes")
n_det = sum(1 for r in rows if r["detected_in_baltic"] == "yes")
n_both = sum(1 for r in rows if r["sanctioned"] == "yes" and r["detected_in_baltic"] == "yes")
n_det_unsanctioned = sum(1 for r in rows if r["detected_in_baltic"] == "yes" and r["sanctioned"] == "no")
detected_not_in_gur = detected_imos - {r["imo"] for r in rows}

print(f"\nWrote {out_path}")
print(f"\n=== Summary ===")
print(f"  Total GUR vessels (current):              {n}")
print(f"  Of which formally sanctioned (FleetLeaks): {n_san} ({100*n_san/n:.1f}%)")
print(f"  Of which detected Feb-Oct '25:             {n_det} ({100*n_det/n:.1f}%)")
print(f"  Detected AND sanctioned:                   {n_both}")
print(f"  Detected BUT not sanctioned:               {n_det_unsanctioned}")
if detected_not_in_gur:
    print(f"  Detected vessels NOT in current GUR list:  {len(detected_not_in_gur)}")
    print(f"    (These were in your Vessels1.db snapshot but have since been de-listed)")
    print(f"    Sample IMOs: {sorted(detected_not_in_gur)[:5]}")
