"""
Refresh the GUR War & Sanctions ship watchlist (war-sanctions.gur.gov.ua).

Scrapes all list pages (name, IMO, flag, vessel type) then every detail page
(MMSI, callsign, former names, build year). Outputs:
  - gur_vessels_master.csv : one row per GUR entry
  - Vessels2.db            : MMSI-keyed db (union of current + any prior MMSIs
                             passed via --legacy-db), schema-compatible with
                             filter_extended.py / fetch_uk_monthly.py

Usage:
  python3 scrape_gur_watchlist.py --legacy-db Vessels1.db
Run time: ~10 min at polite request rates (4 workers, ~0.4s effective spacing).
"""
import argparse, re, sqlite3, time
import pandas as pd
from curl_cffi import requests
from concurrent.futures import ThreadPoolExecutor

BASE = "https://war-sanctions.gur.gov.ua/en/transport/ships"
HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"}

def parse_cards(html):
    out = []
    parts = re.split(r'href="https://war-sanctions\.gur\.gov\.ua/en/transport/ships/(\d+)"', html)
    for i in range(1, len(parts) - 1, 2):
        gid, card = parts[i], parts[i + 1][:4000]
        lines = [l.strip() for l in re.sub(r'<[^>]+>', '\n', card).split('\n') if l.strip()]
        def field(label):
            try:
                return lines[lines.index(label) + 1]
            except (ValueError, IndexError):
                return ''
        flag = ''
        for j, l in enumerate(lines):
            if l == 'Flag (Current)':
                rest = [x for x in lines[j + 1:j + 4] if x]
                flag = rest[0] if rest else ''
                break
        out.append({'gur_id': gid, 'name': field('Vessel name'), 'imo': field('IMO'),
                    'flag': flag, 'vessel_type': field('Vessel Type')})
    return out

def scrape_list(session):
    rows, seen, page = [], set(), 1
    while True:
        r = session.get(BASE, params={'page': page, 'per-page': 12}, timeout=30)
        new = [x for x in parse_cards(r.text) if x['gur_id'] not in seen]
        if not new:
            break
        for x in new:
            seen.add(x['gur_id']); rows.append(x)
        if page % 20 == 0:
            print(f"  list page {page}: {len(rows)} vessels", flush=True)
        page += 1
        time.sleep(0.4)
    return rows

DETAIL_FIELDS = [('MMSI', 'mmsi'), ('Call sign', 'callsign'),
                 ('Former ship names', 'former_names'), ('Build year', 'build_year')]

def scrape_detail(session, v):
    for _ in range(2):
        try:
            r = session.get(f"{BASE}/{v['gur_id']}", timeout=25)
            if r.status_code != 200:
                time.sleep(2); continue
            lines = [l.strip() for l in re.sub(r'<[^>]+>', '\n', r.text).split('\n') if l.strip()]
            out = dict(v)
            for label, key in DETAIL_FIELDS:
                try:
                    out[key] = lines[lines.index(label) + 1]
                except (ValueError, IndexError):
                    out[key] = ''
            # detail pages occasionally omit IMO; guard against field bleed
            if out.get('imo') == 'Flag (Current)':
                out['imo'] = ''
            return out
        except requests.RequestException:
            time.sleep(2)
    return dict(v)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--legacy-db', default=None,
                    help='Prior Vessels db; its MMSIs are unioned into Vessels2.db '
                         'and compared as mmsi_legacy (matched on IMO)')
    args = ap.parse_args()

    session = requests.Session()
    session.headers.update(HEADERS)

    print("Scraping list pages...")
    vessels = scrape_list(session)
    print(f"List complete: {len(vessels)} vessels. Scraping detail pages...")

    results = []
    with ThreadPoolExecutor(max_workers=4) as ex:
        for n, row in enumerate(ex.map(lambda v: scrape_detail(session, v), vessels), 1):
            results.append(row)
            if n % 200 == 0:
                print(f"  detail {n}/{len(vessels)}", flush=True)
    master = pd.DataFrame(results)
    master['imo'] = master['imo'].astype(str).str.strip()
    master['status'] = 'listed'
    master['mmsi_legacy'] = None

    if args.legacy_db:
        con = sqlite3.connect(args.legacy_db)
        legacy = pd.read_sql('SELECT mmsi AS mmsi_legacy, imo, name FROM vessels', con)
        con.close()
        legacy['imo'] = legacy['imo'].astype(str).str.strip()
        legacy['mmsi_legacy'] = legacy['mmsi_legacy'].astype(str).str.strip()
        master = master.drop(columns=['mmsi_legacy']).merge(
            legacy[['imo', 'mmsi_legacy']].drop_duplicates('imo'), on='imo', how='left')
        delisted = legacy[~legacy['imo'].isin(set(master['imo']))].copy()
        delisted['status'] = 'delisted_from_gur'
        master = pd.concat([master, delisted.drop(columns=['name']).assign(name=delisted['name'])],
                           ignore_index=True)
        matched = master[master['mmsi_legacy'].notna() & master['mmsi'].notna()]
        changed = (matched['mmsi_legacy'] != matched['mmsi']).sum()
        print(f"MMSI churn vs legacy db: {changed}/{len(matched)} ({changed/len(matched)*100:.1f}%)")

    master = master.rename(columns={'mmsi': 'mmsi_current'})
    cols = ['gur_id', 'name', 'imo', 'mmsi_current', 'mmsi_legacy', 'flag',
            'vessel_type', 'callsign', 'former_names', 'build_year', 'status']
    master.reindex(columns=cols).to_csv('gur_vessels_master.csv', index=False)
    print(f"Saved gur_vessels_master.csv ({len(master)} rows)")

    rows = []
    for _, r in master.iterrows():
        for col in ('mmsi_current', 'mmsi_legacy'):
            v = str(r.get(col)) if pd.notna(r.get(col)) else ''
            if v.isdigit():
                rows.append({'mmsi': v, 'imo': r['imo'] or None,
                             'name': r['name'], 'destination': None})
    db = pd.DataFrame(rows).drop_duplicates('mmsi')
    con = sqlite3.connect('Vessels2.db')
    db.to_sql('vessels', con, index=False, if_exists='replace')
    con.close()
    print(f"Vessels2.db: {len(db)} MMSI rows")

if __name__ == '__main__':
    main()
