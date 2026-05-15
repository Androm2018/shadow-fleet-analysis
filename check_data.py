import pandas as pd
df = pd.read_csv('extended_transits.csv', low_memory=False)
print(f'Total pings: {len(df):,}')
print(f'Unique vessels: {df["MMSI"].nunique()}')
print(f'Date range: {df["Timestamp"].min()} to {df["Timestamp"].max()}')
print(f'\nZone breakdown:')
print(df.groupby('Zone')['MMSI'].count().sort_values(ascending=False).to_string())
