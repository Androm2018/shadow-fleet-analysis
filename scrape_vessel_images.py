import requests
from bs4 import BeautifulSoup
import csv, os, time, re
from urllib.parse import urljoin

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Accept-Language": "en-GB,en;q=0.9",
}
BASE = "https://www.shipspotting.com"
DELAY = 3.0
OUT_DIR = "vessel_images"
os.makedirs(OUT_DIR, exist_ok=True)

with open("detected_vessels_baltic_feb_oct_2025.csv") as f:
    rows = list(csv.DictReader(f))

manifest = []
for i, row in enumerate(rows, 1):
    imo, name = row["imo"], row.get("name") or "unknown"
    safe_name = re.sub(r"[^A-Za-z0-9_-]", "_", name)[:40]
    out_jpg = f"{OUT_DIR}/IMO_{imo}_{safe_name}.jpg"
    if os.path.exists(out_jpg):
        manifest.append({"imo": imo, "name": name, "file": out_jpg, "status": "cached"})
        continue

    try:
        gallery_url = f"{BASE}/photos/gallery?imo={imo}"
        r = requests.get(gallery_url, headers=HEADERS, timeout=30)
        if r.status_code != 200:
            manifest.append({"imo": imo, "name": name, "file": "", "status": f"http_{r.status_code}"})
            time.sleep(DELAY); continue

        soup = BeautifulSoup(r.text, "html.parser")
        first = soup.select_one("a[href*='/photos/'][href*='/'] img, .gallery-item a")
        if not first:
            manifest.append({"imo": imo, "name": name, "file": "", "status": "no_photo"})
            time.sleep(DELAY); continue

        img_el = first if first.name == "img" else first.select_one("img")
        if img_el and img_el.get("src"):
            img_url = urljoin(BASE, img_el["src"])
            img_url = img_url.replace("/thumb/", "/full/").replace("_tb.", ".")
            img_r = requests.get(img_url, headers=HEADERS, timeout=30)
            if img_r.status_code == 200 and len(img_r.content) > 5000:
                with open(out_jpg, "wb") as f:
                    f.write(img_r.content)
                manifest.append({"imo": imo, "name": name, "file": out_jpg, "status": "ok"})
                print(f"[{i:3d}/210] IMO {imo} ({name}) -> {out_jpg}", flush=True)
            else:
                manifest.append({"imo": imo, "name": name, "file": "", "status": "img_fetch_failed"})
        else:
            manifest.append({"imo": imo, "name": name, "file": "", "status": "no_img_src"})
    except Exception as e:
        manifest.append({"imo": imo, "name": name, "file": "", "status": f"err_{type(e).__name__}"})
        print(f"[{i:3d}/210] IMO {imo}: {e}", flush=True)

    time.sleep(DELAY)

with open(f"{OUT_DIR}/manifest.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["imo", "name", "file", "status"])
    w.writeheader(); w.writerows(manifest)

ok = sum(1 for m in manifest if m["status"] in ("ok", "cached"))
print(f"\nDone: {ok}/{len(rows)} vessels with images")
