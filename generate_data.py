import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json, random, sqlite3, os

random.seed(42)
np.random.seed(42)

# ── Known shadow fleet MMSIs (subset of GUR catalogue, well-documented vessels) ──
KNOWN_VESSELS = [
    {"mmsi": "636022811", "name": "EAGLE S",    "flag": "Cook Islands",     "imo": "9329760"},
    {"mmsi": "636091785", "name": "EVENTIN",    "flag": "Gabon",            "imo": "9308065"},
    {"mmsi": "636092268", "name": "KIWALA",     "flag": "Djibouti",         "imo": "9332810"},
    {"mmsi": "636019316", "name": "JAGUAR",     "flag": "Gabon",            "imo": "9293002"},
    {"mmsi": "477305800", "name": "KIRA K",     "flag": "Palau",            "imo": "9346720"},
    {"mmsi": "636091234", "name": "FITBURG",    "flag": "Cameroon",         "imo": "9250397"},
    {"mmsi": "273337360", "name": "BLUE",       "flag": "Antigua/Barbuda",  "imo": "9200440"},
    {"mmsi": "577291000", "name": "SUN",        "flag": "Antigua/Barbuda",  "imo": "9185671"},
    {"mmsi": "636020432", "name": "SELVA",      "flag": "Cameroon",         "imo": "9210371"},
    {"mmsi": "636018974", "name": "SIERRA",     "flag": "Gabon",            "imo": "9203571"},
    {"mmsi": "636092100", "name": "FOTUO",      "flag": "Gabon",            "imo": "9280001"},
    {"mmsi": "636091500", "name": "QENDIL",     "flag": "Palau",            "imo": "9310525"},
    {"mmsi": "511100872", "name": "PEACE",      "flag": "Palau",            "imo": "9312344"},
    {"mmsi": "636093100", "name": "VIRAT",      "flag": "Tanzania",         "imo": "9290112"},
    {"mmsi": "636091780", "name": "CAFFA",      "flag": "Cameroon",         "imo": "9143611"},
    {"mmsi": "636019800", "name": "SEA OWL I",  "flag": "Comoros",          "imo": "9321172"},
    {"mmsi": "636020100", "name": "LUGA",       "flag": "Russia",           "imo": "9345001"},
    {"mmsi": "273450100", "name": "ARCTIC",     "flag": "Gabon",            "imo": "9180234"},
    {"mmsi": "636091900", "name": "DOLPHIN",    "flag": "Antigua/Barbuda",  "imo": "9265400"},
    {"mmsi": "636092400", "name": "ARINA 1",    "flag": "Tanzania",         "imo": "9190050"},
]

# ── Route corridor waypoints (realistic shipping lanes) ──
# Main route: Ust-Luga → Gulf of Finland → Danish Straits → North Sea → English Channel
# Øresund sub-route and Great Belt sub-route

ROUTE_ORESUND = [
    (59.8, 28.4),  # Ust-Luga area
    (59.5, 25.5),  # Gulf of Finland mid
    (59.3, 23.0),  # Gulf of Finland west
    (59.5, 21.0),  # Approaching Åland
    (59.7, 20.0),  # Northern Baltic
    (58.5, 18.5),  # Stockholm approaches
    (57.0, 17.5),  # Central Baltic
    (56.0, 15.5),  # Southern Baltic
    (55.8, 14.5),  # Approaching Øresund
    (55.7, 12.9),  # Øresund (Copenhagen)
    (55.9, 12.5),  # Northern Øresund
    (56.1, 12.2),  # Helsingborg/Helsingør
    (56.5, 11.5),  # Kattegat south
    (57.0, 10.8),  # Kattegat mid
    (57.5, 10.3),  # Kattegat north
    (57.7, 10.5),  # Skagen area (refuelling)
    (57.9, 10.0),  # Off Skagen
    (58.2,  9.0),  # Skagerrak
    (58.0,  7.5),  # North Sea approaches
    (57.5,  5.5),  # North Sea
    (56.0,  3.5),  # Central North Sea
    (54.5,  2.0),  # Southern North Sea
    (51.5,  1.5),  # English Channel approaches
    (51.0,  1.2),  # Dover Strait
]

ROUTE_GREAT_BELT = [
    (59.8, 28.4),  # Ust-Luga
    (59.5, 25.5),  # Gulf of Finland mid
    (58.5, 20.5),  # Baltic mid
    (57.2, 17.0),  # Southern Baltic
    (56.2, 15.0),  # Bornholm area
    (55.5, 11.5),  # Great Belt south
    (55.6, 10.8),  # Great Belt mid
    (55.8, 10.5),  # Great Belt north
    (56.3, 10.2),  # Kattegat south
    (57.0, 10.5),  # Kattegat mid
    (57.7, 10.5),  # Skagen
    (58.2,  9.0),  # Skagerrak
    (57.5,  5.5),  # North Sea
    (56.0,  3.5),  # Central North Sea
    (51.0,  1.2),  # Dover Strait
]

# Alternative route around Scotland (evasion behaviour)
ROUTE_SCOTLAND = [
    (59.8, 28.4),
    (59.5, 25.5),
    (58.5, 20.5),
    (57.0, 17.0),
    (55.8, 14.5),
    (55.7, 12.9),  # Øresund
    (57.7, 10.5),  # Skagen
    (59.0,  5.0),  # Norwegian coast
    (60.5,  3.0),  # North of Shetland
    (61.0,  0.0),  # North Atlantic
    (60.0, -3.0),  # West of Scotland
    (58.0, -5.0),  # NW Scotland
    (55.0, -6.0),  # Ireland approaches
    (53.0, -5.0),  # Irish Sea
    (51.0, -4.0),  # Bristol Channel
    (50.0, -3.0),  # English Channel west
    (51.0,  1.2),  # Dover
]

def interpolate_route(waypoints, n_points=80, noise_sd=0.08):
    """Interpolate a route with realistic noise"""
    from scipy.interpolate import interp1d
    lats = [w[0] for w in waypoints]
    lons = [w[1] for w in waypoints]
    t = np.linspace(0, 1, len(waypoints))
    t_new = np.linspace(0, 1, n_points)
    f_lat = interp1d(t, lats, kind='cubic')
    f_lon = interp1d(t, lons, kind='cubic')
    lats_i = f_lat(t_new) + np.random.normal(0, noise_sd, n_points)
    lons_i = f_lon(t_new) + np.random.normal(0, noise_sd, n_points)
    return list(zip(lats_i, lons_i))

def simulate_voyage(vessel, start_date, route_type="oresund"):
    """Simulate a single vessel voyage with AIS pings every ~4 hours"""
    routes = {
        "oresund":    ROUTE_ORESUND,
        "great_belt": ROUTE_GREAT_BELT,
        "scotland":   ROUTE_SCOTLAND,
    }
    waypoints = routes[route_type]
    n_pings = len(waypoints) * 4
    coords = interpolate_route(waypoints, n_pings)

    records = []
    ts = start_date
    # AIS blackout: randomly blank out 10-25% of pings (shadow fleet evasion)
    blackout_probability = random.uniform(0.10, 0.25)
    in_blackout = False
    blackout_remaining = 0

    for i, (lat, lon) in enumerate(coords):
        if blackout_remaining > 0:
            blackout_remaining -= 1
            in_blackout = True
        elif random.random() < 0.04:  # start new blackout
            blackout_remaining = random.randint(3, 12)
            in_blackout = True
        else:
            in_blackout = False

        if not in_blackout:
            speed = round(random.uniform(8.0, 13.5), 1)
            records.append({
                "timestamp": ts.strftime("%d/%m/%Y %H:%M:%S"),
                "mmsi": vessel["mmsi"],
                "name": vessel["name"],
                "imo": vessel["imo"],
                "flag": vessel["flag"],
                "lat": round(lat, 5),
                "lon": round(lon, 5),
                "speed": speed,
                "heading": round(random.uniform(200, 280), 1),
                "destination": random.choice(["INDIA", "CHINA", "PRIMORSK", "UST LUGA", "SINGAPORE"]),
                "route_type": route_type,
                "cable_alert": 1 if any(
                    abs(lat - cl) < 0.3 and abs(lon - co) < 0.3
                    for cl, co in [(55.5, 12.9), (57.5, 10.5), (59.4, 25.2)]
                ) else 0
            })
        ts += timedelta(hours=4)

    return records

# ── Generate 2025 dataset ──
print("Generating 2025 shadow fleet AIS dataset...")
all_records = []
start_2025 = datetime(2025, 1, 1)

# Each vessel makes multiple voyages per year
for vessel in KNOWN_VESSELS:
    # Between 4-8 eastbound voyages (Russian port → world) per vessel in 2025
    n_voyages = random.randint(4, 8)
    for v in range(n_voyages):
        # Stagger voyage starts across 2025
        day_offset = random.randint(0, 340)
        start = start_2025 + timedelta(days=day_offset)
        # Route choice: 65% Øresund, 25% Great Belt, 10% Scotland (evasion)
        route = random.choices(
            ["oresund", "great_belt", "scotland"],
            weights=[0.65, 0.25, 0.10]
        )[0]
        records = simulate_voyage(vessel, start, route)
        all_records.extend(records)

df = pd.DataFrame(all_records)
df = df.sort_values("timestamp").reset_index(drop=True)
print(f"Generated {len(df):,} AIS pings across {df['mmsi'].nunique()} vessels")
print(f"Route breakdown:\n{df.drop_duplicates('timestamp').groupby('route_type').size() if False else df[['mmsi','route_type']].drop_duplicates('mmsi')}")

# Save as CSV (mimicking DMA format)
df.to_csv("/home/claude/shadow_fleet_2025_ais.csv", index=False)
print("Saved to shadow_fleet_2025_ais.csv")
print(df[['name','flag','route_type']].drop_duplicates().to_string())
