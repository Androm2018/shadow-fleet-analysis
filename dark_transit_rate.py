"""
Exposure-normalised dark-transit rate, with bootstrap CI.

Turns the raw dark-transit candidate count into a defensible rate by
normalising for how much each vessel was actually observable in high-coverage
zones. Reports two exposure measures and a vessel-clustered bootstrap CI.

Definitions (state these in the paper):
  - High-coverage zones: Great Belt, Øresund, Kattegat (dense receiver cover;
    a present vessel cannot plausibly be out of range).
  - Transit: a contiguous presence in high-coverage zones, segmented whenever
    the vessel is absent from those zones for > SPLIT_H hours (= separate voyage).
  - Exposure (hours): summed transit durations (first->last in-zone ping per
    transit). Dark periods WITHIN a transit are included, so exposure counts
    time-at-risk-of-being-observed-dark, not just time-pinging.
  - Dark-transit event: a within-transit ping gap of GAP_MIN..SPLIT_H with
    implied speed > DARK_KN kn (vessel demonstrably moved while silent in
    high-coverage water). Upper bound = SPLIT_H so numerator/denominator align.

Rates reported:
  - dark events per 100 transits
  - dark events per 1,000 exposure-hours
  - share of vessels (made >=1 transit) with >=1 dark event  [reported, but
    flagged as opportunity-weighted, NOT the headline]
Bootstrap: resample VESSELS with replacement (the clustering unit) x N_BOOT.

Requires tracks_q1_2026.csv (continuous). Exits if only the zone file exists.
"""
import os, sys
import numpy as np
import pandas as pd

GAP_MIN_MIN = 45        # minutes: floor for an anomalous silence
SPLIT_H     = 6         # hours: absence > this = separate transit, and dark-gap ceiling
DARK_KN     = 6         # kn: implied speed above which a silent gap = "moved while dark"
HIGH_COV    = ['Great_Belt', 'Oresund', 'Kattegat']
N_BOOT      = 2000
RNG         = np.random.default_rng(42)

if not os.path.exists('tracks_q1_2026.csv'):
    sys.exit("Needs tracks_q1_2026.csv (continuous). The zone-filtered file cannot "
             "measure exposure (time-in-zone). Run extract_tracks_q1_2026.py first.")

cols = pd.read_csv('tracks_q1_2026.csv', nrows=0).columns
if 'Zone' not in cols:
    # tracks file is bounding-box (no Zone col) -> classify on the fly
    ZB = {'Great_Belt':{'lat':(55.0,55.9),'lon':(10.4,11.2)},
          'Oresund':   {'lat':(55.5,56.2),'lon':(12.4,13.1)},
          'Kattegat':  {'lat':(56.5,57.8),'lon':(10.0,12.5)}}
    df = pd.read_csv('tracks_q1_2026.csv', low_memory=False,
                     usecols=['Timestamp','MMSI','Latitude','Longitude'])
    df['Latitude']=pd.to_numeric(df['Latitude'],errors='coerce')
    df['Longitude']=pd.to_numeric(df['Longitude'],errors='coerce')
    def zone(la,lo):
        for z,b in ZB.items():
            if b['lat'][0]<=la<=b['lat'][1] and b['lon'][0]<=lo<=b['lon'][1]: return z
        return None
    df['Zone']=[zone(la,lo) for la,lo in zip(df['Latitude'],df['Longitude'])]
else:
    df = pd.read_csv('tracks_q1_2026.csv', low_memory=False,
                     usecols=['Timestamp','MMSI','Latitude','Longitude','Zone'])
    df['Latitude']=pd.to_numeric(df['Latitude'],errors='coerce')
    df['Longitude']=pd.to_numeric(df['Longitude'],errors='coerce')

df['ts']=pd.to_datetime(df['Timestamp'],format='%d/%m/%Y %H:%M:%S',errors='coerce')
df=df.dropna(subset=['ts','Latitude','Longitude'])
df['MMSI']=df['MMSI'].astype(str).str.strip()
df=df[df['Zone'].isin(HIGH_COV)].sort_values(['MMSI','ts'])

def haversine_nm(la1,lo1,la2,lo2):
    R=3440.065; p=np.radians; dla=p(la2-la1); dlo=p(lo2-lo1)
    a=np.sin(dla/2)**2+np.cos(p(la1))*np.cos(p(la2))*np.sin(dlo/2)**2
    return 2*R*np.arcsin(np.sqrt(a))

# per-vessel: transits, exposure hours, dark events
per = {}   # mmsi -> dict
for mmsi, g in df.groupby('MMSI'):
    g=g.reset_index(drop=True)
    dt_h=g['ts'].diff().dt.total_seconds()/3600
    # transit segmentation: new transit when absence > SPLIT_H
    new_transit=(dt_h>SPLIT_H)|(dt_h.isna())
    tid=new_transit.cumsum()
    n_transits=tid.nunique()
    # exposure = sum of (last-first) per transit
    exp_h=0.0
    for _,seg in g.groupby(tid):
        exp_h+=(seg['ts'].iloc[-1]-seg['ts'].iloc[0]).total_seconds()/3600
    per[mmsi]={'transits':n_transits,'exposure_h':exp_h,'dark':0}

# numerator from the VALIDATED candidate set (detect_ais_gaps + downtime filter),
# NOT re-detected here, so the rate's events == the candidates you trust.
CAND='ais_dark_candidates_clean.csv' if os.path.exists('ais_dark_candidates_clean.csv') else 'ais_dark_candidates.csv'
if not os.path.exists(CAND):
    sys.exit("Run detect_ais_gaps.py (and receiver_downtime_check.py) first to produce the candidate set.")
cand=pd.read_csv(CAND)
cand['MMSI']=cand['MMSI'].astype(str).str.strip()
dark_by=cand.groupby('MMSI').size()
for m,c in dark_by.items():
    if m in per: per[m]['dark']=int(c)
print(f"Numerator source: {CAND} ({len(cand)} validated dark candidates, "
      f"{cand['MMSI'].nunique()} vessels)\n")

P=pd.DataFrame.from_dict(per, orient='index', columns=['transits','exposure_h','dark'])
if P.empty:
    sys.exit("No vessels with pings in high-coverage zones — check Zone labels / frame.")
P['transits']=P['transits'].astype(int); P['dark']=P['dark'].astype(int)
P['exposure_h']=P['exposure_h'].astype(float)

tot_dark=int(P['dark'].sum()); tot_tr=int(P['transits'].sum())
tot_exp=float(P['exposure_h'].sum()); n_vess=len(P)
vess_with=int((P['dark']>0).sum())

rate_tr =tot_dark/tot_tr*100
rate_exp=tot_dark/tot_exp*1000

# bootstrap over vessels
keys=P.index.to_numpy()
bt_tr=[]; bt_exp=[]
for _ in range(N_BOOT):
    samp=RNG.choice(keys,size=len(keys),replace=True)
    s=P.loc[samp]
    if s['transits'].sum()>0: bt_tr.append(s['dark'].sum()/s['transits'].sum()*100)
    if s['exposure_h'].sum()>0: bt_exp.append(s['dark'].sum()/s['exposure_h'].sum()*1000)
ci=lambda a:(np.percentile(a,2.5),np.percentile(a,97.5))
tr_lo,tr_hi=ci(bt_tr); ex_lo,ex_hi=ci(bt_exp)

print("=== EXPOSURE-NORMALISED DARK-TRANSIT RATE (Q1 2026, high-coverage zones) ===")
print(f"Vessels making >=1 high-coverage transit: {n_vess}")
print(f"Total high-coverage transits:             {tot_tr}")
print(f"Total exposure:                           {tot_exp:,.0f} vessel-hours in zone")
print(f"Dark-transit events (within-transit):     {tot_dark}")
print()
print(f"RATE  {rate_tr:.2f} dark events per 100 transits   (95% CI {tr_lo:.2f}–{tr_hi:.2f})")
print(f"RATE  {rate_exp:.2f} dark events per 1,000 in-zone hours (95% CI {ex_lo:.2f}–{ex_hi:.2f})")
print()
print(f"Vessel share (opportunity-weighted, NOT headline): "
      f"{vess_with}/{n_vess} = {vess_with/n_vess*100:.1f}% of vessels showed >=1 dark event")
print(f"  mean transits/vessel {P['transits'].mean():.1f}, "
      f"mean exposure/vessel {P['exposure_h'].mean():.1f} h "
      f"(range {P['transits'].min()}–{P['transits'].max()} transits)")

P.sort_values('dark',ascending=False).to_csv('dark_transit_rate_per_vessel.csv')
print("\nsaved dark_transit_rate_per_vessel.csv")
print("\nNOTE: still candidates. Confirmed rate requires imagery cross-check; report the")
print("confirmed subset separately. CI reflects sampling of vessels, not confirmation status.")
