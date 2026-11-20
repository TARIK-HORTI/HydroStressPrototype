"""
stations.py
===========
Validation des données maillées (CHIRPS, ERA5-Land) par les stations
météorologiques synoptiques du Maroc publiées par la NOAA (Global Summary of
the Day, GSOD), en accès libre.

Les stations ne remplacent pas CHIRPS / ERA5-Land dans le modèle (elles sont
trop espacées : souvent > 50 km d'une parcelle). Elles servent à vérifier,
pour une analyse donnée, que la météo utilisée est cohérente avec les
observations au sol les plus proches.

Sources :
- Liste des stations : https://www.ncei.noaa.gov/pub/data/noaa/isd-history.csv
- Données journalières : https://www.ncei.noaa.gov/data/global-summary-of-the-day/access/{année}/{station}.csv
"""

import io
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from region import distance_km, is_in_region

logger = logging.getLogger(__name__)

ISD_HISTORY_URL = "https://www.ncei.noaa.gov/pub/data/noaa/isd-history.csv"
GSOD_URL = "https://www.ncei.noaa.gov/data/global-summary-of-the-day/access/{year}/{station}.csv"
STATIONS_CACHE = Path("data/stations_morocco.csv")
COUNTRY_CODES = {"MO", "WI"}       # Maroc, provinces du Sud
TIMEOUT_S = 30

MISSING_TEMP = 9999.9
MISSING_PRCP = 99.99


def _http_get(url: str) -> str:
    import requests
    resp = requests.get(url, timeout=TIMEOUT_S)
    resp.raise_for_status()
    return resp.text


def parse_station_list(csv_text: str, active_since: str = "20200101") -> pd.DataFrame:
    """Stations du Maroc encore actives, au format [station, name, lat, lon, elevation_m, end]."""
    df = pd.read_csv(io.StringIO(csv_text), dtype=str)
    df = df[df["CTRY"].isin(COUNTRY_CODES)].copy()
    df["lat"] = pd.to_numeric(df["LAT"], errors="coerce")
    df["lon"] = pd.to_numeric(df["LON"], errors="coerce")
    df = df.dropna(subset=["lat", "lon"])
    df = df[df.apply(lambda r: is_in_region(r["lon"], r["lat"]), axis=1)]
    df = df[df["END"].fillna("0") >= active_since]
    return pd.DataFrame({
        "station": df["USAF"].str.zfill(6) + df["WBAN"].str.zfill(5),
        "name": df["STATION NAME"].str.title(),
        "lat": df["lat"],
        "lon": df["lon"],
        "elevation_m": pd.to_numeric(df["ELEV(M)"], errors="coerce"),
        "end": df["END"],
    }).drop_duplicates("station").reset_index(drop=True)


def load_stations(cache: Path = STATIONS_CACHE) -> pd.DataFrame:
    """Liste des stations (téléchargée une fois puis mise en cache)."""
    if cache.exists():
        return pd.read_csv(cache, dtype={"station": str, "end": str})
    stations = parse_station_list(_http_get(ISD_HISTORY_URL))
    cache.parent.mkdir(parents=True, exist_ok=True)
    stations.to_csv(cache, index=False)
    logger.info(f"✓ {len(stations)} stations du Maroc mises en cache dans {cache}")
    return stations


def nearest_stations(stations: pd.DataFrame, lat: float, lon: float, n: int = 3,
                     max_km: float = 150.0) -> pd.DataFrame:
    """Les n stations les plus proches à moins de max_km, triées par distance."""
    if stations.empty:
        return stations.assign(distance_km=[])
    d = stations.apply(lambda r: distance_km(lat, lon, r["lat"], r["lon"]), axis=1)
    out = stations.assign(distance_km=d.round(1))
    return out[out["distance_km"] <= max_km].sort_values("distance_km").head(n).reset_index(drop=True)


def parse_gsod(csv_text: str) -> pd.DataFrame:
    """
    Convertit un fichier GSOD en unités métriques :
    [date, temperature_c, temperature_max_c, temperature_min_c, dewpoint_c, precipitation_mm].
    Les codes de valeurs manquantes (9999.9, 99.99) deviennent NaN.
    """
    raw = pd.read_csv(io.StringIO(csv_text))
    raw.columns = [c.strip().upper() for c in raw.columns]

    def temp(col):
        v = pd.to_numeric(raw[col], errors="coerce")
        v = v.where(v < MISSING_TEMP - 1)
        return (v - 32.0) * 5.0 / 9.0

    prcp = pd.to_numeric(raw["PRCP"], errors="coerce")
    prcp = prcp.where(prcp < MISSING_PRCP - 0.001) * 25.4

    return pd.DataFrame({
        "date": pd.to_datetime(raw["DATE"]),
        "temperature_c": temp("TEMP"),
        "temperature_max_c": temp("MAX"),
        "temperature_min_c": temp("MIN"),
        "dewpoint_c": temp("DEWP"),
        "precipitation_mm": prcp,
    })


def fetch_station_series(station: str, start: str, end: str) -> pd.DataFrame:
    """Série GSOD d'une station entre deux dates (incluses)."""
    start_dt, end_dt = datetime.strptime(start, "%Y-%m-%d"), datetime.strptime(end, "%Y-%m-%d")
    frames = []
    for year in range(start_dt.year, end_dt.year + 1):
        try:
            frames.append(parse_gsod(_http_get(GSOD_URL.format(year=year, station=station))))
        except Exception as e:
            logger.warning(f"GSOD {station} {year} indisponible : {e}")
    if not frames:
        return pd.DataFrame(columns=["date", "temperature_c", "temperature_max_c", "temperature_min_c",
                                     "dewpoint_c", "precipitation_mm"])
    df = pd.concat(frames, ignore_index=True)
    return df[(df["date"] >= start_dt) & (df["date"] <= end_dt)].sort_values("date").reset_index(drop=True)


def _metrics(obs: pd.Series, grid: pd.Series) -> Dict[str, Optional[float]]:
    pair = pd.DataFrame({"obs": obs, "grid": grid}).dropna()
    if len(pair) < 3:
        return {"days": len(pair), "bias": None, "mae": None, "corr": None}
    diff = pair["grid"] - pair["obs"]
    corr = pair["obs"].corr(pair["grid"]) if pair["obs"].std() > 0 and pair["grid"].std() > 0 else None
    return {
        "days": int(len(pair)),
        "bias": round(float(diff.mean()), 2),
        "mae": round(float(diff.abs().mean()), 2),
        "corr": round(float(corr), 2) if corr is not None and not np.isnan(corr) else None,
    }


def compare_with_grids(station_df: pd.DataFrame, chirps_df: pd.DataFrame, era5_df: pd.DataFrame) -> Dict[str, Dict]:
    """
    Compare la station aux séries utilisées par l'analyse (même jours).

    Returns:
        {"temperature_mean": {...}, "temperature_max": {...}, "precipitation": {...}}
        bias = maillé - station (°C ou mm/jour) ; precipitation inclut aussi les cumuls.
    """
    s = station_df.set_index("date")
    e = era5_df.set_index("date") if not era5_df.empty else pd.DataFrame()
    c = chirps_df.set_index("date") if not chirps_df.empty else pd.DataFrame()
    out = {}
    if not e.empty:
        out["temperature_mean"] = _metrics(s["temperature_c"], e["temperature_c"].reindex(s.index))
        out["temperature_max"] = _metrics(s["temperature_max_c"], e["temperature_max_c"].reindex(s.index))
    if not c.empty:
        grid = c["precipitation_mm"].reindex(s.index)
        m = _metrics(s["precipitation_mm"], grid)
        both = pd.DataFrame({"obs": s["precipitation_mm"], "grid": grid}).dropna()
        m["total_station_mm"] = round(float(both["obs"].sum()), 1)
        m["total_grid_mm"] = round(float(both["grid"].sum()), 1)
        out["precipitation"] = m
    return out


def validate_analysis(lat: float, lon: float, chirps_df: pd.DataFrame, era5_df: pd.DataFrame,
                      max_km: float = 150.0) -> Dict:
    """
    Cherche la station la plus proche ayant des données sur la période et compare.

    Returns:
        {"station": {...} | None, "series": DataFrame, "metrics": {...}, "message": str}
    """
    dates = pd.concat([chirps_df["date"], era5_df["date"]]) if not era5_df.empty else chirps_df["date"]
    start, end = dates.min().strftime("%Y-%m-%d"), dates.max().strftime("%Y-%m-%d")
    candidates = nearest_stations(load_stations(), lat, lon, n=3, max_km=max_km)
    if candidates.empty:
        return {"station": None, "series": pd.DataFrame(), "metrics": {},
                "message": f"Aucune station NOAA à moins de {max_km:.0f} km."}
    for _, st in candidates.iterrows():
        series = fetch_station_series(st["station"], start, end)
        if len(series.dropna(subset=["temperature_c"])) >= 5:
            return {"station": st.to_dict(), "series": series,
                    "metrics": compare_with_grids(series, chirps_df, era5_df), "message": ""}
    return {"station": None, "series": pd.DataFrame(), "metrics": {},
            "message": "Les stations proches n'ont pas de données sur cette période."}
