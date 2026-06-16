"""
Q1 2026 vessel-track density map — Danish waters (DMA).

Recreates the dashboard's "Vessel Tracks" map for Q1 2026: all detected
watchlist vessels drawn as faint individual tracks (no per-vessel legend,
~210 vessels), so the image reads as a corridor/density map. Frame is
tightened to DMA coverage (no empty Atlantic, no Dover — honest to the data).

Input (cwd): extended_transits_q1_2026.csv  (full ping-level file)
Optional:    ne_coastline.geojson (auto-downloaded if absent)
Output:      vessel_tracks_q1_2026.png
"""
import json, os, urllib.request
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

# DMA-honest frame: Skagerrak entrance across to the Gulf of Finland approach
LON = (7.0, 30.0)
LAT = (53.2, 60.5)

CHOKEPOINTS = {
    'Skagen':     (10.6, 57.72),
    'Kattegat':   (11.3, 56.95),
    'Great Belt': (11.0, 55.35),
    'Øresund':    (12.7, 55.85),
    'Bornholm':   (15.0, 55.15),
    'Ust-Luga':   (28.4, 59.65),
}

print("Loading tracks...")
df = pd.read_csv('extended_transits_q1_2026.csv', low_memory=False)
df['MMSI'] = df['MMSI'].astype(str).str.strip()
df['Latitude']  = pd.to_numeric(df['Latitude'],  errors='coerce')
df['Longitude'] = pd.to_numeric(df['Longitude'], errors='coerce')
df['ts'] = pd.to_datetime(df['Timestamp'], format='%d/%m/%Y %H:%M:%S', errors='coerce')
df = df.dropna(subset=['Latitude', 'Longitude', 'ts'])
df = df[df['Latitude'].between(*LAT) & df['Longitude'].between(*LON)]
print(f"{len(df):,} pings · {df['MMSI'].nunique()} vessels in frame")

# coastline
if not os.path.exists('ne_coastline.geojson'):
    print("Downloading coastline...")
    urllib.request.urlretrieve(
        'https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_10m_coastline.geojson',
        'ne_coastline.geojson')
coast = json.load(open('ne_coastline.geojson'))

def segments(g, max_deg=0.6, max_hours=8):
    """Break a track on large spatial/temporal gaps so sparse pings don't
    draw lines across land or jump between disjoint transits."""
    g = g.sort_values('ts').reset_index(drop=True)
    d = np.hypot(g['Longitude'].diff(), g['Latitude'].diff())
    dt = g['ts'].diff().dt.total_seconds() / 3600
    brk = (d > max_deg) | (dt > max_hours)
    return [s for _, s in g.groupby(brk.cumsum()) if len(s) > 1]

fig, ax = plt.subplots(figsize=(20, 12), facecolor='#0d1520')
ax.set_facecolor('#16314d')                       # sea

# land fill (rough polygons from coastline bbox clip is overkill — use sea bg + coast lines)
for feat in coast['features']:
    geom = feat['geometry']
    lines = [geom['coordinates']] if geom['type'] == 'LineString' else geom['coordinates']
    for line in lines:
        a = np.asarray(line)
        if a[:,0].max() < LON[0]-3 or a[:,0].min() > LON[1]+3: continue
        if a[:,1].max() < LAT[0]-3 or a[:,1].min() > LAT[1]+3: continue
        ax.plot(a[:,0], a[:,1], color='#3a4f63', linewidth=0.7, zorder=2)

# faint per-vessel tracks — colour by zone family for subtle structure, low alpha
print("Drawing tracks...")
for mmsi, g in df.groupby('MMSI'):
    for seg in segments(g):
        ax.plot(seg['Longitude'], seg['Latitude'],
                color='#5ba3e8', alpha=0.10, linewidth=0.6, zorder=3,
                solid_capstyle='round')

# chokepoint labels
for name, (lon, lat) in CHOKEPOINTS.items():
    if not (LON[0] <= lon <= LON[1] and LAT[0] <= lat <= LAT[1]):
        continue
    ax.annotate(name, (lon, lat), color='#7ec8ff', fontsize=11, fontweight='bold',
                ha='center', va='center', zorder=6,
                bbox=dict(boxstyle='round,pad=0.3', facecolor='#0d1520',
                          edgecolor='#5ba3e8', linewidth=1.2, alpha=0.92))

ax.set_xlim(*LON); ax.set_ylim(*LAT)
ax.set_aspect(1.0 / np.cos(np.radians(57)))
ax.set_title(f'Shadow fleet vessel tracks — Danish waters, Q1 2026\n'
             f'Source: Danish Maritime Authority AIS · GUR watchlist v2 · '
             f'n={df["MMSI"].nunique()} vessels · {len(df)/1e6:.1f}M pings',
             color='white', fontsize=15, pad=14)
ax.set_xlabel('Longitude', color='#7a9ab5', fontsize=10)
ax.set_ylabel('Latitude', color='#7a9ab5', fontsize=10)
ax.tick_params(colors='#7a9ab5', labelsize=9)
def fmt_lon(x, _): return f"{abs(x):.0f}°{'E' if x>=0 else 'W'}"
def fmt_lat(y, _): return f"{y:.0f}°N"
ax.xaxis.set_major_formatter(plt.FuncFormatter(fmt_lon))
ax.yaxis.set_major_formatter(plt.FuncFormatter(fmt_lat))
for s in ax.spines.values(): s.set_color('#2a3050')
ax.grid(True, color='#1f3a52', linewidth=0.4, alpha=0.6)

# coverage caveat, bottom-left
ax.text(0.012, 0.018,
        'Coverage: DMA terrestrial AIS (Danish waters). Tracks fade west of Skagen\n'
        'and into the eastern Baltic at the limits of receiver range.',
        transform=ax.transAxes, color='#8aa', fontsize=8.5, va='bottom',
        bbox=dict(boxstyle='round,pad=0.4', facecolor='#0d1520', edgecolor='#2a3050', alpha=0.85))

plt.savefig('vessel_tracks_q1_2026.png', dpi=150, bbox_inches='tight', facecolor='#0d1520')
print("Saved vessel_tracks_q1_2026.png")
