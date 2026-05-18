import requests
import re, csv, os, time, json

HEADERS = {"User-Agent": "shadow-fleet-research/1.0 (academic; contact via github.com/Androm2018)"}
API = "https://commons.wikimedia.org/w/api.php"
DELAY = 0.5  # Commons API is generous; be polite anyway
OUT_ROOT = "vessel_images"
SHIP_TERMS = re.compile(
    r'\b(ship|tanker|vessel|boat|cargo|carrier|IMO|MMSI|barge|bulker|'
    r'freighter|crude\s*oil|LNG|LPG|chemical|oil\s*products|product\s*tanker)\b',
    re.IGNORECASE
)

# Load full vessel list and existing manifest to find gaps
with open("detected_vessels_baltic_feb_oct_2025.csv") as f:
    all_vessels = list(csv.DictReader(f))

covered_imos = set()
manifest_path = f"{OUT_ROOT}/multi_manifest.csv"
if os.path.exists(manifest_path):
    with open(manifest_path) as f:
        for r in csv.DictReader(f):
            if r["status"] in ("ok", "cached") and int(r["n_photos"]) > 0:
                covered_imos.add(r["imo"])

gaps = [v for v in all_vessels if v["imo"] not in covered_imos]
print(f"Backfilling {len(gaps)} vessels from Wikimedia Commons...\n", flush=True)

results = []
for i, vessel in enumerate(gaps, 1):
    imo, name = vessel["imo"], vessel.get("name") or ""
    safe_name = re.sub(r"[^A-Za-z0-9_-]", "_", name or "unknown")[:40]
    vessel_dir = f"{OUT_ROOT}/IMO_{imo}_{safe_name}"
    os.makedirs(vessel_dir, exist_ok=True)

    # Search by IMO (and name if available, for better recall)
    query = f"IMO {imo}" + (f" {name}" if name else "")
    try:
        r = requests.get(API, headers=HEADERS, timeout=30, params={
            "action": "query", "format": "json", "list": "search",
            "srsearch": query, "srnamespace": "6", "srlimit": 20,
        })
        hits = r.json().get("query", {}).get("search", [])
    except Exception as e:
        results.append({"imo": imo, "name": name, "n_photos": 0, "status": f"search_err_{type(e).__name__}"})
        print(f"[{i:3d}/{len(gaps)}] IMO {imo}: search failed: {e}", flush=True)
        time.sleep(DELAY); continue

    # Filter: title must contain ship-related term OR exact IMO digits
    matches = [h["title"] for h in hits
               if SHIP_TERMS.search(h["title"]) or imo in h["title"]]
    # Cap to 5 per vessel
    matches = matches[:5]

    if not matches:
        results.append({"imo": imo, "name": name, "n_photos": 0, "status": "no_commons_match"})
        print(f"[{i:3d}/{len(gaps)}] IMO {imo} ({name}): no Commons match", flush=True)
        time.sleep(DELAY); continue

    # Resolve each filename to a real image URL
    n_ok = 0
    for j, title in enumerate(matches, 1):
        try:
            r = requests.get(API, headers=HEADERS, timeout=30, params={
                "action": "query", "format": "json", "titles": title,
                "prop": "imageinfo", "iiprop": "url|size|extmetadata",
            })
            pages = r.json()["query"]["pages"]
            ii = next(iter(pages.values())).get("imageinfo", [{}])[0]
            img_url = ii.get("url", "").split("?")[0]  # strip tracking params
            if not img_url: continue

            # Download
            existing = [f for f in os.listdir(vessel_dir) if f.startswith("commons_")]
            out_jpg = f"{vessel_dir}/commons_{len(existing)+1:02d}.jpg"
            if os.path.exists(out_jpg): continue

            ir = requests.get(img_url, headers=HEADERS, timeout=60)
            if ir.status_code == 200 and len(ir.content) > 10000:
                with open(out_jpg, "wb") as f: f.write(ir.content)
                n_ok += 1

                # Save licence/attribution alongside
                em = ii.get("extmetadata", {})
                meta = {
                    "source_title": title,
                    "url": img_url,
                    "licence": em.get("LicenseShortName", {}).get("value", "unknown"),
                    "artist": em.get("Artist", {}).get("value", "unknown"),
                    "date": em.get("DateTimeOriginal", {}).get("value", ""),
                }
                with open(out_jpg.replace(".jpg", ".json"), "w") as f:
                    json.dump(meta, f, indent=2)

            time.sleep(DELAY)
        except Exception as e:
            print(f"  photo {j} err: {e}", flush=True)

    results.append({"imo": imo, "name": name, "n_photos": n_ok,
                    "status": "ok" if n_ok else "all_failed"})
    print(f"[{i:3d}/{len(gaps)}] IMO {imo} ({name}): {n_ok} from Commons", flush=True)
    time.sleep(DELAY)

# Write separate manifest for the Commons backfill
with open(f"{OUT_ROOT}/commons_manifest.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["imo", "name", "n_photos", "status"])
    w.writeheader(); w.writerows(results)

total = sum(r["n_photos"] for r in results)
covered = sum(1 for r in results if r["n_photos"] > 0)
print(f"\nDone: {total} Commons photos across {covered}/{len(gaps)} previously-missing vessels")
print(f"All images come with .json sidecar files containing licence + attribution.")
