"""
python3 detect_ais_gaps.pyAIS dark-activity gap analysis — candidate detection, not proof.

Looks for temporal gaps in each vessel's ping stream inside high-coverage
Danish zones (Great Belt, Øresund, Kattegat), where a present vessel cannot
plausibly be out of receiver range. Classifies each gap by implied speed
(great-circle distance / elapsed time):

  DARK TRANSIT   gap > GAP_MIN, implied speed > 6 kn  -> moved while silent
  SILENT DWELL   gap > GAP_MIN, implied speed < 2 kn  -> stationary & silent
  (ambiguous middle band reported but not counted as either)

Prefers tracks_q1_2026.csv (continuous, bounding-box) if present; falls back
to extended_transits_q1_2026.csv (zone-filtered) with a confound warning.

CAVEATS (read before quoting anything):
  - Candidates, NOT confirmation. Confirm with SAR/optical satellite imagery
    (e.g. FleetLeaks) for the vessel+window before claiming AIS-off.
  - Receiver downtime mimics vessel-side gaps; cross-check against whether
    OTHER vessels also went dark in the same window (fleet-wide gap = receiver).
  - A vessel changing MMSI mid-voyage appears as a gap/disappearance; that is
    identity laundering, detectable via IMO continuity, not transponder-off.
  - Legitimate anchoring still transmits (~3 min); true silence is the signal.
"""
import sys
import numpy as np
import pandas as pd

GAP_MIN = 45          # minutes; below this is normal AIS spacing
GAP_MAX = 24*60       # minutes; above this, treat as separate voyages (not dark)
HIGH_COV = ['Great_Belt', 'Oresund', 'Kattegat']

import os
SRC = 'tracks_q1_2026.csv' if os.path.exists('tracks_q1_2026.csv') else 'extended_transits_q1_2026.csv'
if SRC != 'tracks_q1_2026.csv':
    print("WARNING: using zone-filtered file. Gaps are confounded by box-exit; "
          "run extract_tracks_q1_2026.py for a clean result.\n")

cols = pd.read_csv(SRC, nrows=0).columns
zcol = 'Zone' if 'Zone' in cols else None
df = pd.read_csv(SRC, low_memory=False,
                 usecols=[c for c in ['Timestamp','MMSI','Latitude','Longitude','Zone'] if c in cols])
df['ts'] = pd.to_datetime(df['Timestamp'], format='%d/%m/%Y %H:%M:%S', errors='coerce')
df = df.dropna(subset=['ts','Latitude','Longitude'])
df['MMSI'] = df['MMSI'].astype(str).str.strip()
df['Latitude'] = pd.to_numeric(df['Latitude'], errors='coerce')
df['Longitude'] = pd.to_numeric(df['Longitude'], errors='coerce')

if zcol:
    df = df[df['Zone'].isin(HIGH_COV)]
    print(f"Restricted to high-coverage zones {HIGH_COV}")
df = df.sort_values(['MMSI','ts'])

# consecutive deltas per vessel
g = df.groupby('MMSI')
df['dt_min'] = g['ts'].diff().dt.total_seconds() / 60
df['plat'] = g['Latitude'].shift()
df['plon'] = g['Longitude'].shift()

def haversine_nm(la1,lo1,la2,lo2):
    R=3440.065  # nm
    p=np.radians; dla=p(la2-la1); dlo=p(lo2-lo1)
    a=np.sin(dla/2)**2+np.cos(p(la1))*np.cos(p(la2))*np.sin(dlo/2)**2
    return 2*R*np.arcsin(np.sqrt(a))

# baseline normal spacing
normal = df['dt_min'][(df['dt_min']>0)&(df['dt_min']<10)]
print(f"Baseline normal in-zone ping interval: median {normal.median():.2f} min, "
      f"95th pct {normal.quantile(.95):.1f} min\n")

gaps = df[(df['dt_min']>GAP_MIN)&(df['dt_min']<=GAP_MAX)].copy()
gaps['dist_nm'] = haversine_nm(gaps['plat'],gaps['plon'],gaps['Latitude'],gaps['Longitude'])
gaps['impl_kn'] = gaps['dist_nm']/(gaps['dt_min']/60)

dark = gaps[gaps['impl_kn']>6]
dwell = gaps[gaps['impl_kn']<2]
print(f"Gaps {GAP_MIN}min–{GAP_MAX//60}h within high-coverage zones: {len(gaps):,}")
print(f"  DARK TRANSIT  (moved while silent, >6 kn implied): {len(dark):,} gaps, "
      f"{dark['MMSI'].nunique()} vessels")
print(f"  SILENT DWELL  (stationary & silent, <2 kn implied): {len(dwell):,} gaps, "
      f"{dwell['MMSI'].nunique()} vessels")
print(f"  total vessels with >=1 candidate gap: {gaps['MMSI'].nunique()} of {df['MMSI'].nunique()}\n")

# rank vessels by dark-transit count
top = (dark.groupby('MMSI')
       .agg(dark_gaps=('dt_min','size'),
            max_gap_h=('dt_min', lambda s: s.max()/60),
            mean_impl_kn=('impl_kn','mean'),
            max_dist_nm=('dist_nm','max'))
       .sort_values('dark_gaps',ascending=False).head(15).round(1))
print("Top 15 vessels by dark-transit gap count:")
print(top.to_string())

dark.to_csv('ais_dark_candidates.csv', index=False)
print(f"\nsaved ais_dark_candidates.csv ({len(dark)} dark-transit gaps with positions+timestamps)")
print("\nNEXT STEP for any headline claim: take the top vessels + gap windows from")
print("ais_dark_candidates.csv and cross-check SAR/optical imagery for that vessel+time.")
