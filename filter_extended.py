import sqlite3, pandas as pd, os

ZONES = {
    'Oresund':              {'lat': (55.5, 56.2), 'lon': (12.4, 13.1)},
    'Great_Belt':           {'lat': (55.0, 55.9), 'lon': (10.4, 11.2)},
    'Bornholm_North':       {'lat': (55.5, 56.5), 'lon': (13.0, 17.0)},
    'Bornholm_South':       {'lat': (54.0, 55.0), 'lon': (13.0, 17.0)},
    'Origin_UstLuga':       {'lat': (59.3, 60.2), 'lon': (27.0, 29.5)},
    'Origin_StPete':        {'lat': (59.5, 60.2), 'lon': (29.5, 31.0)},
    'Origin_Kaliningrad':   {'lat': (54.3, 55.0), 'lon': (19.0, 21.5)},
    'Kattegat':             {'lat': (56.5, 57.8), 'lon': (10.0, 12.5)},
    'Skagen':               {'lat': (57.5, 58.2), 'lon': (10.0, 11.0)},
}

cols = ['Timestamp','Type','MMSI','Latitude','Longitude','Status','ROT','SOG','COG',
        'Heading','IMO','Callsign','Name','ShipType','CargoType','Width','Length',
        'PosType','Draught','Destination','ETA','DataSource','A','B','C','D']

conn = sqlite3.connect("Vessels1.db")
vessels = pd.read_sql("SELECT mmsi, name FROM vessels", conn)
conn.close()
mmsi_set = set(vessels['mmsi'].astype(str).str.strip())
print(f"Watchlist: {len(mmsi_set)} vessels")

import sys
filename = sys.argv[1]
print(f"Scanning {filename}...")
all_hits = []
for chunk in pd.read_csv(filename, names=cols, chunksize=500000,
                         on_bad_lines='skip', low_memory=False):
    chunk['Latitude']  = pd.to_numeric(chunk['Latitude'],  errors='coerce')
    chunk['Longitude'] = pd.to_numeric(chunk['Longitude'], errors='coerce')
    chunk['MMSI'] = chunk['MMSI'].astype(str).str.strip()
    chunk = chunk[chunk['MMSI'].isin(mmsi_set)].dropna(subset=['Latitude','Longitude'])
    for zone, bounds in ZONES.items():
        hits = chunk[
            chunk['Latitude'].between(*bounds['lat']) &
            chunk['Longitude'].between(*bounds['lon'])
        ].copy()
        if len(hits):
            hits['Zone'] = zone
            all_hits.append(hits)

if all_hits:
    result = pd.concat(all_hits)
    out = 'extended_transits.csv'
    result.to_csv(out, mode='a', header=not os.path.exists(out), index=False)
    print(f"  -> {len(result):,} pings saved")
else:
    print(f"  -> 0 hits")
