"""
Q1 2026 Baltic/Danish-waters analysis — mirrors the Feb-Oct 2025 suite.

Inputs (same directory):
  extended_transits_q1_2026.csv   (from run_q1_2026_fast.py, deduped)
  gur_vessels_master.csv          (watchlist v2, for vessel enrichment)

Outputs:
  baltic_routing_q1_2026.png      (4-panel figure, 2025 dashboard style)
  detected_vessels_q1_2026.csv    (per-vessel table -> v5 dashboard index)
  console: validation report, headline stats, 2025 comparison
"""
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# 2025 published baselines (Feb-Oct 2025 run, Vessels1.db)
BASE_2025 = {'gb_share': 81.5, 'or_share': 18.5, 'vessels_per_day': 3.46,
             'vessels': 210, 'speed_note': 'all top-20 exceeded 12-kn advisory'}

print("Loading...")
df = pd.read_csv('extended_transits_q1_2026.csv', low_memory=False)
df['MMSI'] = df['MMSI'].astype(str).str.strip()
df['ts'] = pd.to_datetime(df['Timestamp'], format='%d/%m/%Y %H:%M:%S', errors='coerce')
df['date'] = df['ts'].dt.date
df['SOG'] = pd.to_numeric(df['SOG'], errors='coerce')

# ── Validation report ────────────────────────────────────────────────────────
print("\n=== VALIDATION ===")
daily = df.groupby('date').size()
print(f"pings: {len(df):,} | vessels: {df['MMSI'].nunique()} | days with data: {len(daily)}/90")
runts = daily[daily < daily.median() * 0.25]
if len(runts):
    print(f"RUNT DAYS (<25% of median {daily.median():,.0f}):")
    print(runts.to_string())
    print(">>> consider removing these dates from q1_2026_done.txt and re-running the loop")
else:
    print("no runt days")
missing = pd.date_range('2026-01-01', '2026-03-31').difference(pd.to_datetime(pd.Series(daily.index)))
if len(missing):
    print(f"MISSING DATES: {[d.date() for d in missing]}")
print("\nZone distribution:")
print(df['Zone'].value_counts().to_string())

# ── Headline stats ───────────────────────────────────────────────────────────
print("\n=== Q1 2026 HEADLINES ===")
straits = df[df['Zone'].isin(['Great_Belt', 'Oresund'])]
gb_p = (straits['Zone'] == 'Great_Belt').sum()
or_p = (straits['Zone'] == 'Oresund').sum()
print(f"Danish Straits split (pings): Great Belt {gb_p/len(straits)*100:.1f}% / "
      f"Oresund {or_p/len(straits)*100:.1f}%  [2025: {BASE_2025['gb_share']}/{BASE_2025['or_share']}]")

# vessel-transit split: distinct vessel-days per strait
gb_vd = straits[straits['Zone'] == 'Great_Belt'].groupby(['MMSI','date']).ngroups
or_vd = straits[straits['Zone'] == 'Oresund'].groupby(['MMSI','date']).ngroups
print(f"Danish Straits split (vessel-days): Great Belt {gb_vd/(gb_vd+or_vd)*100:.1f}% / "
      f"Oresund {or_vd/(gb_vd+or_vd)*100:.1f}%  ({gb_vd+or_vd} strait vessel-days)")

born = df[df['Zone'].isin(['Bornholm_North', 'Bornholm_South'])]
bn = (born['Zone'] == 'Bornholm_North').sum()
print(f"Bornholm split (pings): North {bn/len(born)*100:.1f}% / South {100-bn/len(born)*100:.1f}%")

strait_daily = straits.groupby('date')['MMSI'].nunique()
strait_daily = strait_daily.reindex(pd.date_range('2026-01-01','2026-03-31').date, fill_value=0)
print(f"Strait transits: {strait_daily.mean():.2f} vessels/day  [2025: {BASE_2025['vessels_per_day']}]")
print(f"Detected vessels: {df['MMSI'].nunique()}  [2025: {BASE_2025['vessels']} from 1,206-vessel list; "
      f"now 1,480 MMSIs]")

print("\nSpeed by zone (SOG > 0.5 kn, underway):")
moving = df[df['SOG'] > 0.5]
spd = moving.groupby('Zone')['SOG'].agg(['mean', 'max', 'count']).round(1)
print(spd.to_string())
strait_mov = moving[moving['Zone'].isin(['Great_Belt', 'Oresund'])]
ex = strait_mov.groupby('MMSI')['SOG'].mean()
print(f"\nVessels with mean strait SOG > 12 kn advisory: {(ex > 12).sum()} of {len(ex)} "
      f"strait transitors ({(ex > 12).mean()*100:.0f}%)  [2025: {BASE_2025['speed_note']}]")

# ── Per-vessel table (feeds v5 index) ────────────────────────────────────────
zones_per = df.groupby('MMSI')['Zone'].agg(lambda s: '|'.join(sorted(s.unique())))
per = df.groupby('MMSI').agg(
    pings=('Zone', 'size'), days_detected=('date', 'nunique'),
    first_seen=('ts', 'min'), last_seen=('ts', 'max'),
    name_ais=('Name', lambda s: s.mode().iat[0] if len(s.mode()) else '')).reset_index()
per['zones'] = per['MMSI'].map(zones_per)
sp = moving.groupby('MMSI')['SOG'].agg(['mean', 'max']).round(1)
per = per.merge(sp.rename(columns={'mean': 'sog_mean', 'max': 'sog_max'}),
                left_on='MMSI', right_index=True, how='left')

master = pd.read_csv('gur_vessels_master.csv', dtype=str)
lookup = {}
for _, r in master.iterrows():
    for col in ('mmsi_current', 'mmsi_legacy'):
        v = str(r[col]) if pd.notna(r[col]) else ''
        if v.isdigit() and v not in lookup:
            lookup[v] = r
meta = per['MMSI'].map(lambda m: lookup.get(m))
for field in ('name', 'imo', 'flag', 'vessel_type', 'build_year', 'gur_id'):
    per[f'gur_{field}'] = [getattr(r, field, None) if r is not None else None for r in meta]
per = per.sort_values('pings', ascending=False)
per.to_csv('detected_vessels_q1_2026.csv', index=False)
unmatched = per['gur_imo'].isna().sum()
print(f"\nPer-vessel table: detected_vessels_q1_2026.csv ({len(per)} vessels, "
      f"{unmatched} without master match)")
new_detected = per['gur_gur_id'].notna() & per['MMSI'].map(
    lambda m: lookup.get(m) is not None and pd.isna(lookup[m].get('mmsi_legacy')))
print(f"Detected vessels from the 209 NEW watchlist entries: {int(new_detected.sum())}")

# ── Figure ───────────────────────────────────────────────────────────────────
fig, axes = plt.subplots(2, 2, figsize=(20, 12), facecolor='#0d1520')
fig.suptitle(f'Shadow fleet — Baltic routing analysis, Q1 2026\n'
             f'Source: DMA AIS data · GUR watchlist v2 (1,404 vessels) · '
             f'{df["MMSI"].nunique()} vessels · {len(df)/1e6:.1f}M pings',
             color='white', fontsize=15)

ax = axes[0][0]; ax.set_facecolor('#0d1520')
bs = (born['Zone'] == 'Bornholm_South').sum()
ax.pie([bn, bs], labels=['North of Bornholm', 'South of Bornholm'],
       colors=['#185FA5', '#3B6D11'], autopct='%1.1f%%', startangle=90,
       textprops={'color': 'white', 'fontsize': 11},
       wedgeprops={'linewidth': 2, 'edgecolor': '#0d1520'})
ax.set_title(f'Bornholm routing split\n({len(born):,} pings · '
             f'{born["MMSI"].nunique()} vessels)', color='white', fontsize=12)

ax = axes[0][1]; ax.set_facecolor('#0d1520')
ax.pie([gb_p, or_p], labels=['Great Belt', 'Øresund'],
       colors=['#185FA5', '#3B6D11'], autopct='%1.1f%%', startangle=90,
       textprops={'color': 'white', 'fontsize': 11},
       wedgeprops={'linewidth': 2, 'edgecolor': '#0d1520'})
ax.set_title(f'Danish Straits split\n({len(straits):,} pings · Q1 2026 · '
             f'2025: {BASE_2025["gb_share"]}/{BASE_2025["or_share"]})',
             color='white', fontsize=12)

ax = axes[1][0]; ax.set_facecolor('#111827')
order = df['Zone'].value_counts().index[::-1]
vals = df['Zone'].value_counts().reindex(order)
colors = {'Skagen': '#d44040', 'Kattegat': '#5ba3e8', 'Great_Belt': '#185FA5',
          'Oresund': '#3B6D11', 'Bornholm_North': '#185FA5', 'Bornholm_South': '#3B6D11',
          'Origin_Kaliningrad': '#e8a020', 'Origin_UstLuga': '#e8a020', 'Origin_StPete': '#e8a020'}
ax.barh(vals.index, vals.values, color=[colors.get(z, '#888') for z in vals.index], alpha=0.9)
for i, v in enumerate(vals.values):
    ax.text(v, i, f' {v/1e6:.2f}M' if v > 1e5 else f' {v:,}', va='center', color='#aaa', fontsize=9)
ax.set_title('Total pings by zone (Q1 2026)', color='white', fontsize=12)
ax.tick_params(colors='#aaa', labelsize=9)
ax.grid(True, color='#2a3050', linewidth=0.5, axis='x')
for s in ax.spines.values(): s.set_color('#2a3050')

ax = axes[1][1]; ax.set_facecolor('#111827')
for zone, col, lbl in [('Great_Belt', '#185FA5', 'Great Belt'),
                       ('Oresund', '#3B6D11', 'Øresund'),
                       ('Skagen', '#d44040', 'Skagen (loitering)')]:
    zd = df[df['Zone'] == zone].groupby('date')['MMSI'].nunique()
    zd = zd.reindex(pd.date_range('2026-01-01','2026-03-31').date, fill_value=0)
    roll = pd.Series(zd.values, index=pd.to_datetime(zd.index)).rolling(7, min_periods=1).mean()
    ax.plot(roll.index, roll.values, color=col, linewidth=1.6, label=lbl)
ax.set_title('Daily vessels by zone (7-day avg)', color='white', fontsize=12)
ax.set_ylabel('Unique vessels', color='#aaa', fontsize=10)
ax.legend(facecolor='#0d1220', labelcolor='white', edgecolor='#2a3050', fontsize=9)
ax.tick_params(colors='#aaa', labelsize=9)
ax.grid(True, color='#2a3050', linewidth=0.5)
for s in ax.spines.values(): s.set_color('#2a3050')
ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %Y'))
plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right', color='#aaa')

plt.tight_layout()
plt.savefig('baltic_routing_q1_2026.png', dpi=150, bbox_inches='tight', facecolor='#0d1520')
print("\nSaved baltic_routing_q1_2026.png")
