"""Download the Ken French daily factors (public data library): Fama/French 3 factors daily and Momentum daily.
Saves the zips' CSVs under data/raw/french/ (gitignored) and writes data/raw/french/factors_daily.csv with columns
date, mkt_rf, smb, hml, rf, umd in DECIMALS (the library publishes percent).

Usage: python -m ingest.french_factors
"""
from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pandas as pd
import requests

BASE = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"
FILES = {"ff3": "F-F_Research_Data_Factors_daily_CSV.zip", "mom": "F-F_Momentum_Factor_daily_CSV.zip"}
OUT = Path("data/raw/french")


def read(name: str) -> pd.DataFrame:
    r = requests.get(BASE + FILES[name], timeout=60)
    r.raise_for_status()
    z = zipfile.ZipFile(io.BytesIO(r.content))
    raw = z.read(z.namelist()[0]).decode("latin-1")
    (OUT / z.namelist()[0]).write_text(raw)
    rows = [l for l in raw.splitlines() if l[:8].strip().isdigit() and len(l.split(",")[0].strip()) == 8]
    df = pd.read_csv(io.StringIO("\n".join(rows)), header=None)
    df[0] = pd.to_datetime(df[0].astype(str).str.strip(), format="%Y%m%d")
    return df


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    f = read("ff3").rename(columns={0: "date", 1: "mkt_rf", 2: "smb", 3: "hml", 4: "rf"})
    m = read("mom").rename(columns={0: "date", 1: "umd"})
    d = f.merge(m, on="date", how="inner")
    for c in ("mkt_rf", "smb", "hml", "rf", "umd"):
        d[c] = pd.to_numeric(d[c], errors="coerce") / 100
    d.to_csv(OUT / "factors_daily.csv", index=False)
    print(f"{OUT / 'factors_daily.csv'}: {len(d)} days, {d['date'].min().date()} to {d['date'].max().date()}")


if __name__ == "__main__":
    main()
