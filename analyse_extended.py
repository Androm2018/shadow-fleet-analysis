import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
from matplotlib.patches import Patch

print("Loading data in chunks...")
zones = {}
vessels_per_zone = {}
daily_zone = {}
skagen_vessels = set()
rows = 0

for chunk in pd.read_csv('extended_transits.csv', low_memory=False, chunksize=500000):
    chunk['Timestamp'] = pd.to_datetime(chunk['Timestamp'], dayfirst=True, errors='coerce')
    chunk['MMSI'] = chunk['MMSI'].astype(str).str.strip()
    chunk['date'] = chunk['Timestamp'].dt.date
    rows += len(chunk)

    for zone, grp in chunk.groupby('Zone'):
        zones[zone] = zones.get(zone, 0) + len(grp)
        if zone not in vessels_per_zone:
            vessels_per_zone[zone] = set()
        vessels_per_zone[zone].update(grp['MMSI'].tolist())
        for date, dgrp in grp.groupby('date'):
            key = (str(date), zone)
            if key not in daily_zone:
                daily_zone[key] = set()
            daily_zone[key].update(dgrp['MMSI'].tolist())

    skagen_chunk = chunk[chunk['Zone'] == 'Skagen']
    anchored = skagen_chunk[skagen_chunk['Status'].str.contains('anchor', case=False, na=False)]
    skagen_vessels.update(anchored['MMSI'].tolist())

print(f"Total rows: {rows:,}")

# Build daily dataframe
daily_records = [{'date': pd.to_datetime(k[0]), 'Zone': k[1], 'vessels': len(v)}
                 for k, v in daily_zone.items()]
daily_df = pd.DataFrame(daily_records)

fig, axes = plt.subplots(2, 2, figsize=(18, 12), facecolor='#0d1520')
fig.suptitle('Shadow fleet — Baltic routing analysis, Feb–Oct 2025\n'
             'Source: DMA AIS data · Ukrainian GUR watchlist · 210 vessels · 13.5M pings',
             color='white', fontsize=14)

# ── Pie 1: Bornholm split ──
ax1 = axes[0, 0]
ax1.set_facecolor('#0d1520')
born_n = zones.get('Bornholm_North', 0)
born_s = zones.get('Bornholm_South', 0)
born_total = born_n + born_s
wedges, texts, autotexts = ax1.pie(
    [born_n, born_s],
    labels=['North of Bornholm', 'South of Bornholm'],
    colors=['#185FA5', '#3B6D11'],
    autopct='%1.1f%%', startangle=90,
    pctdistance=0.75,
    textprops={'color': 'white', 'fontsize': 10},
    wedgeprops={'linewidth': 2, 'edgecolor': '#0d1520'}
)
for at in autotexts: at.set_fontweight('bold')
ax1.set_title(f'Bornholm routing split\n({born_total:,} pings · {len(vessels_per_zone.get("Bornholm_North",set()) | vessels_per_zone.get("Bornholm_South",set()))} vessels)',
              color='white', fontsize=11)

# ── Pie 2: Straits split ──
ax2 = axes[0, 1]
ax2.set_facecolor('#0d1520')
gb = zones.get('Great_Belt', 0)
or_ = zones.get('Oresund', 0)
straits_total = gb + or_
wedges2, texts2, autotexts2 = ax2.pie(
    [gb, or_],
    labels=['Great Belt', 'Øresund'],
    colors=['#185FA5', '#3B6D11'],
    autopct='%1.1f%%', startangle=90,
    pctdistance=0.75,
    textprops={'color': 'white', 'fontsize': 10},
    wedgeprops={'linewidth': 2, 'edgecolor': '#0d1520'}
)
for at in autotexts2: at.set_fontweight('bold')
ax2.set_title(f'Danish Straits split\n({straits_total:,} pings · full Feb–Oct 2025)',
              color='white', fontsize=11)

# ── Bar: zone summary ──
ax3 = axes[1, 0]
ax3.set_facecolor('#111827')
zone_order = ['Origin_Kaliningrad', 'Bornholm_South', 'Bornholm_North',
              'Oresund', 'Great_Belt', 'Kattegat', 'Skagen']
zone_labels = ['Kaliningrad origin', 'S. of Bornholm', 'N. of Bornholm',
               'Øresund', 'Great Belt', 'Kattegat', 'Skagen']
zone_colors = ['#e8a020', '#3B6D11', '#185FA5', '#3B6D11', '#185FA5', '#5ba3e8', '#d44040']
vals = [zones.get(z, 0) for z in zone_order]
bars = ax3.barh(zone_labels, vals, color=zone_colors, alpha=0.85)
for bar, val in zip(bars, vals):
    ax3.text(val + 50000, bar.get_y() + bar.get_height()/2,
             f'{val/1e6:.1f}M', va='center', color='#aaa', fontsize=9)
ax3.set_title('Total pings by zone (Feb–Oct 2025)', color='white', fontsize=11)
ax3.set_xlabel('AIS pings', color='#aaa')
ax3.tick_params(colors='#aaa', labelsize=9)
ax3.grid(True, color='#2a3050', linewidth=0.5, axis='x')
for spine in ax3.spines.values(): spine.set_color('#2a3050')

# ── Daily time series: Bornholm routes ──
ax4 = axes[1, 1]
ax4.set_facecolor('#111827')
for zone, col, label in [('Bornholm_North','#185FA5','N. of Bornholm'),
                          ('Bornholm_South','#3B6D11','S. of Bornholm'),
                          ('Skagen','#d44040','Skagen (loitering)')]:
    zone_daily = daily_df[daily_df['Zone'] == zone].sort_values('date')
    if not zone_daily.empty:
        roll = zone_daily.set_index('date')['vessels'].rolling(7, min_periods=1).mean()
        ax4.plot(roll.index, roll.values, color=col, linewidth=1.8, label=label, alpha=0.85)
ax4.set_title('Daily vessels by Baltic zone (7-day avg)', color='white', fontsize=11)
ax4.set_ylabel('Unique vessels', color='#aaa')
ax4.tick_params(colors='#aaa', labelsize=8)
ax4.legend(facecolor='#0d1220', labelcolor='white', edgecolor='#2a3050', fontsize=9)
ax4.grid(True, color='#2a3050', linewidth=0.5)
for spine in ax4.spines.values(): spine.set_color('#2a3050')
ax4.xaxis.set_major_formatter(mdates.DateFormatter('%b %Y'))
plt.setp(ax4.xaxis.get_majorticklabels(), rotation=45, ha='right', color='#aaa')

plt.tight_layout()
plt.savefig('baltic_routing.png', dpi=150, bbox_inches='tight', facecolor='#0d1520')
print("Saved baltic_routing.png")

print(f"\n=== SUMMARY ===")
print(f"Bornholm North: {born_n:,} ({born_n/born_total*100:.1f}%) | {len(vessels_per_zone.get('Bornholm_North',set()))} vessels")
print(f"Bornholm South: {born_s:,} ({born_s/born_total*100:.1f}%) | {len(vessels_per_zone.get('Bornholm_South',set()))} vessels")
print(f"Great Belt:     {gb:,} ({gb/straits_total*100:.1f}%)")
print(f"Oresund:        {or_:,} ({or_/straits_total*100:.1f}%)")
print(f"Kaliningrad:    {zones.get('Origin_Kaliningrad',0):,} pings | {len(vessels_per_zone.get('Origin_Kaliningrad',set()))} vessels")
print(f"Skagen anchored vessels: {len(skagen_vessels)}")
