import yt_dlp
import csv, os, json, time, re
import requests

# Use yt-dlp Python API for search (no API key needed); requests for thumbnail download
OUT_ROOT = "vessel_images"
RESULTS_PER_VESSEL = 5
DELAY = 1.5  # between searches — yt-dlp will rate-limit itself but be polite

os.makedirs(OUT_ROOT, exist_ok=True)

with open("detected_vessels_baltic_feb_oct_2025.csv") as f:
    rows = list(csv.DictReader(f))

ydl_opts = {
    'skip_download': True,
    'quiet': True,
    'no_warnings': True,
    'extract_flat': True,
    'ignoreerrors': True,
}

manifest = []
total_videos = 0

for i, row in enumerate(rows, 1):
    imo, name = row["imo"], (row.get("name") or "").strip()
    if not name:  # skip nameless — search would be too noisy
        manifest.append({"imo": imo, "name": "", "n_videos": 0,
                         "status": "no_name_skipped"})
        continue

    safe_name = re.sub(r"[^A-Za-z0-9_-]", "_", name)[:40]
    vessel_dir = f"{OUT_ROOT}/IMO_{imo}_{safe_name}"
    os.makedirs(vessel_dir, exist_ok=True)
    yt_dir = f"{vessel_dir}/youtube"
    os.makedirs(yt_dir, exist_ok=True)

    # Query: vessel name + IMO + "ship" to disambiguate from unrelated content
    query = f'"{name}" IMO {imo} ship'
    search_url = f"ytsearch{RESULTS_PER_VESSEL}:{query}"

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(search_url, download=False)
        entries = (info or {}).get('entries', []) or []
    except Exception as e:
        manifest.append({"imo": imo, "name": name, "n_videos": 0,
                         "status": f"search_err_{type(e).__name__}"})
        print(f"[{i:3d}/{len(rows)}] IMO {imo} ({name}): search failed", flush=True)
        time.sleep(DELAY); continue

    if not entries:
        manifest.append({"imo": imo, "name": name, "n_videos": 0,
                         "status": "no_results"})
        print(f"[{i:3d}/{len(rows)}] IMO {imo} ({name}): no results", flush=True)
        time.sleep(DELAY); continue

    # Save video metadata + download thumbnails
    vessel_videos = []
    for j, e in enumerate(entries, 1):
        if not e: continue
        video_id = e.get('id')
        if not video_id: continue

        meta = {
            "video_id": video_id,
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "title": e.get('title', ''),
            "channel": e.get('channel') or e.get('uploader') or '',
            "duration_seconds": e.get('duration'),
            "view_count": e.get('view_count'),
            "thumbnail_url": e.get('thumbnails', [{}])[-1].get('url') if e.get('thumbnails') else None,
        }

        # Save thumbnail (small, fast, gives us visual reference)
        thumb_url = meta["thumbnail_url"] or f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
        thumb_path = f"{yt_dir}/yt_{j:02d}_{video_id}.jpg"
        if not os.path.exists(thumb_path):
            try:
                tr = requests.get(thumb_url, timeout=15,
                                  headers={"User-Agent": "Mozilla/5.0"})
                if tr.status_code == 200 and len(tr.content) > 2000:
                    with open(thumb_path, "wb") as f: f.write(tr.content)
                    meta["thumbnail_file"] = thumb_path
            except Exception as ex:
                meta["thumbnail_error"] = str(ex)

        vessel_videos.append(meta)
        total_videos += 1

    # Save per-vessel metadata JSON
    with open(f"{yt_dir}/videos.json", "w") as f:
        json.dump(vessel_videos, f, indent=2)

    manifest.append({"imo": imo, "name": name, "n_videos": len(vessel_videos),
                     "status": "ok"})
    print(f"[{i:3d}/{len(rows)}] IMO {imo} ({name}): {len(vessel_videos)} videos",
          flush=True)
    time.sleep(DELAY)

with open(f"{OUT_ROOT}/youtube_manifest.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["imo", "name", "n_videos", "status"])
    w.writeheader(); w.writerows(manifest)

covered = sum(1 for m in manifest if m["n_videos"] > 0)
print(f"\nDone: {total_videos} videos catalogued across {covered}/{len(rows)} vessels")
print(f"Metadata in vessel_images/IMO_*/youtube/videos.json")
print(f"Thumbnails in vessel_images/IMO_*/youtube/yt_*.jpg")
