"""
Scrape GUR list pages for vessel photos, downscale to 200px-wide JPEG thumbnails.
Output: vessel_thumbs/{imo}.jpg (gur_id used where IMO missing) + thumbs_manifest.csv
"""
import io, re, time, csv
import requests
import pandas as pd
from PIL import Image
from concurrent.futures import ThreadPoolExecutor

BASE = "https://war-sanctions.gur.gov.ua/en/transport/ships"
HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"}
session = requests.Session()
session.headers.update(HEADERS)

import os
os.makedirs('vessel_thumbs', exist_ok=True)

# 1. list pages -> (gur_id, img_url)
records, seen, page = [], set(), 1
while True:
    r = session.get(BASE, params={'page': page, 'per-page': 12}, timeout=30)
    # cards: img src precedes the detail link's content; pair by splitting on detail hrefs
    parts = re.split(r'href="(?:https://war-sanctions\.gur\.gov\.ua)?/en/transport/ships/(\d+)"', r.text)
    new = 0
    for i in range(1, len(parts) - 1, 2):
        gid, card = parts[i], parts[i + 1][:4000]
        if gid in seen:
            continue
        seen.add(gid); new += 1
        img = re.search(r'<img class="photo" src="([^"]+)"', card)
        records.append({'gur_id': gid, 'img_url': img.group(1) if img else ''})
    if new == 0:
        break
    if page % 30 == 0:
        print(f"list page {page}: {len(records)}", flush=True)
    page += 1
    time.sleep(0.3)
print(f"List done: {len(records)} vessels, {sum(1 for r in records if r['img_url'])} with photo URL", flush=True)

# 2. join IMO from master
master = pd.read_csv('gur_vessels_master.csv', dtype=str)
imo_by_gid = dict(zip(master['gur_id'], master['imo'].fillna('')))

# 3. download + downscale
def fetch(rec):
    gid, url = rec['gur_id'], rec['img_url']
    key = imo_by_gid.get(gid, '') or f"gid{gid}"
    out = f"vessel_thumbs/{key}.jpg"
    if not url:
        return {'gur_id': gid, 'imo': imo_by_gid.get(gid, ''), 'file': '', 'status': 'no_photo'}
    if os.path.exists(out):
        return {'gur_id': gid, 'imo': imo_by_gid.get(gid, ''), 'file': out, 'status': 'cached'}
    for _ in range(2):
        try:
            r = session.get(url, timeout=25)
            if r.status_code != 200:
                time.sleep(1.5); continue
            im = Image.open(io.BytesIO(r.content)).convert('RGB')
            w, h = im.size
            im = im.resize((200, max(1, int(h * 200 / w))), Image.LANCZOS)
            im.save(out, 'JPEG', quality=80, optimize=True)
            return {'gur_id': gid, 'imo': imo_by_gid.get(gid, ''), 'file': out, 'status': 'ok'}
        except Exception:
            time.sleep(1.5)
    return {'gur_id': gid, 'imo': imo_by_gid.get(gid, ''), 'file': '', 'status': 'failed'}

results = []
with ThreadPoolExecutor(max_workers=4) as ex:
    for n, res in enumerate(ex.map(fetch, records), 1):
        results.append(res)
        if n % 200 == 0:
            print(f"images {n}/{len(records)}", flush=True)

pd.DataFrame(results).to_csv('thumbs_manifest.csv', index=False)
from collections import Counter
print(Counter(r['status'] for r in results), flush=True)
