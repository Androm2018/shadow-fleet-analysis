"""
Flag breakdown of the Q1 2026 Danish-waters detected vessels.

Reads detected_vessels_q1_2026.csv (has gur_flag from the watchlist join),
normalises flag strings, prints a full table + a grouped summary
(Russian / flag-of-convenience / unknown / other), and renders a dark-style
horizontal bar chart: flag_breakdown_q1_2026.png
"""
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

d = pd.read_csv('detected_vessels_q1_2026.csv', dtype=str)
flag = (d['gur_flag'].fillna('').str.strip().str.title()
        .replace({'': 'Unknown', 'Nan': 'Unknown'}))
n = len(d)

vc = flag.value_counts()
print(f"=== FLAG BREAKDOWN — {n} vessels detected in Danish waters, Q1 2026 ===\n")
for k, v in vc.items():
    print(f"  {k:<22} {v:>4}  ({v/n*100:4.1f}%)")

# grouped summary
FOC = {'Panama','Liberia','Cameroon','Sierra Leone','Marshall Islands','Cook Islands',
       'Comoros','Barbados','Palau','Gabon','Togo','Antigua And Barbuda','Saint Kitts And Nevis',
       'Tanzania','Belize','Honduras','Malta','Cyprus','Saint Vincent And The Grenadines'}
def group(f):
    if f == 'Russian Federation': return 'Russian Federation'
    if f == 'Unknown': return 'Unknown / no flag'
    if f in FOC: return 'Flag of convenience'
    return 'Other'
g = flag.map(group).value_counts()
print("\n--- grouped ---")
for k, v in g.items():
    print(f"  {k:<22} {v:>4}  ({v/n*100:4.1f}%)")

# chart
fig, ax = plt.subplots(figsize=(12, 8), facecolor='#0d1520')
ax.set_facecolor('#111827')
top = vc.head(12)[::-1]
COLORS = {'Russian Federation':'#d44040', 'Unknown':'#6a7a90'}
bars = ax.barh(top.index, top.values,
               color=[COLORS.get(k, '#2a7fd4') for k in top.index], alpha=0.9)
for b, v in zip(bars, top.values):
    ax.text(v + n*0.005, b.get_y()+b.get_height()/2, f"{v} ({v/n*100:.0f}%)",
            va='center', color='#aaa', fontsize=9)
ax.set_title(f'Flag of registration — {n} GUR-watchlist vessels detected in Danish waters, Q1 2026\n'
             f'Source: Danish Maritime Authority AIS · GUR watchlist v2',
             color='white', fontsize=12.5, pad=12)
ax.set_xlabel('Vessels', color='#aaa')
ax.tick_params(colors='#aaa', labelsize=10)
ax.grid(True, color='#2a3050', linewidth=0.5, axis='x')
for s in ax.spines.values(): s.set_color('#2a3050')
ax.set_xlim(0, top.max()*1.15)
plt.tight_layout()
plt.savefig('flag_breakdown_q1_2026.png', dpi=150, bbox_inches='tight', facecolor='#0d1520')
print("\nSaved flag_breakdown_q1_2026.png")
