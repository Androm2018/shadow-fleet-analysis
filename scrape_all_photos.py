import requests
import re, csv, os, time

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Accept-Language": "en-GB,en;q=0.9",
}
DELAY_PAGE = 2.5
DELAY_PHOTO = 1.0
MAX_PAGES = 10        # was 5
MAX_PHOTOS = 50       # was 20 — captures the natural ceiling we observed (~48)
OUT_ROOT = "vessel_images"

os.makedirs(OUT_ROOT, exist_ok=True)
PHOTO_RE = re.compile(r'https://www\.shipspotting\.com/photos/middle/\d+/\d+/\d+/\d+\.jpg')
PHOTO_ID_RE = re.compile(r'/middle/\d+/\d+/\d+/(\d+)\.jpg')

with open("detected_vessels_baltic_feb_oct_2025.csv") as f:
    rows = list(csv.DictReader(f))

manifest = []
total_new_downloads = 0

for i, row in enumerate(rows, 1):
    imo, name = row["imo"], row.get("name") or "unknown"
    safe_name = re.sub(r"[^A-Za-z0-9_-]", "_", name)[:40]
    vessel_dir = f"{OUT_ROOT}/IMO_{imo}_{safe_name}"
    os.makedirs(vessel_dir, exist_ok=True)

    # Track which photo IDs we already have (not just count!)
    existing_files = [f for f in os.listdir(vessel_dir)
                     if f.endswith(".jpg") and f.startswith("photo_")]
    existing_ids = set()
    for fname in existing_files:
        # Photo files have stable URLs — if we had IDs, we'd dedupe by them
        pass  # we'll dedupe by URL set below

    # Collect ALL photo URLs across pages (no early cache exit)
    all_photo_urls = []
    seen = set()
    for page in range(1, MAX_PAGES + 1):
        try:
            url = f"https://www.shipspotting.com/photos/gallery?imo={imo}&page={page}"
            r = requests.get(url, headers=HEADERS, timeout=30)
            if r.status_code != 200:
                print(f"  page {page} HTTP {r.status_code}", flush=True)
                break
            found = PHOTO_RE.findall(r.text)
            new = [p for p in found if p not in seen]
            if not new and page > 1: break
            for p in new:
                seen.add(p); all_photo_urls.append(p)
            time.sleep(DELAY_PAGE)
        except Exception as e:
            print(f"  page {page} err: {e}", flush=True)
            break

    all_photo_urls = all_photo_urls[:MAX_PHOTOS]
    if not all_photo_urls:
        manifest.append({"imo": imo, "name": name, "dir": vessel_dir,
                         "n_photos": len(existing_files),
                         "n_new": 0, "status": "no_photos_found"})
        print(f"[{i:3d}/{len(rows)}] IMO {imo}: no photos found "
              f"(existing: {len(existing_files)})", flush=True)
        continue

    # Map photo URLs to deterministic filenames by photo ID
    # so re-runs don't re-download what's already there
    n_existing = len(existing_files)
    n_new = 0
    for photo_url in all_photo_urls:
        photo_id_match = PHOTO_ID_RE.search(photo_url)
        if not photo_id_match: continue
        photo_id = photo_id_match.group(1)
        out_jpg = f"{vessel_dir}/ss_{photo_id}.jpg"
        if os.path.exists(out_jpg): continue

        try:
            pr = requests.get(photo_url, headers=HEADERS, timeout=30)
            if pr.status_code == 200 and len(pr.content) > 10000:
                with open(out_jpg, "wb") as f: f.write(pr.content)
                n_new += 1
                total_new_downloads += 1
            time.sleep(DELAY_PHOTO)
        except Exception as e:
            print(f"  photo {photo_id} err: {e}", flush=True)

    final_count = len([f for f in os.listdir(vessel_dir) if f.endswith(".jpg")])
    manifest.append({"imo": imo, "name": name, "dir": vessel_dir,
                     "n_photos": final_count, "n_new": n_new,
                     "status": "ok" if final_count > 0 else "no_photos"})
    print(f"[{i:3d}/{len(rows)}] IMO {imo} ({name}): {final_count} total "
          f"(+{n_new} new)", flush=True)

with open(f"{OUT_ROOT}/multi_manifest.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["imo", "name", "dir", "n_photos", "n_new", "status"])
    w.writeheader(); w.writerows(manifest)

total = sum(m["n_photos"] for m in manifest)
covered = sum(1 for m in manifest if m["n_photos"] > 0)
print(f"\nDone: {total} photos across {covered}/{len(rows)} vessels")
print(f"New this run: {total_new_downloads}")
