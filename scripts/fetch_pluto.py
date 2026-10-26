import os
import requests
import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_PATH = os.path.join(BASE_DIR, "data", "pluto_gfa.csv")

# NYC PLUTO on NYC Open Data (Socrata)
DATASET_ID = "64uk-42ks"
URL = f"https://data.cityofnewyork.us/resource/{DATASET_ID}.json"

params = {
    "$select": "borocode,block,lot,bldgarea",
    "$where": "bldgarea IS NOT NULL AND borocode IS NOT NULL AND block IS NOT NULL AND lot IS NOT NULL",
    "$limit": 6000,
    "$order": "borocode,block,lot",
}

resp = requests.get(URL, params=params, timeout=60)
resp.raise_for_status()
df = pd.DataFrame(resp.json())

# Reconstruct canonical 10-digit BBL: borough(1) + block(5) + lot(4)
df["bbl"] = (
    df["borocode"].astype(int).astype(str)
    + df["block"].astype(int).astype(str).str.zfill(5)
    + df["lot"].astype(int).astype(str).str.zfill(4)
)

df["gfa_pluto"] = pd.to_numeric(df["bldgarea"], errors="coerce")
df = df.dropna(subset=["gfa_pluto"])
df = df[df["gfa_pluto"] > 0]

df = df[["bbl", "gfa_pluto"]]
df.to_csv(OUTPUT_PATH, index=False)

print(f"Saved {len(df)} PLUTO records to {OUTPUT_PATH}")
print("bbl length distribution:", df["bbl"].str.len().value_counts().to_dict())
print(df.head(8).to_string(index=False))