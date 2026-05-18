import requests
import re, csv, os, time

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Accept-Language": "en-GB,en;q=0.9",
}
DELAY_PAGE = 2.5      # between gallery page fetches
DELAY_PHOTO = 1.0     # between photo downloads (smaller — CDN, not search)
MAX_PAGES = 5         # cap at 5 pages = up to 60 photos per vessel
MAX_PHOTOS = 20       # cap downloads per vessel
SIZE = "middle"       # 'middle' (~300KB) or 'big' (~3MB)
OUT_ROOT = "vessel_images"

os.makedirs(OUT_ROOT, exist_ok=True)
PHOTO_RE = re.compile(r'https://www\.shipspotting\.com/photos/middle/\d+/\d+/\d+/\d+\.jpg')

with open("detected_vessels_baltic_feb_oct_2025.csv") as f:
    rows = list(csv.DictReader(f))

manifest = []
for i, row in enumerate(rows, 1):
    imo, name = row["imo"], row.get("name") or "unknown"
    safe_name = re.sub(r"[^A-Za-z0-9_-]", "_", name)[:40]
    vessel_dir = f"{OUT_ROOT}/IMO_{imo}_{safe_name}"
    os.makedirs(vessel_dir, exist_ok=True)

    existing = [f for f in os.listdir(vessel_dir) if f.endswith(".jpg")]
    if len(existing) >= 5:  # already have a reasonable set
        manifest.append({"imo": imo, "name": name, "dir": vessel_dir,
                         "n_photos": len(existing), "status": "cached"})
        print(f"[{i:3d}/{len(rows)}] IMO {imo}: cached ({len(existing)})", flush=True)
        continue

    # Collect photo URLs across pages
    all_photos = []
    seen = set()
    for page in range(1, MAX_PAGES + 1):
        try:
            url = f"https://www.shipspotting.com/photos/gallery?imo={imo}&page={page}"
            r = requests.get(url, headers=HEADERS, timeout=30)
            if r.status_code != 200: break
            found = PHOTO_RE.findall(r.text)
            new = [p for p in found if p not in seen]
            if not new and page > 1: break
            for p in new:
                seen.add(p); all_photos.append(p)
            time.sleep(DELAY_PAGE)
        except Exception as e:
            print(f"  page {page} error: {e}", flush=True)
            break

    all_photos = all_photos[:MAX_PHOTOS]
    if not all_photos:
        manifest.append({"imo": imo, "name": name, "dir": vessel_dir,
                         "n_photos": 0, "status": "no_photos"})
        print(f"[{i:3d}/{len(rows)}] IMO {imo} ({name}): no photos found", flush=True)
        continue

    # Optionally swap 'middle' for 'big' for full-res
    if SIZE == "big":
        all_photos = [p.replace("/middle/", "/big/") for p in all_photos]

    # Download
    n_ok = 0
    for j, photo_url in enumerate(all_photos, 1):
        out_jpg = f"{vessel_dir}/photo_{j:02d}.jpg"
        if os.path.exists(out_jpg):
            n_ok += 1; continue
        try:
            pr = requests.get(photo_url, headers=HEADERS, timeout=30)
            if pr.status_code == 200 and len(pr.content) > 10000:
                with open(out_jpg, "wb") as f: f.write(pr.content)
                n_ok += 1
            time.sleep(DELAY_PHOTO)
        except Exception as e:
            print(f"  photo {j} err: {e}", flush=True)

    manifest.append({"imo": imo, "name": name, "dir": vessel_dir,
                     "n_photos": n_ok, "status": "ok" if n_ok else "all_failed"})
    print(f"[{i:3d}/{len(rows)}] IMO {imo} ({name}): {n_ok} photos", flush=True)

with open(f"{OUT_ROOT}/multi_manifest.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["imo", "name", "dir", "n_photos", "status"])
    w.writeheader(); w.writerows(manifest)

total = sum(m["n_photos"] for m in manifest)
covered = sum(1 for m in manifest if m["n_photos"] > 0)
print(f"\nDone: {total} photos across {covered}/{len(rows)} vessels")
