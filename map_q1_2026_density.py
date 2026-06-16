"""
Q1 2026 ping-density heatmap — Danish waters (DMA).

Replaces the faint-line track map with a 2D log-density hexbin of all
watchlist AIS pings. Corridors render by traffic intensity; no per-vessel
lines means no gap-jump artifacts and no legend. Frame tightened to actual
DMA coverage.

Input (cwd): extended_transits_q1_2026.csv
Optional:    ne_coastline.geojson (auto-downloaded)
Output:      vessel_density_q1_2026.png
"""
import json, os, urllib.request
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

# Tight frame on real DMA traffic (origin ports east of ~16E are out of range)
LON = (8.0, 16.5)
LAT = (54.0, 58.6)

CHOKEPOINTS = {
    'Skagen':     (10.55, 57.73),
    'Kattegat':   (11.30, 56.95),
    'Great Belt': (10.95, 55.35),
    'Øresund':    (12.70, 55.95),
    'Bornholm':   (15.00, 55.10),
}

import os as _os
SRC = 'tracks_q1_2026.csv' if _os.path.exists('tracks_q1_2026.csv') else 'extended_transits_q1_2026.csv'
print(f"Loading {SRC}...")
df = pd.read_csv(SRC, low_memory=False,
                 usecols=lambda c: c in ('Latitude','Longitude','SOG'))
df['Latitude']  = pd.to_numeric(df['Latitude'],  errors='coerce')
df['Longitude'] = pd.to_numeric(df['Longitude'], errors='coerce')
df = df.dropna(subset=['Latitude','Longitude'])
df = df[df['Latitude'].between(*LAT) & df['Longitude'].between(*LON)]
print(f"{len(df):,} pings in frame")

if not os.path.exists('ne_coastline.geojson'):
    print("Downloading coastline...")
    urllib.request.urlretrieve(
        'https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_10m_coastline.geojson',
        'ne_coastline.geojson')
coast = json.load(open('ne_coastline.geojson'))

# dark-navy -> blue -> cyan -> white ramp (on-brand for the dashboard)
cmap = LinearSegmentedColormap.from_list('shadow',
    ['#0d1520', '#15324f', '#1d5a8c', '#2a7fd4', '#5ba3e8', '#9ed6ff', '#ffffff'])

fig, ax = plt.subplots(figsize=(18, 11), facecolor='#0d1520')
ax.set_facecolor('#0d1520')

aspect = 1.0 / np.cos(np.radians(56.3))

# hexbin density, log-scaled (chokepoints are orders of magnitude denser)
hb = ax.hexbin(df['Longitude'], df['Latitude'], gridsize=340, bins='log',
               cmap=cmap, mincnt=1, linewidths=0, zorder=2,
               extent=(LON[0], LON[1], LAT[0], LAT[1]))

# coastline on top, subtle
for feat in coast['features']:
    g = feat['geometry']
    lines = [g['coordinates']] if g['type'] == 'LineString' else g['coordinates']
    for line in lines:
        a = np.asarray(line)
        if a[:,0].max() < LON[0]-2 or a[:,0].min() > LON[1]+2: continue
        if a[:,1].max() < LAT[0]-2 or a[:,1].min() > LAT[1]+2: continue
        ax.plot(a[:,0], a[:,1], color='#46586f', linewidth=0.8, zorder=3, alpha=0.9)

for name, (lon, lat) in CHOKEPOINTS.items():
    ax.annotate(name, (lon, lat), color='#cfeaff', fontsize=11.5, fontweight='bold',
                ha='center', va='center', zorder=5,
                bbox=dict(boxstyle='round,pad=0.3', facecolor='#0d1520',
                          edgecolor='#5ba3e8', linewidth=1.2, alpha=0.9))

ax.set_xlim(*LON); ax.set_ylim(*LAT); ax.set_aspect(aspect)
ax.set_title('Shadow fleet AIS density — Danish waters, Q1 2026\n'
             f'Source: Danish Maritime Authority AIS · GUR watchlist v2 · '
             f'{len(df)/1e6:.1f}M pings · log-scaled traffic intensity',
             color='white', fontsize=15, pad=14)
ax.set_xlabel('Longitude', color='#7a9ab5'); ax.set_ylabel('Latitude', color='#7a9ab5')
ax.tick_params(colors='#7a9ab5', labelsize=9)
ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x,_: f"{abs(x):.0f}°{'E' if x>=0 else 'W'}"))
ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda y,_: f"{y:.0f}°N"))
for s in ax.spines.values(): s.set_color('#2a3050')

cb = fig.colorbar(hb, ax=ax, fraction=0.025, pad=0.01)
cb.set_label('AIS pings per cell (log)', color='#9ab', fontsize=9)
cb.ax.yaxis.set_tick_params(color='#7a9ab5')
plt.setp(plt.getp(cb.ax,'yticklabels'), color='#7a9ab5')
cb.outline.set_edgecolor('#2a3050')

ax.text(0.012, 0.022,
        'Coverage: DMA terrestrial AIS (Danish waters only). Intensity reflects ping count,\n'
        'so loitering/anchorage zones (notably Skagen) read brighter than transit speed alone implies.',
        transform=ax.transAxes, color='#8aa', fontsize=8.5, va='bottom',
        bbox=dict(boxstyle='round,pad=0.4', facecolor='#0d1520', edgecolor='#2a3050', alpha=0.85))

plt.savefig('vessel_density_q1_2026.png', dpi=150, bbox_inches='tight', facecolor='#0d1520')
print("Saved vessel_density_q1_2026.png")
