"""
Q1 2026 DMA loop — fast version. Drop-in replacement for run_q1_2026.py;
resumes from the same q1_2026_done.txt and appends to the same output CSV.

Speedups vs v1:
  1. grep -F pre-filter: raw daily CSV (30M+ rows) is reduced to watchlist-MMSI
     candidate rows with fixed-string grep before pandas parses anything.
     False positives (an MMSI digit-string appearing in another column) are
     removed by the exact MMSI-column check afterwards.
  2. usecols: only the 9 columns the analysis needs are parsed.

Kill the old process first:  kill %1   (or: pkill -f run_q1_2026.py)
Then:  nohup python3 -u run_q1_2026_fast.py > q1_2026.log 2>&1 &
"""
import os, sqlite3, subprocess
from datetime import date, timedelta
import pandas as pd

ZONES = {
    'Oresund':            {'lat': (55.5, 56.2), 'lon': (12.4, 13.1)},
    'Great_Belt':         {'lat': (55.0, 55.9), 'lon': (10.4, 11.2)},
    'Bornholm_North':     {'lat': (55.5, 56.5), 'lon': (13.0, 17.0)},
    'Bornholm_South':     {'lat': (54.0, 55.0), 'lon': (13.0, 17.0)},
    'Origin_UstLuga':     {'lat': (59.3, 60.2), 'lon': (27.0, 29.5)},
    'Origin_StPete':      {'lat': (59.5, 60.2), 'lon': (29.5, 31.0)},
    'Origin_Kaliningrad': {'lat': (54.3, 55.0), 'lon': (19.0, 21.5)},
    'Kattegat':           {'lat': (56.5, 57.8), 'lon': (10.0, 12.5)},
    'Skagen':             {'lat': (57.5, 58.2), 'lon': (10.0, 11.0)},
}
ALL_COLS = ['Timestamp','Type','MMSI','Latitude','Longitude','Status','ROT','SOG','COG',
            'Heading','IMO','Callsign','Name','ShipType','CargoType','Width','Length',
            'PosType','Draught','Destination','ETA','DataSource','A','B','C','D']
KEEP = ['Timestamp','MMSI','Latitude','Longitude','SOG','COG','IMO','Name','Destination']
OUT, DONE = 'extended_transits_q1_2026.csv', 'q1_2026_done.txt'

conn = sqlite3.connect('Vessels2.db')
mmsi_set = set(pd.read_sql('SELECT mmsi FROM vessels', conn)['mmsi'].astype(str).str.strip())
conn.close()
with open('mmsi_patterns.txt', 'w') as f:
    f.write('\n'.join(sorted(mmsi_set)) + '\n')
print(f"Watchlist: {len(mmsi_set)} MMSIs (Vessels2.db)")

done = set()
if os.path.exists(DONE):
    done = set(open(DONE).read().split())

# one-off migration: days processed by run_q1_2026.py wrote all 26 columns;
# reduce existing output to KEEP+Zone so appended rows align
if os.path.exists(OUT):
    head = pd.read_csv(OUT, nrows=1)
    if len(head.columns) > len(KEEP) + 1:
        print("Migrating existing output to reduced column schema...", flush=True)
        full = pd.read_csv(OUT, low_memory=False)
        full[KEEP + ['Zone']].to_csv(OUT + '.tmp', index=False)
        os.replace(OUT + '.tmp', OUT)
        print(f"  migrated {len(full):,} rows", flush=True)
write_header = not os.path.exists(OUT)

d, end = date(2026, 1, 1), date(2026, 3, 31)
while d <= end:
    ds = d.isoformat()
    d += timedelta(days=1)
    if ds in done:
        continue
    zf, cf, sub = f"aisdk-{ds}.zip", f"aisdk-{ds}.csv", f"subset-{ds}.csv"
    print(f"\n=== {ds} ===", flush=True)

    if subprocess.run(['wget', '-q', f'http://aisdata.ais.dk/{zf}']).returncode != 0:
        print("  download failed, skipping (rerun later)"); continue
    subprocess.run(['unzip', '-oq', zf])
    os.remove(zf)
    if not os.path.exists(cf):
        print("  unexpected zip contents, skipping"); continue

    # fast pre-filter: candidate rows containing any watchlist MMSI string
    with open(sub, 'w') as out:
        subprocess.run(['grep', '-F', '-f', 'mmsi_patterns.txt', cf], stdout=out)
    os.remove(cf)

    hits_total = 0
    if os.path.getsize(sub) > 0:
        df = pd.read_csv(sub, names=ALL_COLS, usecols=KEEP,
                         on_bad_lines='skip', low_memory=False)
        df['MMSI'] = df['MMSI'].astype(str).str.strip()
        df = df[df['MMSI'].isin(mmsi_set)]                 # drop grep false positives
        df['Latitude']  = pd.to_numeric(df['Latitude'],  errors='coerce')
        df['Longitude'] = pd.to_numeric(df['Longitude'], errors='coerce')
        df = df.dropna(subset=['Latitude', 'Longitude'])
        parts = []
        for zone, b in ZONES.items():
            h = df[df['Latitude'].between(*b['lat']) &
                   df['Longitude'].between(*b['lon'])].copy()
            if len(h):
                h['Zone'] = zone
                parts.append(h)
        if parts:
            res = pd.concat(parts)
            res.to_csv(OUT, mode='a', header=write_header, index=False)
            write_header = False
            hits_total = len(res)
    os.remove(sub)
    with open(DONE, 'a') as f:
        f.write(ds + '\n')
    print(f"  {hits_total:,} pings saved | disk freed", flush=True)

print("\nQ1 2026 loop complete.")
