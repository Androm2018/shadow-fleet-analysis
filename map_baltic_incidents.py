"""
Baltic Sea critical-infrastructure incident map (Sep 2022 -> Dec 2025).

Dark cartographic style matching the AIS density map. Shows:
  - damaged cables / pipelines as lines (approximate routes between endpoints)
  - incident points, dated, with suspect vessel and attribution status
NOT AIS-derived. Cable routes are schematic straight-line approximations
between published landing-point regions; incident coordinates are approximate
area centroids from public investigation reporting.
"""
import json, os, urllib.request
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

LON = (9.0, 30.5)
LAT = (53.3, 60.9)

# ── Damaged infrastructure: (name, (lon1,lat1)->(lon2,lat2) endpoints, kind) ──
# Endpoints are approximate landing regions; routes are schematic.
CABLES = [
    ('Balticconnector (gas)',        (24.5,59.49),(21.9,59.40),'pipe'),   # Inkoo FI - Paldiski EE
    ('Estlink 2 (power)',            (26.0,60.18),(26.6,59.40),'power'),  # Anttila FI - Püssi EE
    ('EE-S1 / FEC (FI–EE data)',     (24.9,59.55),(24.7,59.45),'data'),
    ('C-Lion1 (FI–DE data)',         (25.0,60.00),(12.1,54.10),'data'),   # Helsinki - Rostock
    ('BCS East-West (SE–LT data)',   (18.3,57.20),(21.0,55.70),'data'),   # Gotland - Lithuania
    ('Sweden–Latvia (Gotland) data', (18.6,57.30),(21.0,57.05),'data'),   # Gotland - Ventspils LV
    ('Elisa (FI–EE data)',           (25.0,59.90),(24.8,59.45),'data'),
]
KIND_STYLE = {'pipe':('#e8a020','-'),'power':('#d44040','-'),'data':('#5ba3e8','-')}

# ── Incidents: label, lon, lat, date, vessel, status ──
# status: confirmed (vessel id'd + anchor drag), investigated (contested/dropped),
#         context (different MO / earlier)
INCIDENTS = [
    ("Balticconnector + FI–EE/SE cables", 23.2,59.55,"8 Oct 2023","Newnew Polar Bear","confirmed"),
    ("C-Lion1 (FI–DE)",                   16.5,55.40,"18 Nov 2024","Yi Peng 3","confirmed"),
    ("BCS East-West (SE–LT)",             19.3,56.30,"17 Nov 2024","Yi Peng 3","confirmed"),
    ("Estlink 2 + 4 telecom cables",      26.3,59.95,"25 Dec 2024","Eagle S","investigated"),
    ("Sweden–Latvia (Gotland)",           19.8,57.10,"26 Jan 2025","Vezhen / Silver Dania","investigated"),
    ("C-Lion1 (2nd, FI–DE)",              15.0,55.10,"~26 Jan 2025","detected Feb 2025","investigated"),
    ("Latvia RTV fibre",                  20.6,57.00,"Jan 2025","—","investigated"),
    ("Elisa (FI–EE)",                     25.6,59.70,"31 Dec 2025","Fitburg","confirmed"),
    ("Nord Stream 1 & 2",                 15.5,55.00,"26 Sep 2022","— (explosives)","context"),
]
STATUS_STYLE = {
    'confirmed':   ('#d44040','Confirmed vessel + anchor-drag'),
    'investigated':('#e8a020','Investigated / attribution dropped or contested'),
    'context':     ('#6a7a90','Earlier event, different method'),
}

if not os.path.exists('ne_coastline.geojson'):
    urllib.request.urlretrieve(
        'https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_10m_coastline.geojson',
        'ne_coastline.geojson')
coast=json.load(open('ne_coastline.geojson'))

fig,ax=plt.subplots(figsize=(19,11),facecolor='#0d1520')
ax.set_facecolor('#10243a')
for feat in coast['features']:
    g=feat['geometry']; lines=[g['coordinates']] if g['type']=='LineString' else g['coordinates']
    for line in lines:
        a=np.asarray(line)
        if a[:,0].max()<LON[0]-3 or a[:,0].min()>LON[1]+3: continue
        if a[:,1].max()<LAT[0]-3 or a[:,1].min()>LAT[1]+3: continue
        ax.plot(a[:,0],a[:,1],color='#46586f',linewidth=0.8,zorder=3)

# cables/pipelines as schematic lines
for name,p1,p2,kind in CABLES:
    col,ls=KIND_STYLE[kind]
    ax.plot([p1[0],p2[0]],[p1[1],p2[1]],color=col,ls=ls,lw=1.4,alpha=0.55,zorder=4)

# incident markers with explicit non-colliding label anchors + leaders
LABELPOS={
    "Balticconnector + FI–EE/SE cables":(20.4,60.4,'right'),
    "C-Lion1 (FI–DE)":(13.2,56.6,'right'),
    "BCS East-West (SE–LT)":(16.3,55.9,'right'),
    "Estlink 2 + 4 telecom cables":(27.8,58.6,'left'),
    "Sweden–Latvia (Gotland)":(17.9,58.2,'right'),
    "C-Lion1 (2nd, FI–DE)":(9.6,55.9,'left'),
    "Latvia RTV fibre":(22.6,56.4,'left'),
    "Elisa (FI–EE)":(28.2,60.3,'left'),
    "Nord Stream 1 & 2":(9.6,54.4,'left'),
}
for label,lon,lat,date,vessel,status in INCIDENTS:
    col=STATUS_STYLE[status][0]
    ms=300 if status=='confirmed' else (220 if status=='investigated' else 150)
    mk='o' if status!='context' else 'X'
    ax.scatter([lon],[lat],s=ms,c=col,edgecolors='white',linewidths=1.3,marker=mk,zorder=6,alpha=0.95)
    lx,ly,ha=LABELPOS[label]
    txt=f"{label}\n{date}"+(f"\n{vessel}" if vessel not in ('—','— (explosives)') else (f"\n{vessel}" if vessel=='— (explosives)' else ''))
    ax.annotate(txt,(lon,lat),xytext=(lx,ly),zorder=7,color='white',fontsize=8,
                fontweight='bold',va='center',ha=ha,
                arrowprops=dict(arrowstyle='-',color=col,lw=0.9,alpha=0.8,shrinkA=3,shrinkB=8),
                bbox=dict(boxstyle='round,pad=0.3',facecolor='#0d1520',edgecolor=col,lw=1.0,alpha=0.95))

# legends: incident status + infrastructure type
status_h=[Line2D([0],[0],marker='o',color='none',markerfacecolor=STATUS_STYLE[k][0],
          markeredgecolor='white',markersize=11,label=STATUS_STYLE[k][1]) for k in STATUS_STYLE]
infra_h=[Line2D([0],[0],color=KIND_STYLE[k][0],lw=2,label=lbl) for k,lbl in
         [('pipe','Gas pipeline'),('power','Power interconnector'),('data','Telecom/data cable')]]
leg1=ax.legend(handles=status_h,loc='upper left',fontsize=8.5,facecolor='#0d1220',
               labelcolor='white',edgecolor='#2a3050',framealpha=0.92,title='Incident attribution',title_fontsize=8.5)
ax.add_artist(leg1)
ax.legend(handles=infra_h,loc='lower right',fontsize=8.5,facecolor='#0d1220',
          labelcolor='white',edgecolor='#2a3050',framealpha=0.92,title='Infrastructure (schematic routes)',title_fontsize=8.5)

ax.set_xlim(*LON); ax.set_ylim(*LAT); ax.set_aspect(1.0/np.cos(np.radians(57)))
ax.set_title('Baltic Sea critical-infrastructure incidents — Sep 2022 to Dec 2025\n'
             'Damaged cables & pipelines (schematic) with anchor-drag incidents attributed to commercial / shadow-fleet vessels',
             color='white',fontsize=14,pad=14)
ax.set_xlabel('Longitude',color='#7a9ab5'); ax.set_ylabel('Latitude',color='#7a9ab5')
ax.tick_params(colors='#7a9ab5',labelsize=9)
ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x,_:f"{abs(x):.0f}°{'E' if x>=0 else 'W'}"))
ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda y,_:f"{y:.0f}°N"))
for s in ax.spines.values(): s.set_color('#2a3050')

ax.text(0.012,0.30,
        'Cable/pipeline routes are schematic straight-line approximations between published landing regions, not surveyed paths.\n'
        'Incident coordinates are approximate area centroids from public reporting (not AIS-derived). At least 11 cable/pipeline\n'
        'damage events are counted in the region since Oct 2023; principal documented events shown. Eagle S case dismissed by a\n'
        'Finnish court Oct 2025 (intent not proven); Vezhen/Silver Dania suspicions dropped — hence "investigated", not confirmed.',
        transform=ax.transAxes,color='#8aa',fontsize=7.5,va='top',ha='left',
        bbox=dict(boxstyle='round,pad=0.4',facecolor='#0d1520',edgecolor='#2a3050',alpha=0.88))

plt.savefig('baltic_incidents.png',dpi=150,bbox_inches='tight',facecolor='#0d1520')
print("Saved baltic_incidents.png")
