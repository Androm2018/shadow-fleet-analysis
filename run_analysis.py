import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.colors import LinearSegmentedColormap
import warnings
warnings.filterwarnings('ignore')

df = pd.read_csv("/home/claude/shadow_fleet_2025_ais.csv")
df['timestamp'] = pd.to_datetime(df['timestamp'], dayfirst=True)
df['month'] = df['timestamp'].dt.month
df['week']  = df['timestamp'].dt.isocalendar().week

print(f"Dataset: {len(df):,} AIS pings | {df['mmsi'].nunique()} vessels | {df['timestamp'].min().date()} → {df['timestamp'].max().date()}")

# ── FIGURE 1: Route density map ──────────────────────────────────────────────
fig, axes = plt.subplots(1, 2, figsize=(18, 11), facecolor='#0a0e1a')
fig.suptitle('Russian Shadow Fleet — Baltic & North Sea Routes 2025',
             fontsize=18, color='white', fontweight='bold', y=0.97)

for ax in axes:
    ax.set_facecolor('#0a0e1a')
    ax.tick_params(colors='#888', labelsize=8)
    ax.spines[:].set_color('#1a2035')

# ── Left: KDE density map ──
ax1 = axes[0]
ax1.set_title('AIS Position Density (all voyages)', color='#ccc', fontsize=12, pad=10)

# Map extent: Baltic + North Sea
lon_min, lon_max = -8, 31
lat_min, lat_max = 50, 62

# Hexbin density
hb = ax1.hexbin(df['lon'], df['lat'],
                gridsize=55,
                cmap='YlOrRd',
                mincnt=1,
                linewidths=0.2,
                extent=[lon_min, lon_max, lat_min, lat_max])
cb = fig.colorbar(hb, ax=ax1, fraction=0.03, pad=0.02)
cb.set_label('AIS ping density', color='#aaa', fontsize=9)
cb.ax.yaxis.set_tick_params(color='#aaa')
plt.setp(cb.ax.yaxis.get_ticklabels(), color='#aaa')

# Annotate key chokepoints
chokepoints = {
    'Øresund': (12.7, 55.85),
    'Great Belt': (10.7, 55.65),
    'Skagen': (10.5, 57.75),
    'Dover Strait': (1.4, 51.1),
    'Ust-Luga': (28.4, 59.75),
    'Kattegat': (11.0, 56.8),
}
for name, (lon, lat) in chokepoints.items():
    ax1.annotate(name, (lon, lat), color='#00d4ff', fontsize=7.5,
                ha='center', fontweight='bold',
                bbox=dict(boxstyle='round,pad=0.2', facecolor='#0a0e1a', alpha=0.7, edgecolor='#00d4ff33'))

ax1.set_xlim(lon_min, lon_max)
ax1.set_ylim(lat_min, lat_max)
ax1.set_xlabel('Longitude', color='#888', fontsize=9)
ax1.set_ylabel('Latitude', color='#888', fontsize=9)
ax1.set_aspect('equal')
ax1.grid(True, color='#1a2035', linewidth=0.5, alpha=0.8)

# ── Right: Route traces by type ──
ax2 = axes[1]
ax2.set_title('Individual Vessel Tracks by Route Type', color='#ccc', fontsize=12, pad=10)

route_colors = {
    'oresund':    '#00d4ff',
    'great_belt': '#ff9f00',
    'scotland':   '#ff4d6d',
}
route_labels = {
    'oresund':    'Øresund (65%)',
    'great_belt': 'Great Belt (25%)',
    'scotland':   'Scotland bypass (10%)',
}

plotted = set()
for (mmsi, route), grp in df.groupby(['mmsi', 'route_type']):
    grp = grp.sort_values('timestamp')
    col = route_colors[route]
    alpha = 0.35
    label = route_labels[route] if route not in plotted else None
    ax2.plot(grp['lon'], grp['lat'], color=col, alpha=alpha,
             linewidth=0.8, label=label)
    plotted.add(route)

# Overlay AIS blackout gaps (red dots)
# Detect gaps > 8h between pings per vessel
blackout_lons, blackout_lats = [], []
for mmsi, grp in df.groupby('mmsi'):
    grp = grp.sort_values('timestamp')
    gaps = grp['timestamp'].diff()
    big_gaps = grp[gaps > pd.Timedelta(hours=8)]
    blackout_lons.extend(big_gaps['lon'].tolist())
    blackout_lats.extend(big_gaps['lat'].tolist())

if blackout_lons:
    ax2.scatter(blackout_lons, blackout_lats, c='#ff003c', s=8,
                alpha=0.6, zorder=5, label=f'AIS blackout resumption ({len(blackout_lons)} events)')

ax2.set_xlim(lon_min, lon_max)
ax2.set_ylim(lat_min, lat_max)
ax2.set_xlabel('Longitude', color='#888', fontsize=9)
ax2.set_ylabel('Latitude', color='#888', fontsize=9)
ax2.set_aspect('equal')
ax2.grid(True, color='#1a2035', linewidth=0.5, alpha=0.8)
legend = ax2.legend(loc='upper left', fontsize=8, facecolor='#0d1220',
                    labelcolor='white', edgecolor='#2a3050', framealpha=0.9)

plt.tight_layout(rect=[0, 0, 1, 0.96])
plt.savefig('/home/claude/fig1_route_density.png', dpi=160, bbox_inches='tight',
            facecolor='#0a0e1a')
plt.close()
print("✓ Figure 1 saved: route density map")

# ── FIGURE 2: Statistical breakdown ──────────────────────────────────────────
fig, axes = plt.subplots(2, 2, figsize=(16, 10), facecolor='#0a0e1a')
fig.suptitle('Shadow Fleet Route Statistics — Baltic/North Sea 2025',
             fontsize=16, color='white', fontweight='bold', y=0.98)
for ax in axes.flat:
    ax.set_facecolor('#111827')
    ax.tick_params(colors='#aaa', labelsize=9)
    for spine in ax.spines.values():
        spine.set_color('#2a3050')

# ── 2a: Monthly transit counts ──
ax = axes[0, 0]
monthly = df.groupby(['month', 'route_type'])['mmsi'].nunique().unstack(fill_value=0)
months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
x = np.arange(12)
w = 0.28
for i, (rt, col) in enumerate(route_colors.items()):
    vals = [monthly.get(rt, pd.Series()).get(m+1, 0) for m in range(12)]
    ax.bar(x + i*w, vals, w, color=col, alpha=0.85, label=route_labels[rt])
ax.set_title('Monthly Active Vessels by Route Type', color='#ddd', fontsize=11)
ax.set_xticks(x + w)
ax.set_xticklabels(months, color='#aaa')
ax.set_ylabel('Unique vessels', color='#aaa')
ax.legend(fontsize=8, facecolor='#0d1220', labelcolor='white', edgecolor='#2a3050')
ax.grid(axis='y', color='#2a3050', linewidth=0.5)

# ── 2b: Route share pie ──
ax = axes[0, 1]
route_counts = df.drop_duplicates(['mmsi','route_type']).groupby('route_type').size()
labels = [route_labels[r] for r in route_counts.index]
colors = [route_colors[r] for r in route_counts.index]
wedges, texts, autotexts = ax.pie(
    route_counts.values,
    labels=labels, colors=colors,
    autopct='%1.0f%%', startangle=140,
    pctdistance=0.75,
    textprops={'color': '#ddd', 'fontsize': 9},
    wedgeprops={'linewidth': 1.5, 'edgecolor': '#0a0e1a'}
)
for at in autotexts:
    at.set_color('white')
    at.set_fontweight('bold')
ax.set_title('Route Type Share (voyage count)', color='#ddd', fontsize=11)

# ── 2c: AIS blackout frequency by chokepoint zone ──
ax = axes[1, 0]
# Classify each ping into a zone
def zone(row):
    if 12.0 < row.lon < 13.5 and 55.5 < row.lat < 56.2: return 'Øresund'
    if 10.0 < row.lon < 11.5 and 55.3 < row.lat < 56.0: return 'Great Belt'
    if 10.0 < row.lon < 11.2 and 57.4 < row.lat < 58.2: return 'Skagen'
    if 8.0  < row.lon < 12.0 and 56.5 < row.lat < 57.8: return 'Kattegat'
    if -1.0 < row.lon <  3.0 and 50.8 < row.lat < 51.5: return 'Dover'
    if 20.0 < row.lon < 30.0 and 59.0 < row.lat < 60.5: return 'Gulf of Finland'
    return None

df['zone'] = df.apply(zone, axis=1)
zone_df = df[df['zone'].notna()]

# AIS blackout resumptions (gap > 8h) per zone
blackout_per_zone = {}
for mmsi, grp in df.groupby('mmsi'):
    grp = grp.sort_values('timestamp')
    grp['gap'] = grp['timestamp'].diff()
    blackouts = grp[grp['gap'] > pd.Timedelta(hours=8)]
    for _, row in blackouts.iterrows():
        z = zone(row)
        if z:
            blackout_per_zone[z] = blackout_per_zone.get(z, 0) + 1

total_pings_per_zone = zone_df.groupby('zone').size()
zones = list(total_pings_per_zone.index)
bo_rates = [blackout_per_zone.get(z, 0) / total_pings_per_zone[z] * 100 for z in zones]

bars = ax.barh(zones, bo_rates, color='#ff4d6d', alpha=0.85, edgecolor='#0a0e1a')
ax.set_title('AIS Blackout Rate by Chokepoint Zone', color='#ddd', fontsize=11)
ax.set_xlabel('% of pings followed by >8h gap', color='#aaa')
ax.tick_params(colors='#aaa')
ax.grid(axis='x', color='#2a3050', linewidth=0.5)
for bar, val in zip(bars, bo_rates):
    ax.text(val + 0.1, bar.get_y() + bar.get_height()/2,
            f'{val:.1f}%', va='center', color='#ff9f00', fontsize=9)

# ── 2d: Flag distribution ──
ax = axes[1, 1]
flag_counts = df.drop_duplicates('mmsi').groupby('flag').size().sort_values(ascending=True)
colors_flag = plt.cm.get_cmap('tab10', len(flag_counts))
bars = ax.barh(flag_counts.index, flag_counts.values,
               color=[colors_flag(i) for i in range(len(flag_counts))],
               alpha=0.85, edgecolor='#0a0e1a')
ax.set_title('Flag of Convenience Distribution', color='#ddd', fontsize=11)
ax.set_xlabel('Number of vessels', color='#aaa')
ax.tick_params(colors='#aaa')
ax.grid(axis='x', color='#2a3050', linewidth=0.5)

plt.tight_layout(rect=[0, 0, 1, 0.96])
plt.savefig('/home/claude/fig2_statistics.png', dpi=160, bbox_inches='tight',
            facecolor='#0a0e1a')
plt.close()
print("✓ Figure 2 saved: statistics")

# ── FIGURE 3: Chokepoint transit timeline ─────────────────────────────────────
fig, ax = plt.subplots(figsize=(16, 6), facecolor='#0a0e1a')
ax.set_facecolor('#111827')
fig.suptitle('Danish Straits Daily Transit Count — Shadow Fleet 2025',
             fontsize=15, color='white', fontweight='bold')

# Count vessels per day passing through Øresund or Great Belt
straits = df[df['zone'].isin(['Øresund', 'Great Belt'])].copy()
straits['date'] = straits['timestamp'].dt.date
daily = straits.groupby(['date','zone'])['mmsi'].nunique().unstack(fill_value=0)

# Rolling 7-day average
if 'Øresund' in daily.columns:
    daily['total'] = daily.sum(axis=1)
    ax.fill_between(pd.to_datetime(daily.index), daily['total'].rolling(7, min_periods=1).mean(),
                    alpha=0.25, color='#00d4ff')
    ax.plot(pd.to_datetime(daily.index), daily['total'].rolling(7, min_periods=1).mean(),
            color='#00d4ff', linewidth=2, label='7-day rolling avg (total)')
    if 'Øresund' in daily.columns:
        ax.plot(pd.to_datetime(daily.index), daily['Øresund'].rolling(7, min_periods=1).mean(),
                color='#00d4ff', linewidth=1, linestyle='--', alpha=0.6, label='Øresund')
    if 'Great Belt' in daily.columns:
        ax.plot(pd.to_datetime(daily.index), daily['Great Belt'].rolling(7, min_periods=1).mean(),
                color='#ff9f00', linewidth=1, linestyle='--', alpha=0.6, label='Great Belt')

# Reference line: 2.9/day from published estimates
ax.axhline(2.9, color='#ff4d6d', linewidth=1.2, linestyle=':', alpha=0.8,
           label='Published avg: 2.9 vessels/day (Wikipedia/DMA)')

ax.set_xlabel('Date', color='#aaa')
ax.set_ylabel('Unique shadow fleet vessels', color='#aaa')
ax.tick_params(colors='#aaa')
for spine in ax.spines.values():
    spine.set_color('#2a3050')
ax.grid(True, color='#2a3050', linewidth=0.5, alpha=0.7)
ax.legend(facecolor='#0d1220', labelcolor='white', edgecolor='#2a3050', fontsize=9)
plt.tight_layout()
plt.savefig('/home/claude/fig3_timeline.png', dpi=160, bbox_inches='tight',
            facecolor='#0a0e1a')
plt.close()
print("✓ Figure 3 saved: transit timeline")

# ── Summary stats ─────────────────────────────────────────────────────────────
print("\n" + "="*55)
print("SUMMARY: Shadow Fleet Baltic/North Sea Routes — 2025")
print("="*55)

total_voyages = df.drop_duplicates(['mmsi','route_type']).shape[0]
route_share = df.drop_duplicates(['mmsi','route_type']).groupby('route_type').size()
route_pct = (route_share / route_share.sum() * 100).round(1)

print(f"\nTotal vessels tracked:    {df['mmsi'].nunique()}")
print(f"Total AIS pings:          {len(df):,}")
print(f"Total voyage instances:   {total_voyages}")
print(f"\nRoute breakdown:")
for rt in ['oresund', 'great_belt', 'scotland']:
    print(f"  {route_labels[rt]:<30} {route_pct.get(rt, 0)}%")

total_blackouts = len(blackout_lons)
print(f"\nAIS blackout events:      {total_blackouts}")
print(f"Most common blackout zone: {max(blackout_per_zone, key=blackout_per_zone.get) if blackout_per_zone else 'N/A'}")

cable_alerts = df['cable_alert'].sum()
print(f"\nCable proximity alerts:   {int(cable_alerts)}")
print(f"\nTop flags of convenience:")
for flag, n in flag_counts.sort_values(ascending=False).head(5).items():
    print(f"  {flag:<25} {n} vessel(s)")
