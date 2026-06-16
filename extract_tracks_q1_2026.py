"""
Q1 2026 continuous-track extract — Danish waters (DMA).

Same download + grep-by-MMSI pipeline as run_q1_2026_fast.py, but keeps ALL
watchlist pings inside ONE map-frame bounding box instead of the nine zone
boxes. This preserves the connecting segments between chokepoints, so the
density/track maps show continuous corridors rather than isolated zone blobs.

Writes a separate, minimal-column file (tracks_q1_2026.csv) — does NOT touch
extended_transits_q1_2026.csv (the zone-filtered file the analysis suite uses).

Resumable via tracks_q1_2026_done.txt. Same runtime as the original Q1 loop
(download-bound); the wider filter keeps ~3-5x more pings per vessel but adds
negligible time.

Run in shadow-fleet-analysis Codespace:
  nohup python3 -u extract_tracks_q1_2026.py > tracks_q1.log 2>&1 &
"""
import os, sqlite3, subprocess
from datetime import date, timedelta
import pandas as pd

# Capture box: a small margin beyond the display frame (8.0-16.5E, 54.0-58.6N)
# so corridors reach the edges naturally rather than cutting hard.
BOX = {'lon': (7.5, 17.5), 'lat': (53.6, 58.9)}

ALL_COLS = ['Timestamp','Type','MMSI','Latitude','Longitude','Status','ROT','SOG','COG',
            'Heading','IMO','Callsign','Name','ShipType','CargoType','Width','Length',
            'PosType','Draught','Destination','ETA','DataSource','A','B','C','D']
KEEP = ['Timestamp','MMSI','Latitude','Longitude','SOG']     # minimal: enough for maps
OUT, DONE = 'tracks_q1_2026.csv', 'tracks_q1_2026_done.txt'

conn = sqlite3.connect('Vessels2.db')
mmsi_set = set(pd.read_sql('SELECT mmsi FROM vessels', conn)['mmsi'].astype(str).str.strip())
conn.close()
with open('mmsi_patterns.txt', 'w') as f:
    f.write('\n'.join(sorted(mmsi_set)) + '\n')
print(f"Watchlist: {len(mmsi_set)} MMSIs")

done = set(open(DONE).read().split()) if os.path.exists(DONE) else set()
write_header = not os.path.exists(OUT)

d, end = date(2026, 1, 1), date(2026, 3, 31)
while d <= end:
    ds = d.isoformat(); d += timedelta(days=1)
    if ds in done:
        continue
    zf, cf, sub = f"aisdk-{ds}.zip", f"aisdk-{ds}.csv", f"trk-{ds}.csv"
    print(f"\n=== {ds} ===", flush=True)
    if subprocess.run(['wget','-q',f'http://aisdata.ais.dk/{zf}']).returncode != 0:
        print("  download failed, skipping (rerun later)"); continue
    subprocess.run(['unzip','-oq',zf]); os.remove(zf)
    if not os.path.exists(cf):
        print("  unexpected zip contents, skipping"); continue
    with open(sub,'w') as out:
        subprocess.run(['grep','-F','-f','mmsi_patterns.txt',cf], stdout=out)
    os.remove(cf)

    n = 0
    if os.path.getsize(sub) > 0:
        df = pd.read_csv(sub, names=ALL_COLS, usecols=KEEP,
                         on_bad_lines='skip', low_memory=False)
        df['MMSI'] = df['MMSI'].astype(str).str.strip()
        df = df[df['MMSI'].isin(mmsi_set)]
        df['Latitude']  = pd.to_numeric(df['Latitude'],  errors='coerce')
        df['Longitude'] = pd.to_numeric(df['Longitude'], errors='coerce')
        df = df.dropna(subset=['Latitude','Longitude'])
        df = df[df['Latitude'].between(*BOX['lat']) & df['Longitude'].between(*BOX['lon'])]
        if len(df):
            df.to_csv(OUT, mode='a', header=write_header, index=False)
            write_header = False; n = len(df)
    os.remove(sub)
    with open(DONE,'a') as f:
        f.write(ds + '\n')
    print(f"  {n:,} pings kept", flush=True)

print("\nTrack extract complete -> tracks_q1_2026.csv")
