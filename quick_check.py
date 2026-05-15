import pandas as pd

zones = {}
vessels = set()
rows = 0

for chunk in pd.read_csv('extended_transits.csv', low_memory=False, chunksize=500000):
    rows += len(chunk)
    vessels.update(chunk['MMSI'].astype(str).tolist())
    for zone, count in chunk['Zone'].value_counts().items():
        zones[zone] = zones.get(zone, 0) + count
    print(f"  processed {rows:,} rows so far...")

print(f"\nTotal rows: {rows:,}")
print(f"Unique vessels: {len(vessels):,}")
print(f"\nZone breakdown:")
for zone, count in sorted(zones.items(), key=lambda x: -x[1]):
    print(f"  {zone:<25} {count:>10,}")
