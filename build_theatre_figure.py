"""Baltic theatre — 3-panel physical-geography figure backing the analytical passage."""
import json, math, os, urllib.request
import numpy as np, rasterio
from rasterio.warp import transform_bounds
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, BoundaryNorm
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

LON=(9.0,30.5); LAT=(53.5,60.9)

# coastline
if not os.path.exists('ne_coastline.geojson'):
    urllib.request.urlretrieve('https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_10m_coastline.geojson','ne_coastline.geojson')
coast=json.load(open('ne_coastline.geojson'))
def draw_coast(ax,col='#5a6e88',lw=0.6):
    for f in coast['features']:
        g=f['geometry']; lines=[g['coordinates']] if g['type']=='LineString' else g['coordinates']
        for ln in lines:
            a=np.asarray(ln)
            if a[:,0].max()<LON[0]-2 or a[:,0].min()>LON[1]+2: continue
            if a[:,1].max()<LAT[0]-2 or a[:,1].min()>LAT[1]+2: continue
            ax.plot(a[:,0],a[:,1],color=col,lw=lw,zorder=4)

# bathymetry
with rasterio.open('baltic_depth_small.tif') as r:
    dep=r.read(1).astype(float); dep[dep==r.nodata]=np.nan
    b=r.bounds
    west,south,east,north=transform_bounds(r.crs,'EPSG:4326',b.left,b.bottom,b.right,b.top) if r.crs and r.crs.to_epsg()!=4326 else (b.left,b.bottom,b.right,b.top)
depth=np.where(dep<0,-dep,np.nan)   # positive metres below sea level; land->nan
ext=[west,east,south,north]; asp=1/np.cos(np.radians(57))

# chokepoints
CHOKE={'Danish Straits':(11.0,55.8),'Kadet Trench':(12.7,54.6),'Bornholm approaches':(15.3,55.1),
       'Gulf of Finland\n(Estlink / data cables)':(26.0,59.8),'Skagerrak\napproach':(9.6,57.9)}
# schematic cable/pipeline corridors (same as incident map, approximate)
CABLES=[((24.5,59.49),(21.9,59.40)),((26.0,60.18),(26.6,59.40)),((25.0,60.00),(12.1,54.10)),
        ((18.3,57.20),(21.0,55.70)),((18.6,57.30),(21.0,57.05))]
# schematic average winter max ice extent (indicative southern boundary of routine ice)
ICE_LINE=[(19.0,60.9),(19.3,60.0),(20.5,59.6),(23.0,59.5),(26.0,59.6),(28.5,59.8),(30.0,60.0)]
ICE_BOTHNIA=[(17.0,60.9),(17.5,60.4),(19.0,60.2),(19.3,60.0)]

fig,axes=plt.subplots(1,3,figsize=(27,9),facecolor='#0d1520')
for ax in axes:
    ax.set_facecolor('#0d1520'); ax.set_xlim(*LON); ax.set_ylim(*LAT); ax.set_aspect(asp)
    ax.tick_params(colors='#7a9ab5',labelsize=8)
    for s in ax.spines.values(): s.set_color('#2a3050')
    ax.set_xlabel('Longitude',color='#7a9ab5',fontsize=8)
axes[0].set_ylabel('Latitude',color='#7a9ab5',fontsize=8)

# ---- Panel 1: graded depth + 50m anchor-reach + cables + chokepoints ----
ax=axes[0]
cmap=LinearSegmentedColormap.from_list('depth',['#bfe6ff','#5ba3e8','#2a5f9e','#163a66','#0d2138'])
bounds=[0,10,20,30,50,75,100,150,300,800]
norm=BoundaryNorm(bounds,cmap.N)
ax.imshow(depth,extent=ext,origin='upper',cmap=cmap,norm=norm,aspect=asp,zorder=2)
# 50m anchor-reach contour emphasised
from matplotlib import colors as mcols
shelf=np.where(depth<=50,1,np.nan)
ax.contour(np.linspace(west,east,depth.shape[1]),np.linspace(north,south,depth.shape[0]),
           depth,levels=[50],colors=['#ffd24d'],linewidths=1.4,zorder=5)
draw_coast(ax)
for (p1,p2) in CABLES: ax.plot([p1[0],p2[0]],[p1[1],p2[1]],color='#ff5a5a',lw=1.2,alpha=0.7,zorder=6)
for name,(lon,lat) in CHOKE.items():
    ax.annotate(name,(lon,lat),color='white',fontsize=8,fontweight='bold',ha='center',va='center',zorder=8,
                bbox=dict(boxstyle='round,pad=0.25',facecolor='#0d1520',edgecolor='#7ec8ff',lw=1,alpha=0.9))
ax.set_title('Bathymetry & anchor reach\nWater depth (m); yellow line = 50 m anchor-reach limit; red = cable/pipeline corridors',
             color='white',fontsize=10.5,pad=8)
ax.legend(handles=[Line2D([0],[0],color='#ffd24d',lw=2,label='50 m depth contour'),
                   Line2D([0],[0],color='#ff5a5a',lw=2,label='Cable / pipeline (schematic)')],
          loc='upper right',fontsize=7.5,facecolor='#0d1220',labelcolor='white',edgecolor='#2a3050')

# ---- Panel 2: chokepoint geography ----
ax=axes[1]
draw_coast(ax,'#46586f',0.7)
ax.imshow(np.where(np.isfinite(depth),1.0,np.nan),extent=ext,origin='upper',cmap=mcols.ListedColormap(['#16314d']),aspect=asp,zorder=1)
FOCUS={'Danish Straits\n(1857 Copenhagen Convention regime)':(11.0,55.7,'#ffd24d'),
       'Kadet Trench':(12.6,54.55,'#ff9a3c'),
       'Bornholm approaches':(15.6,55.0,'#ff5a5a'),
       'Gulf of Finland\nEstlink + data-cable corridor':(25.5,59.7,'#7ec8ff')}
for name,(lon,lat,col) in FOCUS.items():
    ax.scatter([lon],[lat],s=260,facecolor='none',edgecolor=col,linewidths=2.2,zorder=6)
    ax.annotate(name,(lon,lat),xytext=(lon,lat-0.7),color='white',fontsize=8,fontweight='bold',
                ha='center',va='top',zorder=8,
                bbox=dict(boxstyle='round,pad=0.25',facecolor='#0d1520',edgecolor=col,lw=1,alpha=0.92))
ax.set_title('Monitoring focus points\nNatural chokepoints where shadow-fleet activity clusters',
             color='white',fontsize=10.5,pad=8)

# ---- Panel 3: environmental constraint (ice) ----
ax=axes[2]
draw_coast(ax,'#46586f',0.7)
ax.imshow(np.where(np.isfinite(depth),1.0,np.nan),extent=ext,origin='upper',cmap=mcols.ListedColormap(['#16314d']),aspect=asp,zorder=1)
# routine winter ice zone: polygon north of the indicative line, clipped to sea
il=np.array(ICE_LINE)
ax.plot(il[:,0],il[:,1],color='#bfe6ff',lw=1.8,ls='--',zorder=6)
# shade only the area north of the line (Gulf of Finland east + Bothnia north) over the sea mask
from matplotlib.path import Path as MPath
import matplotlib.patches as mpatches
poly=list(ICE_LINE)+[(30.5,60.9),(9.0,60.9)]
icepatch=mpatches.Polygon(poly,closed=True,facecolor='#bfe6ff',alpha=0.14,edgecolor='none',zorder=2)
ax.add_patch(icepatch)
# overlay the sea-only tint again ON TOP so ice shade shows only over water
ax.imshow(np.where(np.isfinite(depth),np.nan,np.nan),extent=ext,origin='upper',aspect=asp,zorder=3)
ax.annotate('Routine winter sea ice\n(Gulf of Bothnia, Gulf of Finland;\nmax extent reaches Baltic Proper in severe years)',
            (24,60.4),color='#bfe6ff',fontsize=8,ha='center',va='center',zorder=8,
            bbox=dict(boxstyle='round,pad=0.3',facecolor='#0d1520',edgecolor='#bfe6ff',lw=1,alpha=0.9))
ax.annotate('Short, steep wind-sea · prolonged winter darkness\nlow-salinity, acoustically awkward water (degrades passive sonar)',
            (16,54.2),color='#9ab',fontsize=8,ha='center',va='center',zorder=8,
            bbox=dict(boxstyle='round,pad=0.3',facecolor='#0d1520',edgecolor='#2a3050',lw=1,alpha=0.9))
ax.set_title('Environmental constraints on persistent operations\nIce, darkness, sea-state and acoustics shape any counter-USV design',
             color='white',fontsize=10.5,pad=8)
ax.legend(handles=[Line2D([0],[0],color='#bfe6ff',lw=2,ls='--',label='Indicative average winter ice limit')],
          loc='lower right',fontsize=7.5,facecolor='#0d1220',labelcolor='white',edgecolor='#2a3050')

fig.suptitle('Baltic Sea — physical theatre of shadow-fleet and seabed-infrastructure threat',color='white',fontsize=16,y=0.98)
fig.text(0.5,0.02,'Bathymetry: EMODnet Bathymetry (EMODnet __mean DTM). Coastline: Natural Earth. Cable corridors & ice limit are schematic/indicative, '
         'compiled from public sources — not surveyed. ~58% of sea area in frame is <50 m (anchor-reachable).',
         color='#7a8ba0',fontsize=8,ha='center')
plt.savefig('baltic_theatre.png',dpi=140,bbox_inches='tight',facecolor='#0d1520')
print("Saved baltic_theatre.png")
