"""
Build shadow_fleet_dashboard_v5.html.

Base: shadow_fleet_dashboard_v4.html in cwd if present, otherwise the live
site (https://shadowfleet.tiiny.site/) is downloaded as the base.

Inserts before the "Data Sources & Methods" section:
  1. Q1 2026 Baltic analysis      (baltic_routing_q1_2026.png + headline stats)
  2. Northern UK routing          (uk_north_routing.png, if present)
  3. Watchlist v2 profile         (from gur_vessels_master.csv)
  4. Vessel index                 (cards from detected_vessels_q1_2026.csv
                                   + vessel_thumbs/{imo}.jpg, searchable)

Appends a watchlist-v2 note inside Data Sources & Methods.
Output: shadow_fleet_dashboard_v5.html  (single file, all assets embedded)
"""
import base64, html, os, sys
import pandas as pd

# ── base document ────────────────────────────────────────────────────────────
if os.path.exists('shadow_fleet_dashboard_v4.html'):
    doc = open('shadow_fleet_dashboard_v4.html', encoding='utf-8').read()
    print("base: local v4")
else:
    import urllib.request
    doc = urllib.request.urlopen('https://shadowfleet.tiiny.site/', timeout=60).read().decode('utf-8')
    print("base: live site")

def b64img(path):
    return base64.b64encode(open(path, 'rb').read()).decode()

# ── inputs ───────────────────────────────────────────────────────────────────
per = pd.read_csv('detected_vessels_q1_2026.csv', dtype=str)
master = pd.read_csv('gur_vessels_master.csv', dtype=str)
for c in ('pings', 'days_detected', 'sog_mean', 'sog_max'):
    per[c] = pd.to_numeric(per[c], errors='coerce')

n_vessels = len(per)
listed = master[master['status'] == 'listed']
det_rate = n_vessels / len(listed) * 100

# ── section 1: Q1 2026 Baltic ────────────────────────────────────────────────
fig_b64 = b64img('baltic_routing_q1_2026.png')
sec_q1 = f"""
<section id="q1-2026-baltic">
<h2>Q1 2026 — Danish Waters Analysis</h2>
<p><em>Updated June 2026.</em> Re-run of the Baltic chokepoint analysis for
1 January – 31 March 2026, against the refreshed GUR watchlist
(1,404 vessels; current and legacy MMSIs, 1,480 identifiers). Source: Danish
Maritime Authority terrestrial AIS. {n_vessels} watchlist vessels detected
in Danish waters this quarter ({det_rate:.1f}% of the listed fleet).
The 2025 sections above are retained as the comparison baseline.</p>
<img src="data:image/png;base64,{fig_b64}" style="width:100%" alt="Q1 2026 Baltic routing analysis">
</section>
"""

# ── section 2: northern UK (optional) ────────────────────────────────────────
sec_north = ""
if os.path.exists('uk_north_routing.png'):
    sec_north = f"""
<section id="northern-uk">
<h2>Northern UK Routing (Jan–Apr 2025)</h2>
<p>Refined zone analysis of GUR-watchlist traffic rounding Scotland, from the
Jan–Apr 2025 Datalastic dataset (212 vessels in UK/Irish waters). 19 vessels
used northern Scotland routes; the cohort is dominated by the Russian Arctic
fleet — seven Arc7 LNG carriers account for 60.8% of northern-zone pings,
running a West of Hebrides → Minch → North Channel corridor at 14–16 kn.
Two vessels transited the Pentland Firth. Coverage caps at 61.0°N in this
pull, truncating north-of-Shetland transits.</p>
<img src="data:image/png;base64,{b64img('uk_north_routing.png')}" style="width:100%" alt="Northern UK routing analysis">
</section>
"""
else:
    print("note: uk_north_routing.png not found — skipping northern UK section")

# ── section 3: watchlist profile ─────────────────────────────────────────────
flags = listed['flag'].value_counts().head(6)
types = listed['vessel_type'].value_counts().head(5)
ages = pd.to_numeric(listed['build_year'], errors='coerce')
flag_rows = ''.join(f"<tr><td>{html.escape(str(k))}</td><td>{v}</td></tr>" for k, v in flags.items())
type_rows = ''.join(f"<tr><td>{html.escape(str(k))}</td><td>{v}</td></tr>" for k, v in types.items())
sec_watch = f"""
<section id="watchlist-profile">
<h2>Watchlist Profile — GUR War &amp; Sanctions List (June 2026)</h2>
<p>The Ukrainian GUR War &amp; Sanctions ship list stood at 1,404 vessels when
scraped in June 2026, up from 1,206 when this project's original vessel
database was assembled — and 23.6% of carried-over vessels had changed MMSI
in the interim, underscoring identity churn as a core shadow-fleet evasion
behaviour. Median build year {ages.median():.0f} (median age
{2026-ages.median():.0f} years).</p>
<div style="display:flex;gap:2em;flex-wrap:wrap">
<table><caption>Top flags</caption><tr><th>Flag</th><th>Vessels</th></tr>{flag_rows}</table>
<table><caption>Vessel types</caption><tr><th>Type</th><th>Vessels</th></tr>{type_rows}</table>
</div>
</section>
"""

# ── section 4: vessel index ──────────────────────────────────────────────────
cards = []
missing_thumbs = 0
for _, v in per.iterrows():
    imo = v.get('gur_imo')
    thumb = f"vessel_thumbs/{imo}.jpg" if pd.notna(imo) else None
    if thumb and os.path.exists(thumb):
        img = f'<img src="data:image/jpeg;base64,{b64img(thumb)}" loading="lazy" alt="">'
    else:
        img = '<div class="noimg">no image</div>'
        missing_thumbs += 1
    name = v.get('gur_name') if pd.notna(v.get('gur_name')) else (v.get('name_ais') or 'UNKNOWN')
    zones = (v.get('zones') or '').replace('|', ' · ').replace('_', ' ')
    meta = ' · '.join(filter(None, [
        str(v.get('flag')) if pd.notna(v.get('flag')) else None,
        str(v.get('gur_vessel_type')) if pd.notna(v.get('gur_vessel_type')) else None,
        f"built {v.get('gur_build_year')}" if pd.notna(v.get('gur_build_year')) else None]))
    sog = (f"SOG mean {v['sog_mean']:.1f} / max {v['sog_max']:.1f} kn"
           if pd.notna(v['sog_mean']) else "")
    search_blob = html.escape(' '.join(str(x).lower() for x in
        [name, imo, v['MMSI'], v.get('flag'), v.get('gur_vessel_type')] if pd.notna(x)))
    cards.append(f"""<div class="vcard" data-s="{search_blob}">{img}
<h4>{html.escape(str(name))}</h4>
<p class="ids">IMO {imo if pd.notna(imo) else '—'} · MMSI {v['MMSI']}</p>
<p class="meta">{html.escape(meta)}</p>
<p class="stats">{int(v['days_detected'])} days · {int(v['pings']):,} pings · {sog}</p>
<p class="zones">{html.escape(zones)}</p></div>""")

sec_index = f"""
<section id="vessel-index">
<h2>Vessel Index — Q1 2026 Detections ({n_vessels} vessels)</h2>
<p>Every GUR-watchlist vessel detected in Danish waters, Q1 2026. Photos:
GUR War &amp; Sanctions portal. Sorted by AIS activity.</p>
<input id="vfilter" type="text" placeholder="Filter by name, IMO, MMSI, flag, type…"
 style="width:100%;max-width:30em;padding:.5em;margin-bottom:1em;background:#111827;color:#eee;border:1px solid #2a3050;border-radius:4px">
<div id="vgrid" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:12px">
{''.join(cards)}
</div>
<style>
.vcard{{background:#111827;border:1px solid #2a3050;border-radius:6px;padding:10px;font-size:.85em}}
.vcard img{{width:100%;border-radius:4px}}
.vcard .noimg{{width:100%;aspect-ratio:16/10;background:#1a2035;border-radius:4px;display:flex;align-items:center;justify-content:center;color:#556}}
.vcard h4{{margin:.5em 0 .2em}}
.vcard p{{margin:.15em 0;color:#9aa}}
.vcard .ids{{color:#7af;font-size:.9em}}
</style>
<script>
document.getElementById('vfilter').addEventListener('input', function() {{
  var q = this.value.toLowerCase();
  document.querySelectorAll('#vgrid .vcard').forEach(function(c) {{
    c.style.display = c.dataset.s.indexOf(q) > -1 ? '' : 'none';
  }});
}});
</script>
</section>
"""

# ── assemble ─────────────────────────────────────────────────────────────────
new_sections = sec_q1 + sec_north + sec_watch + sec_index
anchor = '<h2>Data Sources'
pos = doc.find(anchor)
if pos == -1:
    print("WARNING: methods anchor not found — appending before </body>")
    pos = doc.rfind('</body>')
    doc = doc[:pos] + new_sections + doc[pos:]
else:
    # insert before the enclosing <section>/<div> if one wraps the h2; fall back to h2
    wrap = max(doc.rfind('<section', 0, pos), doc.rfind('<div', 0, pos))
    ins = wrap if wrap != -1 and pos - wrap < 200 else pos
    doc = doc[:ins] + new_sections + doc[ins:]

methods_note = """<p><strong>June 2026 update:</strong> watchlist refreshed
from the GUR War &amp; Sanctions portal (1,404 vessels; detection keyed on the
union of current and legacy MMSIs, 1,480 identifiers, after finding 23.6% MMSI
churn). Q1 2026 Danish-waters run: DMA daily files, 1 Jan – 31 Mar 2026.
Known caveats: two Comoros MMSIs are reused across distinct hulls (attribution
ambiguity for SARD/ION and COMETA/VIKRAM); GUR portal requires browser TLS
fingerprint (curl_cffi) from cloud IPs.</p>"""
mpos = doc.find(anchor)
if mpos != -1:
    endh2 = doc.find('</h2>', mpos) + 5
    doc = doc[:endh2] + methods_note + doc[endh2:]

doc = doc.replace('shadow_fleet_dashboard_v4', 'shadow_fleet_dashboard_v5')
open('shadow_fleet_dashboard_v5.html', 'w', encoding='utf-8').write(doc)
size = os.path.getsize('shadow_fleet_dashboard_v5.html') / 1e6
print(f"DONE: shadow_fleet_dashboard_v5.html ({size:.1f} MB) | "
      f"{n_vessels} vessel cards, {missing_thumbs} without photo")
if size > 25:
    print("WARNING: file large — check tiiny.site free-tier upload limit")
