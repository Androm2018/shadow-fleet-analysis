python3 detected_flag_sanctions.py"""
Flag × sanctions cross-tab for the Q1 2026 DETECTED vessels (Danish waters).

Joins detected_vessels_q1_2026.csv (has gur_flag, gur_imo) to sanctions_by_imo.csv
(exported from the sanctions cross-reference; imo + ofac/uk/eu booleans).
Writes detected_255_flag_sanctions.csv — same shape as the workbook's
'Flag × Sanctions' sheet but restricted to the detected fleet.

Drop both files into the Codespace, then: python3 detected_flag_sanctions.py
"""
import pandas as pd

det = pd.read_csv('detected_vessels_q1_2026.csv', dtype=str)
det['imo'] = det['gur_imo'].astype(str).str.strip()
det['flag'] = det['gur_flag'].fillna('').str.strip().str.title().replace({'':'Unknown','Nan':'Unknown'})

s = pd.read_csv('sanctions_by_imo.csv', dtype={'imo':str})
for c in ('ofac','uk','eu'):
    s[c] = s[c].astype(str).str.lower().isin(['true','1'])
sset = {'ofac':set(s[s.ofac].imo), 'uk':set(s[s.uk].imo), 'eu':set(s[s.eu].imo)}

det['ofac'] = det['imo'].isin(sset['ofac'])
det['uk']   = det['imo'].isin(sset['uk'])
det['eu']   = det['imo'].isin(sset['eu'])
det['any']  = det[['ofac','uk','eu']].any(axis=1)
n = len(det)

rows=[]
for flag,g in det.groupby('flag'):
    rows.append({'Flag':flag,'Vessels':len(g),'OFAC':int(g.ofac.sum()),'UK':int(g.uk.sum()),
                 'EU':int(g.eu.sum()),'Any Western':int(g['any'].sum()),
                 'None (GUR-only)':int((~g['any']).sum()),'% sanctioned':round(g['any'].mean()*100,1)})
tab=pd.DataFrame(rows).sort_values('Vessels',ascending=False).reset_index(drop=True)
tot={'Flag':'TOTAL','Vessels':n,'OFAC':int(det.ofac.sum()),'UK':int(det.uk.sum()),
     'EU':int(det.eu.sum()),'Any Western':int(det['any'].sum()),
     'None (GUR-only)':int((~det['any']).sum()),'% sanctioned':round(det['any'].mean()*100,1)}
out=pd.concat([tab, pd.DataFrame([tot])], ignore_index=True)
out.to_csv('detected_255_flag_sanctions.csv', index=False)
print(f"DETECTED {n} vessels — flag × sanctions:\n")
print(tab.to_string(index=False))
print("\nTOTAL:", tot)
print("\nsaved detected_255_flag_sanctions.csv")
