"""
Rebuild dashboard for readability -> shadow_fleet_dashboard_v6.html

Takes shadow_fleet_dashboard_v5.html, removes the four sections the v5
builder bolted on, and rebuilds them in v4's own design system (Syne /
JetBrains Mono, stat-card / finding / chart-panel components). Adds:
  - sticky section navigation (auto-built from h2s)
  - period badges on every section header (2025 baseline vs Q1 2026 vs live)
  - vessel index as a sortable, filterable, paginated ledger
  - back-to-top, smooth scroll, keyboard focus, reduced-motion support

Inputs in cwd: shadow_fleet_dashboard_v5.html, detected_vessels_q1_2026.csv,
gur_vessels_master.csv, vessel_thumbs/, baltic_routing_q1_2026.png,
uk_north_routing.png (optional)
"""
import base64, html, os, re
import pandas as pd

doc = open('shadow_fleet_dashboard_v5.html', encoding='utf-8').read()

def b64img(p): return base64.b64encode(open(p, 'rb').read()).decode()

# ── 1. excise the v5-era bolt-ons ───────────────────────────────────────────
start = doc.find('<section id="q1-2026-baltic">')
vi = doc.find('<section id="vessel-index">')
if start != -1 and vi != -1:
    end = doc.find('</section>', doc.find('</script>', vi)) + len('</section>')
    doc = doc[:start] + doc[end:]
    print("removed v5 bolt-on sections")
doc = re.sub(r'<p><strong>June 2026 update:</strong>.*?</p>', '', doc, flags=re.S)

# ── 2. data ─────────────────────────────────────────────────────────────────
per = pd.read_csv('detected_vessels_q1_2026.csv', dtype=str)
for c in ('pings', 'days_detected', 'sog_mean', 'sog_max'):
    per[c] = pd.to_numeric(per[c], errors='coerce')
master = pd.read_csv('gur_vessels_master.csv', dtype=str)
listed = master[master['status'] == 'listed']
new_ids = set(master.loc[master['mmsi_legacy'].isna() & (master['status'] == 'listed'), 'gur_id'])

n = len(per)
det_rate = n / len(listed) * 100
n_new = per['gur_gur_id'].isin(new_ids).sum()
strait = per[per['zones'].fillna('').str.contains('Great_Belt|Oresund')]
fast = (strait['sog_mean'] > 12).sum()

def stat(value, label, sub='', accent='--blue'):
    return (f'<div class="stat-card" style="--accent:var({accent})">'
            f'<div class="stat-value">{value}</div>'
            f'<div class="stat-label">{label}</div>'
            f'<div class="stat-sub">{sub}</div></div>')

def panel(png, alt):
    return (f'<div class="chart-panel"><div class="chart-body">'
            f'<img src="data:image/png;base64,{b64img(png)}" style="width:100%;display:block" '
            f'alt="{alt}"></div></div>')

# ── 3. rebuilt sections, in v4's vocabulary ─────────────────────────────────
sec_q1 = f"""
<section class="section" id="q1-2026">
<div class="section-header"><h2>Q1 2026 — Danish Waters <span class="pbadge">Jan–Mar 2026</span></h2>
<p class="section-desc">Re-run of the Baltic chokepoint analysis for 1 January –
31 March 2026 against the refreshed GUR watchlist (1,404 vessels; detection keyed
on the union of current and legacy MMSIs — 1,480 identifiers). Source: Danish
Maritime Authority terrestrial AIS. The 2025 sections above are the comparison
baseline.</p></div>
<div class="stats-grid">
{stat(n, 'vessels detected', f'{det_rate:.1f}% of listed fleet')}
{stat(int(n_new), 'from new listings', 'of 209 vessels added to the GUR list since 2025', '--green')}
{stat(len(strait), 'strait transitors', 'vessels using Great Belt or Øresund')}
{stat(fast, 'above 12 kn advisory', f'of {len(strait)} strait transitors (mean SOG)', '--red')}
</div>
{panel('baltic_routing_q1_2026.png', 'Q1 2026 Baltic routing analysis')}
</section>"""

sec_north = ""
if os.path.exists('uk_north_routing.png'):
    sec_north = f"""
<section class="section" id="northern-uk">
<div class="section-header"><h2>Northern UK Routing <span class="pbadge">Jan–Apr 2025</span></h2>
<p class="section-desc">Watchlist traffic rounding Scotland, from the Jan–Apr
2025 Datalastic dataset. 19 vessels used northern Scotland routes — a cohort
dominated by the Russian Arctic fleet: seven Arc7 LNG carriers account for
60.8% of northern-zone pings, running a West of Hebrides → Minch → North
Channel corridor at 14–16 kn. Two vessels transited the Pentland Firth.
Coverage caps at 61.0°N in this pull, truncating north-of-Shetland transits.</p>
</div>
{panel('uk_north_routing.png', 'Northern UK routing analysis')}
</section>"""

flags = listed['flag'].value_counts().head(6)
types = listed['vessel_type'].value_counts().head(5)
ages = pd.to_numeric(listed['build_year'], errors='coerce')
def tbl(caption, series):
    rows = ''.join(f'<tr><td>{html.escape(str(k))}</td><td class="num">{v}</td></tr>'
                   for k, v in series.items())
    return (f'<table class="wl-table"><caption>{caption}</caption>'
            f'<tbody>{rows}</tbody></table>')

sec_watch = f"""
<section class="section" id="watchlist">
<div class="section-header"><h2>Watchlist Profile <span class="pbadge">Jun 2026</span></h2>
<p class="section-desc">The Ukrainian GUR War &amp; Sanctions ship list, scraped
June 2026. Identity churn is the headline: nearly a quarter of carried-over
vessels changed MMSI since the project's original database was assembled —
detection keyed to stale identifiers silently undercounts.</p></div>
<div class="stats-grid">
{stat('1,404', 'vessels listed', 'up from 1,206 at original db build')}
{stat('+209', 'new listings', 'added to the GUR list since 2025', '--green')}
{stat('23.6%', 'changed MMSI', '282 of 1,196 carried-over vessels', '--red')}
{stat(f'{2026-ages.median():.0f} yrs', 'median age', f'median build year {ages.median():.0f}', '--amber')}
</div>
<div class="wl-tables">{tbl('Top flags', flags)}{tbl('Vessel types', types)}</div>
</section>"""

# vessel ledger
cards, missing = [], 0
for _, v in per.iterrows():
    imo = v.get('gur_imo')
    t = f"vessel_thumbs/{imo}.jpg" if pd.notna(imo) else None
    if t and os.path.exists(t):
        img = f'<img src="data:image/jpeg;base64,{b64img(t)}" loading="lazy" alt="">'
    else:
        img = '<div class="noimg">NO IMAGE</div>'; missing += 1
    name = v.get('gur_name') if pd.notna(v.get('gur_name')) else (v.get('name_ais') or 'UNKNOWN')
    zones = (v.get('zones') or '').replace('_', ' ').replace('|', ' · ')
    meta = ' · '.join(str(x) for x in [v.get('flag'), v.get('gur_vessel_type'),
        f"built {v.get('gur_build_year')}" if pd.notna(v.get('gur_build_year')) else None]
        if pd.notna(x) and x is not None)
    sogtxt = (f'{v["sog_mean"]:.1f} / {v["sog_max"]:.1f} kn' if pd.notna(v['sog_mean']) else '—')
    blob = html.escape(' '.join(str(x).lower() for x in
        [name, imo, v['MMSI'], v.get('flag'), v.get('gur_vessel_type')] if pd.notna(x)))
    cards.append(
        f'<div class="vcard" data-s="{blob}" data-pings="{int(v["pings"])}" '
        f'data-days="{int(v["days_detected"])}" data-max="{v["sog_max"] if pd.notna(v["sog_max"]) else 0}" '
        f'data-name="{html.escape(str(name))}">{img}'
        f'<div class="vname">{html.escape(str(name))}</div>'
        f'<div class="vids">IMO {imo if pd.notna(imo) else "—"} · MMSI {v["MMSI"]}</div>'
        f'<div class="vmeta">{html.escape(meta)}</div>'
        f'<div class="vrow"><span>{int(v["days_detected"])} days</span>'
        f'<span>{int(v["pings"]):,} pings</span><span>{sogtxt}</span></div>'
        f'<div class="vzones">{html.escape(zones)}</div></div>')

sec_index = f"""
<section class="section" id="vessel-index">
<div class="section-header"><h2>Vessel Index <span class="pbadge">Q1 2026</span></h2>
<p class="section-desc">Every GUR-watchlist vessel detected in Danish waters in
Q1 2026 — {n} vessels. Photos: GUR War &amp; Sanctions portal. Speed shown as
mean / max SOG while underway.</p></div>
<div class="vctrl">
<input id="vfilter" type="search" placeholder="Filter by name, IMO, MMSI, flag, type">
<select id="vsort">
<option value="pings">Sort: most active</option>
<option value="days">Sort: most days detected</option>
<option value="max">Sort: highest max speed</option>
<option value="name">Sort: name A–Z</option>
</select>
<span id="vcount" class="vcount"></span>
</div>
<div id="vgrid">{''.join(cards)}</div>
<button id="vmore" class="vmore">Show 60 more</button>
</section>"""

# ── 4. nav, badges ──────────────────────────────────────────────────────────
# insert new sections before the methodology section
mpos = doc.find('Data Sources')
hpos = doc.rfind('<h2', 0, mpos)
wrap = doc.rfind('<section', 0, hpos)
ins = wrap if wrap != -1 and hpos - wrap < 300 else hpos
doc = doc[:ins] + sec_q1 + sec_north + sec_watch + sec_index + doc[ins:]

# period badges on the 2025 sections (v4 sections keep their existing ids)
BADGES = [('Key Findings', 'Feb–Oct 2025'),
          ('Vessel Tracks', 'Mar 2025'),
          ('Daily Transit Volume', 'Feb–Oct 2025'),
          ('Vessel Speed in Danish Waters', 'Feb–Oct 2025'),
          ('Baltic Sea Routing Analysis', 'Feb–Oct 2025'),
          ('UK &amp; Irish Waters Analysis', 'Jan–Apr 2025')]
for title, badge in BADGES:
    m = re.search(r'(<h2[^>]*>\s*' + title + r')(\s*</h2>)', doc)
    if m:
        doc = (doc[:m.end(1)] + f' <span class="pbadge">{badge}</span>'
               + doc[m.end(1):])

# extend v4's own nav with the new sections
navadd = ('<a href="#northern-uk">Northern UK</a>'
          '<a href="#q1-2026">Q1 2026</a>'
          '<a href="#watchlist">Watchlist</a>'
          '<a href="#vessel-index">Vessels</a>')
doc = doc.replace('</nav>', navadd + '</nav>', 1)

extra_css = """<style>
html{scroll-behavior:smooth}
@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}}
section,h2{scroll-margin-top:70px}
.pbadge{font-family:var(--mono);font-size:10.5px;font-weight:500;letter-spacing:.06em;
 color:var(--muted);border:1px solid var(--border);border-radius:99px;
 padding:3px 10px;vertical-align:middle;margin-left:10px;white-space:nowrap}
.wl-tables{display:flex;gap:32px;flex-wrap:wrap;margin-top:8px}
.wl-table{border-collapse:collapse;min-width:260px}
.wl-table caption{font-family:var(--mono);font-size:11px;letter-spacing:.08em;
 text-transform:uppercase;color:var(--muted);text-align:left;padding-bottom:10px}
.wl-table td{border-bottom:1px solid var(--border);padding:8px 4px;font-size:14px}
.wl-table td.num{font-family:var(--mono);text-align:right;color:var(--blue-lt)}
.vctrl{display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin-bottom:20px}
.vctrl input,.vctrl select{background:var(--bg2);color:var(--text);border:1px solid var(--border);
 border-radius:6px;padding:9px 12px;font-family:var(--mono);font-size:12.5px}
.vctrl input{flex:1;min-width:220px;max-width:420px}
.vctrl :focus-visible{outline:1px solid var(--blue-lt);outline-offset:1px}
.vcount{font-family:var(--mono);font-size:11.5px;color:var(--muted)}
#vgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(225px,1fr));gap:14px}
.vcard{background:var(--bg2);border:1px solid var(--border);border-left:3px solid var(--blue);
 border-radius:0 8px 8px 0;padding:12px;display:none}
.vcard.show{display:block}
.vcard img,.vcard .noimg{width:100%;aspect-ratio:16/10;object-fit:cover;border-radius:4px;
 background:var(--bg3)}
.vcard .noimg{display:flex;align-items:center;justify-content:center;
 font-family:var(--mono);font-size:10px;letter-spacing:.1em;color:var(--muted)}
.vname{font-weight:700;font-size:14.5px;color:#fff;margin-top:10px}
.vids{font-family:var(--mono);font-size:11px;color:var(--blue-lt);margin-top:3px}
.vmeta{font-size:12px;color:var(--muted);margin-top:6px;min-height:1.2em}
.vrow{display:flex;justify-content:space-between;font-family:var(--mono);font-size:11px;
 color:var(--text);border-top:1px solid var(--border);margin-top:10px;padding-top:8px}
.vzones{font-size:11px;color:var(--muted);margin-top:6px}
.vmore{display:block;margin:24px auto 0;background:var(--bg3);color:var(--text);
 border:1px solid var(--border);border-radius:6px;padding:10px 26px;
 font-family:var(--mono);font-size:12px;cursor:pointer}
.vmore:hover{border-color:var(--blue)}
.totop{position:fixed;right:18px;bottom:18px;z-index:50;background:var(--bg3);
 color:var(--text);border:1px solid var(--border);border-radius:8px;width:38px;height:38px;
 font-size:16px;cursor:pointer;opacity:0;pointer-events:none;transition:opacity .2s}
.totop.on{opacity:1;pointer-events:auto}
@media(max-width:640px){.topnav{overflow-x:auto}.wl-tables{gap:16px}}
</style>"""
doc = doc.replace('</head>', extra_css + '</head>', 1)

js = """<button class="totop" id="totop" aria-label="Back to top">↑</button>
<script>
(function(){
var grid=document.getElementById('vgrid');if(!grid)return;
var cards=Array.prototype.slice.call(grid.children),
    filter=document.getElementById('vfilter'),
    sort=document.getElementById('vsort'),
    more=document.getElementById('vmore'),
    count=document.getElementById('vcount'),
    PAGE=60,limit=PAGE;
function key(c,k){return k==='name'?c.dataset.name:-parseFloat(c.dataset[k]||0)}
function render(){
  var q=(filter.value||'').toLowerCase(),k=sort.value;
  var vis=cards.filter(function(c){return c.dataset.s.indexOf(q)>-1});
  vis.sort(function(a,b){var x=key(a,k),y=key(b,k);return x<y?-1:x>y?1:0});
  cards.forEach(function(c){c.classList.remove('show')});
  vis.forEach(function(c,i){grid.appendChild(c);if(i<limit)c.classList.add('show')});
  count.textContent='showing '+Math.min(limit,vis.length)+' of '+vis.length;
  more.style.display=vis.length>limit?'block':'none';
}
filter.addEventListener('input',function(){limit=PAGE;render()});
sort.addEventListener('change',function(){limit=PAGE;render()});
more.addEventListener('click',function(){limit+=PAGE;render()});
render();
var tt=document.getElementById('totop');
window.addEventListener('scroll',function(){tt.classList.toggle('on',window.scrollY>900)},{passive:true});
tt.addEventListener('click',function(){window.scrollTo({top:0,behavior:'smooth'})});
})();
</script>"""
doc = doc.replace('</body>', js + '</body>', 1)

# refresh stale hero metadata
doc = doc.replace('Ukrainian GUR (1,200+ vessels)', 'Ukrainian GUR (1,404 vessels)')
doc = doc.replace('Period: Feb–Oct 2025', 'Period: Feb 2025 – Mar 2026')

# methods note (re-add, cleanly, after the Data Sources h2)
note = """<p class="section-desc"><strong>June 2026 update:</strong> watchlist
refreshed from the GUR War &amp; Sanctions portal (1,404 vessels; detection keyed
on the union of current and legacy MMSIs after finding 23.6% MMSI churn).
Q1 2026 Danish-waters run: DMA daily files, 1 Jan – 31 Mar 2026. Known caveats:
two Comoros MMSIs are reused across distinct hulls (attribution ambiguity for
SARD/ION and COMETA/VIKRAM); the GUR portal requires a browser TLS fingerprint
(curl_cffi) from cloud IPs; UK/Irish sections remain Jan–Apr 2025 pending the
Q1 2026 Datalastic run.</p>"""
mh = re.search(r'(<section id="methodology">.*?</h2>)', doc, re.S)
if mh:
    doc = doc[:mh.end()] + note + doc[mh.end():]

open('shadow_fleet_dashboard_v6.html', 'w', encoding='utf-8').write(doc)
print(f"DONE: shadow_fleet_dashboard_v6.html "
      f"({os.path.getsize('shadow_fleet_dashboard_v6.html')/1e6:.1f} MB) | "
      f"{n} vessel cards ({missing} without photo)")
