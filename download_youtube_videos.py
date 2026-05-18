import yt_dlp, csv, os, json, time

OUT_ROOT = "vessel_images"
MAX_DURATION_SECONDS = 1800   # skip anything over 30 min — likely a livestream/compilation
MAX_FILESIZE_MB = 200         # per-video cap so storage doesn't explode
DELAY = 4.0                   # between downloads — YouTube watches for bursts
SUMMARY_PATH = f"{OUT_ROOT}/download_log.csv"

# Find all vessels with YouTube hits
targets = []
for d in sorted(os.listdir(OUT_ROOT)):
    json_path = f"{OUT_ROOT}/{d}/youtube/videos.json"
    if not os.path.exists(json_path): continue
    try:
        with open(json_path) as f: videos = json.load(f)
    except Exception: continue
    for v in videos:
        targets.append({
            "vessel_dir": f"{OUT_ROOT}/{d}/youtube",
            "vessel_id": d,
            "video_id": v.get("video_id"),
            "url": v.get("url"),
            "title": v.get("title", ""),
            "duration": v.get("duration_seconds") or 0,
        })

print(f"Found {len(targets)} videos to attempt across "
      f"{len(set(t['vessel_id'] for t in targets))} vessels", flush=True)

# Filter out long ones (likely livestreams, compilations, false positives)
keep, skipped = [], []
for t in targets:
    if t["duration"] and t["duration"] > MAX_DURATION_SECONDS:
        skipped.append({**t, "reason": f"duration_{t['duration']}s"})
    else:
        keep.append(t)
print(f"Keeping {len(keep)} (skipping {len(skipped)} over {MAX_DURATION_SECONDS}s)",
      flush=True)

# Common yt-dlp options
def make_opts(out_template):
    return {
        'format': 'best[ext=mp4][filesize<200M]/best[filesize<200M]/best',
        'outtmpl': out_template,
        'merge_output_format': 'mp4',
        'quiet': True,
        'no_warnings': True,
        'ignoreerrors': True,
        'noplaylist': True,
        'max_filesize': MAX_FILESIZE_MB * 1024 * 1024,
        # Optional: 'cookiefile': 'youtube_cookies.txt',  # uncomment if you export cookies
        # JS runtime is auto-detected if deno is on PATH
    }

results = []
for i, t in enumerate(keep, 1):
    out_path = f"{t['vessel_dir']}/video_{t['video_id']}.%(ext)s"
    final_glob = f"{t['vessel_dir']}/video_{t['video_id']}.mp4"

    if os.path.exists(final_glob):
        results.append({**t, "status": "cached", "size_mb": round(os.path.getsize(final_glob)/1e6, 1)})
        print(f"[{i:3d}/{len(keep)}] cached: {t['video_id']}", flush=True)
        continue

    try:
        with yt_dlp.YoutubeDL(make_opts(out_path)) as ydl:
            ydl.download([t["url"]])
        size_mb = round(os.path.getsize(final_glob)/1e6, 1) if os.path.exists(final_glob) else 0
        if size_mb > 0:
            results.append({**t, "status": "ok", "size_mb": size_mb})
            print(f"[{i:3d}/{len(keep)}] ok: {t['video_id']} ({size_mb}MB) "
                  f"- {t['title'][:60]}", flush=True)
        else:
            results.append({**t, "status": "no_file_produced", "size_mb": 0})
            print(f"[{i:3d}/{len(keep)}] failed (no file): {t['video_id']}", flush=True)
    except Exception as e:
        results.append({**t, "status": f"err_{type(e).__name__}", "size_mb": 0})
        print(f"[{i:3d}/{len(keep)}] err: {t['video_id']}: {type(e).__name__}",
              flush=True)

    time.sleep(DELAY)

# Save log
all_rows = results + [{**s, "status": s["reason"], "size_mb": 0} for s in skipped]
with open(SUMMARY_PATH, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["vessel_id", "video_id", "title",
                                       "duration", "url", "status", "size_mb"])
    w.writeheader()
    for r in all_rows:
        w.writerow({k: r.get(k, "") for k in
                    ["vessel_id", "video_id", "title", "duration",
                     "url", "status", "size_mb"]})

ok = sum(1 for r in results if r["status"] in ("ok", "cached"))
total_gb = sum(r.get("size_mb", 0) for r in results) / 1024
print(f"\nDone: {ok}/{len(keep)} downloaded successfully")
print(f"Total storage: {total_gb:.1f}GB")
print(f"Log saved to {SUMMARY_PATH}")
