"""
Receiver-downtime control for AIS gap analysis.

At a ~10-second normal ping cadence, a genuine vessel-side AIS-off event
affects ONE vessel at a time. If MANY watchlist vessels fall silent in the
SAME window, that is almost certainly a shore-receiver outage (or DMA feed
gap), not fleet behaviour — those windows must be excluded before any gap
is treated as a dark-activity candidate.

Method: bin all pings (whole frame, all watchlist vessels) into 15-min slots;
count distinct vessels seen per slot. Slots where the active-vessel count
collapses far below its rolling normal are suspect receiver outages. Any
candidate gap (from ais_dark_candidates.csv) whose window overlaps a suspect
slot is flagged 'receiver-suspect' and should be dropped.

Prefers tracks_q1_2026.csv; falls back to extended_transits_q1_2026.csv.
"""
import os
import numpy as np
import pandas as pd

SRC = 'tracks_q1_2026.csv' if os.path.exists('tracks_q1_2026.csv') else 'extended_transits_q1_2026.csv'
print(f"Reading {SRC}")
df = pd.read_csv(SRC, low_memory=False, usecols=['Timestamp','MMSI'])
df['ts'] = pd.to_datetime(df['Timestamp'], format='%d/%m/%Y %H:%M:%S', errors='coerce')
df = df.dropna(subset=['ts'])
df['MMSI'] = df['MMSI'].astype(str)

# active vessels per 15-min slot
df['slot'] = df['ts'].dt.floor('15min')
active = df.groupby('slot')['MMSI'].nunique()
active = active.asfreq('15min', fill_value=0)

# rolling normal (1-day window) and a low-water flag
roll = active.rolling(96, min_periods=24, center=True).median()
# suspect: active drops below 35% of local normal AND normal is non-trivial
suspect = active[(active < 0.35 * roll) & (roll >= 5)]
print(f"15-min slots total: {len(active):,}")
print(f"Suspect receiver-outage slots: {len(suspect):,} "
      f"({len(suspect)/len(active)*100:.1f}% of time)")
if len(suspect):
    print("\nLongest suspect windows (consecutive slots):")
    s = suspect.index.to_series()
    grp = (s.diff() > pd.Timedelta('15min')).cumsum()
    for _, win in s.groupby(grp):
        if len(win) >= 2:
            print(f"  {win.iloc[0]} -> {win.iloc[-1]}  ({len(win)*15} min)")

suspect.to_frame('active_vessels').to_csv('receiver_suspect_slots.csv')
print(f"\nsaved receiver_suspect_slots.csv")

# cross-flag candidate gaps if present
if os.path.exists('ais_dark_candidates.csv'):
    cand = pd.read_csv('ais_dark_candidates.csv')
    cand['gap_end'] = pd.to_datetime(cand['Timestamp'], format='%d/%m/%Y %H:%M:%S', errors='coerce')
    cand['gap_start'] = cand['gap_end'] - pd.to_timedelta(cand['dt_min'], unit='m')
    suspect_set = set(suspect.index)
    def overlaps(r):
        slots = pd.date_range(r['gap_start'].floor('15min'), r['gap_end'].ceil('15min'), freq='15min')
        return any(s in suspect_set for s in slots)
    cand['receiver_suspect'] = cand.apply(overlaps, axis=1)
    clean = cand[~cand['receiver_suspect']]
    print(f"\nCandidate gaps: {len(cand)} | receiver-suspect: {cand['receiver_suspect'].sum()} "
          f"| surviving (vessel-side): {len(clean)}")
    clean.to_csv('ais_dark_candidates_clean.csv', index=False)
    print("saved ais_dark_candidates_clean.csv  <-- use THIS for SAR cross-check")
