"""
Baltic theatre analysis — GUR shadow-fleet density vs. all-tanker baseline.

1. Downloads EMODnet Human Activities tanker vessel-density (annual avg,
   ship-hours/km^2) for the Baltic via WCS — the ALL-tanker baseline.
2. Builds GUR-watchlist ping density from tracks_q1_2026.csv on the SAME grid.
3. Normalises both to their own max and computes a log-ratio difference:
     warm  = watchlist over-represented vs. normal tanker traffic
     cool  = normal tanker lanes the watchlist under-uses
   Renders three panels: baseline, watchlist, difference.

Requires: tracks_q1_2026.csv, rasterio, matplotlib, numpy.
  pip install rasterio --break-system-packages
Output: theatre_density_diff.png  (+ saves the EMODnet GeoTIFF locally)
"""
import math, os
import numpy as np
import pandas as pd
import rasterio
from rasterio.warp import transform_bounds
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm, TwoSlopeNorm

LON=(9.0,30.5); LAT=(53.5,60.9)
TIF='emodnet_tanker_baltic_avg.tif'

def merc(lon,lat):
    lon=np.asarray(lon,dtype=float); lat=np.asarray(lat,dtype=float)
    x=lon*20037508.34/180
    y=np.log(np.tan((90+lat)*np.pi/360))/(np.pi/180)*20037508.34/180
    return (x,y)

if not os.path.exists(TIF):
    import urllib.request
    x0,y0=merc(LON[0],LAT[0]); x1,y1=merc(LON[1],LAT[1])
    url=("https://ows.emodnet-humanactivities.eu/wcs?service=WCS&version=2.0.1"
         "&request=GetCoverage&coverageId=emodnet__vesseldensity_10avg"
         f"&format=image/tiff&subset=X({x0},{x1})&subset=Y({y0},{y1})")
    print("Downloading EMODnet tanker density (all-tanker baseline)...")
    urllib.request.urlretrieve(url, TIF)

with rasterio.open(TIF) as r:
    base=r.read(1).astype(float); nod=r.nodata
    base[base==nod]=np.nan; base[base<0]=np.nan
    H,W=base.shape; b=r.bounds; crs=r.crs
    west,south,east,north=transform_bounds(crs,'EPSG:4326',b.left,b.bottom,b.right,b.top)
    # grid edges in mercator for binning the watchlist pings
    xs=np.linspace(b.left,b.right,W+1); ys=np.linspace(b.top,b.bottom,H+1)

# watchlist density on the SAME grid
print("Building watchlist density from tracks_q1_2026.csv...")
df=pd.read_csv('tracks_q1_2026.csv',low_memory=False,usecols=['Latitude','Longitude'])
df['Latitude']=pd.to_numeric(df['Latitude'],errors='coerce')
df['Longitude']=pd.to_numeric(df['Longitude'],errors='coerce')
df=df.dropna()
mx,my=merc(df['Longitude'].values,df['Latitude'].values)
wl,_,_=np.histogram2d(my,mx,bins=[ys[::-1],xs])   # ys descending -> flip
wl=wl[::-1]                                        # align to raster orientation
wl=wl.astype(float); wl[wl==0]=np.nan

# Restrict to the DMA-covered footprint: only cells where the watchlist has
# data are comparable (elsewhere watchlist is absent for coverage, not behaviour).
footprint = np.isfinite(wl) & (wl > 0)
base_f = np.where(footprint, base, np.nan)
wl_f   = np.where(footprint, wl,   np.nan)
# Compare like-for-like: each layer as SHARE of its own total within the footprint.
base_share = base_f / np.nansum(base_f)
wl_share   = wl_f   / np.nansum(wl_f)
both = footprint & np.isfinite(base_share) & (base_share > 0)
ratio = np.full(base.shape, np.nan)
ratio[both] = np.log10(wl_share[both] / base_share[both])
# also clip the baseline panel to the footprint so all three panels share extent
base = base_f

ext=[west,east,south,north]; asp=1/np.cos(np.radians(57))
fig,axes=plt.subplots(1,3,figsize=(26,9),facecolor='#0d1520')
for ax in axes:
    ax.set_facecolor('#0d1520'); ax.tick_params(colors='#7a9ab5',labelsize=8)
    for s in ax.spines.values(): s.set_color('#2a3050')

im0=axes[0].imshow(base,extent=ext,origin='upper',cmap='inferno',
    norm=LogNorm(vmin=0.1,vmax=np.nanpercentile(base,99.5)),aspect=asp)
axes[0].set_title('All tankers (EMODnet baseline)\nship-hours/km²/yr',color='white',fontsize=11)
fig.colorbar(im0,ax=axes[0],fraction=0.04,pad=0.01)

im1=axes[1].imshow(wl,extent=ext,origin='upper',cmap='viridis',
    norm=LogNorm(vmin=1,vmax=np.nanpercentile(wl,99.5)),aspect=asp)
axes[1].set_title('GUR watchlist (Q1 2026 DMA)\nAIS pings per cell',color='white',fontsize=11)
fig.colorbar(im1,ax=axes[1],fraction=0.04,pad=0.01)

im2=axes[2].imshow(ratio,extent=ext,origin='upper',cmap='RdBu_r',
    norm=TwoSlopeNorm(vcenter=0,vmin=-2,vmax=2),aspect=asp)
axes[2].set_title('Difference (log ratio)\nred = watchlist over-represented vs normal tankers',color='white',fontsize=11)
fig.colorbar(im2,ax=axes[2],fraction=0.04,pad=0.01)

fig.suptitle('Baltic theatre — shadow-fleet density vs. all-tanker baseline',color='white',fontsize=15)
for ax in axes: ax.set_xlabel('Lon',color='#7a9ab5')
axes[0].set_ylabel('Lat',color='#7a9ab5')
plt.savefig('theatre_density_diff.png',dpi=140,bbox_inches='tight',facecolor='#0d1520')
print("Saved theatre_density_diff.png")
