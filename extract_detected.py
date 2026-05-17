import pandas as pd
import sqlite3

mmsi_seen = set()
for chunk in pd.read_csv('extended_transits.csv', usecols=['MMSI'], chunksize=500000):
    mmsi_seen.update(chunk['MMSI'].astype(str).str.strip().unique())

print(f"Unique MMSIs seen in transits: {len(mmsi_seen)}")

conn = sqlite3.connect('Vessels1.db')
placeholders = ','.join('?' * len(mmsi_seen))
detected = pd.read_sql(
    f"SELECT mmsi, imo, name FROM vessels WHERE mmsi IN ({placeholders})",
    conn, params=list(mmsi_seen)
)
conn.close()

detected.to_csv('detected_vessels.csv', index=False)
print(f"{len(detected)} vessels matched to watchlist")
print(f"  with names: {detected['name'].notna().sum()}")
print(f"  with IMO:   {detected['imo'].notna().sum()}")
