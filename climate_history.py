"""
climate_history.py
==================
Téléchargement de l'historique climatique quotidien d'un point (sans compte,
sans Earth Engine) et calcul des features météo du modèle.

Sources (gratuites, sans clé) :
- Open-Meteo Archive (défaut) : réanalyse ERA5-Land ~9 km, 1950 -> J-5,
  avec l'ET0 FAO Penman-Monteith calculée par Open-Meteo.
  https://open-meteo.com/en/docs/historical-weather-api
- NASA POWER (secours) : MERRA-2 / satellite ~50 km, 1981 -> présent.
  L'ET0 est alors estimée par la formule de Hargreaves.
  https://power.larc.nasa.gov/docs/services/api/temporal/daily/

Colonnes de la série quotidienne produite :
    date, precipitation_mm, temperature_c, temperature_min_c, temperature_max_c,
    humidity_percent, humidity_min_percent, et0_mm

Les features météo sont calculées exactement comme pour l'analyse en ligne
(extract_data.CHIRPSExtractor / ERA5Extractor), sur les 30 jours qui
précèdent la date (incluse).
"""

import logging
import math
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, Optional

import pandas as pd
import requests

from extract_data import (
    WEATHER_WINDOW_DAYS,
    CHIRPSExtractor,
    DataUnavailableError,
    ERA5Extractor,
    check_completeness,
    compute_humidity_relative,
)

logger = logging.getLogger(__name__)

OPEN_METEO_URL = "https://archive-api.open-meteo.com/v1/archive"
NASA_POWER_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
TIMEOUT_S = 60
RETRIES = 4

COLUMNS = ["date", "precipitation_mm", "temperature_c", "temperature_min_c", "temperature_max_c",
           "humidity_percent", "humidity_min_percent", "et0_mm"]

OPEN_METEO_DAILY = {
    "precipitation_sum": "precipitation_mm",
    "temperature_2m_mean": "temperature_c",
    "temperature_2m_min": "temperature_min_c",
    "temperature_2m_max": "temperature_max_c",
    "relative_humidity_2m_mean": "humidity_percent",
    "relative_humidity_2m_min": "humidity_min_percent",
    "et0_fao_evapotranspiration": "et0_mm",
}


def _get_json(url: str, params: Dict, session=None) -> Dict:
    http = session or requests
    last_error = None
    for attempt in range(RETRIES):
        try:
            resp = http.get(url, params=params, timeout=TIMEOUT_S)
            if resp.status_code == 429 or resp.status_code >= 500:
                raise requests.HTTPError(f"HTTP {resp.status_code}")
            resp.raise_for_status()
            return resp.json()
        except (requests.RequestException, ValueError) as e:
            last_error = e
            wait = 2 ** (attempt + 1)
            logger.warning(f"{url} : échec ({e}), nouvel essai dans {wait} s")
            if session is None:
                time.sleep(wait)
    raise DataUnavailableError(f"Téléchargement impossible depuis {url} : {last_error}")


def fetch_open_meteo(lat: float, lon: float, start: str, end: str, session=None,
                     model: str = "era5_land") -> pd.DataFrame:
    """
    Série quotidienne Open-Meteo. model="era5_land" garde la même réanalyse que
    l'analyse en ligne (ERA5-Land) ; si une variable manque, on retombe sur
    "best_match" (ERA5 + ERA5-Land).
    """
    params = {
        "latitude": round(lat, 4), "longitude": round(lon, 4),
        "start_date": start, "end_date": end,
        "daily": ",".join(OPEN_METEO_DAILY), "timezone": "Africa/Casablanca",
    }
    if model:
        params["models"] = model
    data = _get_json(OPEN_METEO_URL, params, session)
    daily = data.get("daily") or {}
    if not daily.get("time"):
        raise DataUnavailableError(f"Open-Meteo : réponse vide ({data.get('reason', 'sans détail')})")
    df = pd.DataFrame({"date": pd.to_datetime(daily["time"])})
    for api_name, col in OPEN_METEO_DAILY.items():
        df[col] = pd.to_numeric(pd.Series(daily.get(api_name, [None] * len(df))), errors="coerce")
    if model and df[COLUMNS[1:]].isna().all().any():
        logger.info("Open-Meteo : variable absente en ERA5-Land, utilisation de best_match")
        return fetch_open_meteo(lat, lon, start, end, session, model=None)
    df.attrs["elevation_m"] = data.get("elevation")
    df.attrs["source"] = f"Open-Meteo ({model or 'best_match'})"
    return df[COLUMNS]


def extraterrestrial_radiation_mm(lat: float, day_of_year: int) -> float:
    """Rayonnement extraterrestre Ra (FAO-56 éq. 21), converti en mm/jour d'eau évaporée."""
    phi = math.radians(lat)
    dr = 1 + 0.033 * math.cos(2 * math.pi * day_of_year / 365)
    delta = 0.409 * math.sin(2 * math.pi * day_of_year / 365 - 1.39)
    ws = math.acos(max(-1.0, min(1.0, -math.tan(phi) * math.tan(delta))))
    ra_mj = (24 * 60 / math.pi) * 0.0820 * dr * (
        ws * math.sin(phi) * math.sin(delta) + math.cos(phi) * math.cos(delta) * math.sin(ws))
    return 0.408 * ra_mj


def hargreaves_et0(lat: float, day: pd.Timestamp, tmean: float, tmin: float, tmax: float) -> float:
    ra = extraterrestrial_radiation_mm(lat, day.dayofyear)
    return max(0.0, 0.0023 * (tmean + 17.8) * math.sqrt(max(0.0, tmax - tmin)) * ra)


def fetch_nasa_power(lat: float, lon: float, start: str, end: str, session=None) -> pd.DataFrame:
    params = {
        "parameters": "PRECTOTCORR,T2M,T2M_MIN,T2M_MAX,RH2M,T2MDEW",
        "community": "AG", "latitude": round(lat, 4), "longitude": round(lon, 4),
        "start": start.replace("-", ""), "end": end.replace("-", ""), "format": "JSON",
    }
    data = _get_json(NASA_POWER_URL, params, session)
    try:
        p = data["properties"]["parameter"]
    except (KeyError, TypeError):
        raise DataUnavailableError(f"NASA POWER : réponse inattendue ({str(data)[:200]})")
    fill = (data.get("header") or {}).get("fill_value", -999)
    df = pd.DataFrame({k: pd.Series(v) for k, v in p.items()})
    df = df.replace(fill, float("nan"))
    df.index = pd.to_datetime(df.index, format="%Y%m%d")
    out = pd.DataFrame({
        "date": df.index,
        "precipitation_mm": df["PRECTOTCORR"].values,
        "temperature_c": df["T2M"].values,
        "temperature_min_c": df["T2M_MIN"].values,
        "temperature_max_c": df["T2M_MAX"].values,
        "humidity_percent": df["RH2M"].values,
    })
    out["humidity_min_percent"] = [
        compute_humidity_relative(tmax, td) if pd.notna(tmax) and pd.notna(td) else float("nan")
        for tmax, td in zip(df["T2M_MAX"], df["T2MDEW"])
    ]
    out["et0_mm"] = [
        hargreaves_et0(lat, d, t, tn, tx) if pd.notna(t) and pd.notna(tn) and pd.notna(tx) else float("nan")
        for d, t, tn, tx in zip(out["date"], out["temperature_c"], out["temperature_min_c"], out["temperature_max_c"])
    ]
    coords = (data.get("geometry") or {}).get("coordinates") or []
    out.attrs["elevation_m"] = coords[2] if len(coords) > 2 else None
    out.attrs["source"] = "NASA POWER"
    return out[COLUMNS].reset_index(drop=True)


FETCHERS = {"open-meteo": fetch_open_meteo, "nasa-power": fetch_nasa_power}


def download_climate(lat: float, lon: float, start: str, end: str, source: str = "open-meteo",
                     cache_file: Optional[str] = None, session=None) -> pd.DataFrame:
    """
    Télécharge la série quotidienne année par année (requêtes courtes, reprise
    possible) et l'enregistre en CSV. Si cache_file existe et couvre déjà la
    période, il est relu sans rien télécharger.
    """
    if cache_file and Path(cache_file).exists():
        cached = pd.read_csv(cache_file, parse_dates=["date"])
        if not cached.empty and cached["date"].min() <= pd.Timestamp(start) and cached["date"].max() >= pd.Timestamp(end):
            logger.info(f"Climat relu depuis {cache_file}")
            return cached[(cached["date"] >= start) & (cached["date"] <= end)].reset_index(drop=True)

    # Les archives s'arrêtent quelques jours avant aujourd'hui
    last_available = date.today() - timedelta(days=6)
    end_d = min(datetime.strptime(end, "%Y-%m-%d").date(), last_available)
    start_d = datetime.strptime(start, "%Y-%m-%d").date()
    if start_d > end_d:
        raise ValueError(f"Période vide : {start} -> {end_d}")

    fetch = FETCHERS[source]
    parts, meta = [], {}
    for year in range(start_d.year, end_d.year + 1):
        y0 = max(start_d, date(year, 1, 1))
        y1 = min(end_d, date(year, 12, 31))
        logger.info(f"{source} : {y0} -> {y1}")
        part = fetch(lat, lon, y0.isoformat(), y1.isoformat(), session=session)
        meta = part.attrs or meta
        parts.append(part)
    df = pd.concat(parts, ignore_index=True).drop_duplicates("date").sort_values("date").reset_index(drop=True)
    df.attrs = meta

    missing = df[COLUMNS[1:]].isna().mean()
    for col, frac in missing.items():
        if frac > 0.05:
            logger.warning(f"{col} : {frac:.0%} de jours manquants")

    if cache_file:
        Path(cache_file).parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(cache_file, index=False)
        logger.info(f"✓ {len(df)} jours enregistrés dans {cache_file} ({meta.get('source', source)})")
    return df


def weather_features(daily: pd.DataFrame, on: pd.Timestamp) -> Dict[str, float]:
    """Les 10 features météo du modèle sur les 30 jours finissant à `on` (inclus)."""
    on = pd.Timestamp(on)
    window = daily[(daily["date"] > on - pd.Timedelta(days=WEATHER_WINDOW_DAYS)) & (daily["date"] <= on)]
    window = window.dropna(subset=COLUMNS[1:7])
    check_completeness(window, WEATHER_WINDOW_DAYS, "Climat téléchargé")
    feats = CHIRPSExtractor().aggregate_features(window[["date", "precipitation_mm"]])
    feats.update(ERA5Extractor().aggregate_features(window))
    return feats


def annual_rain_normal(daily: pd.DataFrame) -> float:
    """Cumul annuel moyen sur les années complètes de la série (remplace la normale CHIRPS sans Earth Engine)."""
    d = daily.dropna(subset=["precipitation_mm"])
    counts = d.groupby(d["date"].dt.year)["precipitation_mm"].agg(["sum", "count"])
    full = counts[counts["count"] >= 360]
    if full.empty:
        raise DataUnavailableError("Pas d'année complète pour calculer la pluie annuelle moyenne.")
    return float(full["sum"].mean())
