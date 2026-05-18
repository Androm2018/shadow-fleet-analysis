import csv, os, json

OUT_ROOT = "vessel_images"

with open(f"{OUT_ROOT}/multi_manifest.csv") as f:
    manifest = [r for r in csv.DictReader(f) if r["status"] in ("ok", "cached") and int(r["n_photos"]) > 0]

vessels = []
for m in manifest:
    photos = sorted([f for f in os.listdir(m["dir"]) if f.endswith(".jpg")])
    rel_dir = os.path.basename(m["dir"])
    vessels.append({
        "imo": m["imo"],
        "name": m["name"],
        "dir": rel_dir,
        "n": len(photos),
        "thumb": f"{rel_dir}/{photos[0]}" if photos else "",
        "photos": [f"{rel_dir}/{p}" for p in photos],
    })

vessels.sort(key=lambda v: (v["name"] or "zzz", v["imo"]))

html = f"""<!DOCTYPE html><html><head><meta charset='utf-8'>
<title>Baltic-active shadow fleet — {len(vessels)} vessels with images</title>
<style>
*{{box-sizing:border-box}}
body{{font-family:system-ui,-apple-system,sans-serif;background:#0a1018;color:#ddd;margin:0;padding:20px}}
h1{{color:#fff;margin:0 0 8px 0;font-size:22px}}
.sub{{color:#8aa;margin-bottom:20px;font-size:13px}}
.controls{{display:flex;gap:10px;margin-bottom:20px;flex-wrap:wrap}}
input,select{{padding:10px 12px;background:#1a2333;color:#fff;border:1px solid #2a3050;border-radius:6px;font-size:14px}}
input{{flex:1;min-width:240px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:14px}}
.card{{background:#141d2c;border:1px solid #1f2940;border-radius:8px;overflow:hidden;cursor:pointer;transition:transform .15s,border-color .15s}}
.card:hover{{transform:translateY(-2px);border-color:#3b5680}}
.card img{{width:100%;height:160px;object-fit:cover;display:block;background:#0a1018}}
.meta{{padding:10px 12px}}
.name{{font-weight:600;color:#fff;font-size:14px;margin-bottom:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.imo{{color:#7a99c2;font-family:'SF Mono',Menlo,monospace;font-size:11px}}
.count{{display:inline-block;background:#2a3a5c;color:#cfe;padding:2px 6px;border-radius:3px;font-size:11px;margin-left:6px}}
.modal{{display:none;position:fixed;inset:0;background:rgba(0,0,0,0.92);z-index:100;padding:40px 20px;overflow-y:auto}}
.modal.open{{display:block}}
.modal-close{{position:fixed;top:15px;right:20px;background:#1a2333;color:#fff;border:1px solid #3b5680;padding:8px 14px;border-radius:6px;cursor:pointer;font-size:14px;z-index:101}}
.modal-title{{color:#fff;font-size:20px;margin:0 0 4px 0;max-width:80%}}
.modal-sub{{color:#7a99c2;font-family:monospace;font-size:13px;margin-bottom:24px}}
.modal-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(360px,1fr));gap:14px}}
.modal-grid img{{width:100%;border-radius:6px;background:#1a2333;cursor:zoom-in}}
</style></head><body>
<h1>Baltic-active shadow fleet — visual reference</h1>
<div class='sub'>{len(vessels)} vessels with images · {sum(v['n'] for v in vessels)} photos · click a card for all photos</div>
<div class='controls'>
  <input id='q' placeholder='Filter by name, IMO…' oninput='applyFilter()'>
  <select id='sort' onchange='applyFilter()'>
    <option value='name'>Sort: name</option>
    <option value='imo'>Sort: IMO</option>
    <option value='photos'>Sort: most photos</option>
  </select>
</div>
<div class='grid' id='grid'></div>

<div class='modal' id='modal'>
  <button class='modal-close' onclick='closeModal()'>Close ✕</button>
  <h2 class='modal-title' id='modal-title'></h2>
  <div class='modal-sub' id='modal-sub'></div>
  <div class='modal-grid' id='modal-grid'></div>
</div>

<script>
const vessels = {json.dumps(vessels)};

function render(list){{
  const grid = document.getElementById('grid');
  grid.innerHTML = list.map((v,i) => `
    <div class='card' onclick='openModal(${{i}})'>
      <img src='${{v.thumb}}' loading='lazy'>
      <div class='meta'>
        <div class='name'>${{v.name||'(no name)'}}<span class='count'>${{v.n}}</span></div>
        <div class='imo'>IMO ${{v.imo}}</div>
      </div>
    </div>`).join('');
  window.currentList = list;
}}

function applyFilter(){{
  const q = document.getElementById('q').value.toLowerCase();
  const sort = document.getElementById('sort').value;
  let list = vessels.filter(v => (v.name+' '+v.imo).toLowerCase().includes(q));
  if(sort==='name') list.sort((a,b)=>(a.name||'zzz').localeCompare(b.name||'zzz'));
  if(sort==='imo')  list.sort((a,b)=>a.imo.localeCompare(b.imo));
  if(sort==='photos') list.sort((a,b)=>b.n-a.n);
  render(list);
}}

function openModal(i){{
  const v = window.currentList[i];
  document.getElementById('modal-title').textContent = v.name||'(no name)';
  document.getElementById('modal-sub').textContent = `IMO ${{v.imo}} · ${{v.n}} photos`;
  document.getElementById('modal-grid').innerHTML = v.photos.map(p =>
    `<a href='${{p}}' target='_blank'><img src='${{p}}' loading='lazy'></a>`).join('');
  document.getElementById('modal').classList.add('open');
}}
function closeModal(){{ document.getElementById('modal').classList.remove('open'); }}
document.addEventListener('keydown', e => {{ if(e.key==='Escape') closeModal(); }});

render(vessels);
</script>
</body></html>"""

with open(f"{OUT_ROOT}/index.html", "w") as f:
    f.write(html)

print(f"Written {OUT_ROOT}/index.html — {len(vessels)} vessels, {sum(v['n'] for v in vessels)} photos")
