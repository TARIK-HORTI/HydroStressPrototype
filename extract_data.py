"""
extract_data.py
================
Extraction des données satellitaires (Sentinel-2, CHIRPS, ERA5-Land) et calcul
des indices spectraux pour l'analyse du stress hydrique au Maroc.

- Sentinel-2 : composite médian sans nuages sur la fenêtre (réflectances
  converties en [0, 1]), avec contrôle de la part de pixels valides.
- CHIRPS : précipitations quotidiennes au centroïde de la parcelle.
- ERA5-Land DAILY_AGGR : température moyenne / min / max journalières et
  humidité relative calculée depuis le point de rosée.
- Aucune valeur par défaut silencieuse : une source indisponible ou incomplète
  lève DataUnavailableError.
"""

from __future__ import annotations

import json
import logging
import math
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

try:
    import ee
except ImportError:  # mode démonstration sans Earth Engine (earthengine-api non installé)
    ee = None
import numpy as np
import pandas as pd
from shapely.geometry import Polygon

from region import ZONES, validate_in_region, zone_for_point

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------
SENTINEL2_COLLECTION = "COPERNICUS/S2_SR_HARMONIZED"
CHIRPS_COLLECTION = "UCSB-CHG/CHIRPS/DAILY"
ERA5_COLLECTION = "ECMWF/ERA5_LAND/DAILY_AGGR"
SRTM_IMAGE = "USGS/SRTMGL1_003"
CLIMATOLOGY_YEARS = (1991, 2020)

# Classes SCL Sentinel-2 conservées : 4 = végétation, 5 = sol nu
SCL_VALID_CLASSES = [4, 5]

# Facteur d'échelle des réflectances S2 L2A (DN -> réflectance)
S2_REFLECTANCE_SCALE = 1e-4

# Part minimale de pixels valides (non nuageux) sur la parcelle
MIN_VALID_PIXEL_FRACTION = 0.3

# Seuil maximal de surface d'une parcelle (km²)
MAX_PARCEL_AREA_KM2 = 10.0

# Facteur de correction du sol pour SAVI
SAVI_L = 0.5

# Fenêtre des features météo utilisées par le modèle (jours)
WEATHER_WINDOW_DAYS = 30

# Part minimale de jours présents dans une série météo
MIN_WEATHER_COMPLETENESS = 0.8

EE_SCOPES = [
    "https://www.googleapis.com/auth/earthengine",
    "https://www.googleapis.com/auth/cloud-platform",
]


class DataUnavailableError(RuntimeError):
    """Une source de données est indisponible ou trop incomplète."""


# ---------------------------------------------------------------------------
# Authentification Earth Engine
# ---------------------------------------------------------------------------
def parse_service_account_secrets(secrets) -> Optional[dict]:
    """
    Extrait le compte de service des secrets Streamlit. Deux formats acceptés :

    - GCP_SERVICE_ACCOUNT_JSON = '''{ ...contenu du fichier JSON collé tel quel... }'''
    - [GCP_SERVICE_ACCOUNT] : table TOML avec les champs du JSON
    """
    if "GCP_SERVICE_ACCOUNT_JSON" in secrets:
        raw = secrets["GCP_SERVICE_ACCOUNT_JSON"]
        info = json.loads(raw, strict=False) if isinstance(raw, str) else dict(raw)
        return info
    if "GCP_SERVICE_ACCOUNT" in secrets:
        return dict(secrets["GCP_SERVICE_ACCOUNT"])
    return None


def _service_account_from_streamlit() -> Optional[dict]:
    """Lit le compte de service dans st.secrets s'il est configuré."""
    try:
        import streamlit as st
        return parse_service_account_secrets(st.secrets)
    except FileNotFoundError:
        return None
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Secret GCP_SERVICE_ACCOUNT_JSON invalide : collez le contenu complet du fichier JSON ({e})."
        ) from e
    except Exception:
        return None


def _service_account_from_env() -> Optional[dict]:
    """
    Compte de service via l'environnement (serveur, Docker, Cloud Run) :
    EE_SERVICE_ACCOUNT_JSON (contenu JSON brut, p. ex. injecté depuis Secret Manager),
    sinon un fichier désigné par EE_SERVICE_ACCOUNT_FILE ou GOOGLE_APPLICATION_CREDENTIALS.
    """
    raw = os.environ.get("EE_SERVICE_ACCOUNT_JSON", "").strip()
    if raw:
        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            raise ValueError(f"EE_SERVICE_ACCOUNT_JSON invalide : JSON attendu ({e}).") from e
    for var in ("EE_SERVICE_ACCOUNT_FILE", "GOOGLE_APPLICATION_CREDENTIALS"):
        path = os.environ.get(var)
        if path and os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    return None


def initialize_earth_engine() -> str:
    """
    Initialise Earth Engine, dans cet ordre :
    1. Compte de service dans st.secrets (GCP_SERVICE_ACCOUNT_JSON ou
       [GCP_SERVICE_ACCOUNT], Streamlit Cloud)
    2. Variable EE_SERVICE_ACCOUNT_JSON (JSON brut) ou fichier via
       EE_SERVICE_ACCOUNT_FILE / GOOGLE_APPLICATION_CREDENTIALS
    3. Identifiants utilisateur de `earthengine authenticate` (projet via EE_PROJECT)

    Returns:
        str: méthode d'authentification utilisée
    """
    if ee is None:
        raise RuntimeError("earthengine-api n'est pas installé : pip install earthengine-api")
    info = _service_account_from_streamlit() or _service_account_from_env()
    if info:
        from google.oauth2 import service_account
        credentials = service_account.Credentials.from_service_account_info(info, scopes=EE_SCOPES)
        ee.Initialize(credentials=credentials, project=info["project_id"])
        logger.info("✓ Earth Engine initialisé (compte de service)")
        return "service_account"

    project = os.environ.get("EE_PROJECT")
    ee.Initialize(project=project) if project else ee.Initialize()
    logger.info("✓ Earth Engine initialisé (identifiants utilisateur)")
    return "user"


# ---------------------------------------------------------------------------
# Utilitaires
# ---------------------------------------------------------------------------
def polygon_area_km2(poly: Polygon) -> float:
    """Surface approximative (km²) d'un polygone en degrés, corrigée de la latitude."""
    lat = poly.centroid.y
    km_per_deg_lat = 111.32
    km_per_deg_lon = 111.32 * math.cos(math.radians(lat))
    return poly.area * km_per_deg_lat * km_per_deg_lon


def validate_geometry(coordinates: List[List[float]], require_region: bool = True) -> Polygon:
    """
    Valide et retourne un polygone Shapely à partir des coordonnées GeoJSON.

    Vérifie : au moins 3 sommets, pas d'auto-intersection, surface
    < MAX_PARCEL_AREA_KM2 et, par défaut, appartenance au Maroc.

    Args:
        coordinates: Liste de [lon, lat] au format GeoJSON
        require_region: Impose que la parcelle soit dans la zone d'étude

    Returns:
        Polygon: Géométrie validée

    Raises:
        ValueError: Si la géométrie est invalide, trop grande ou hors zone
    """
    if coordinates and coordinates[0] != coordinates[-1]:
        coordinates = coordinates + [coordinates[0]]

    if len(coordinates) < 4:
        raise ValueError(
            f"Polygone invalide : {len(coordinates) - 1} sommet(s), minimum 3."
        )

    if require_region:
        validate_in_region(coordinates)

    poly = Polygon(coordinates)
    if not poly.is_valid:
        raise ValueError("Géométrie invalide : le polygone s'auto-intersecte.")

    area_km2 = polygon_area_km2(poly)
    if area_km2 > MAX_PARCEL_AREA_KM2:
        raise ValueError(
            f"Parcelle trop grande : {area_km2:.2f} km² (max {MAX_PARCEL_AREA_KM2} km²)."
        )

    logger.info(f"✓ Géométrie validée : {area_km2:.4f} km², {len(coordinates) - 1} sommets")
    return poly


def compute_humidity_relative(temperature_c: float, dewpoint_c: float) -> float:
    """
    Humidité relative (%) par la formule de Magnus-Tetens :
        HR = 100 * es(Td) / es(T),  es(T) = 6.112 * exp(17.67 T / (T + 243.5))
    """
    if np.isnan(temperature_c) or np.isnan(dewpoint_c):
        return float("nan")
    if temperature_c <= dewpoint_c:
        return 100.0
    es_t = 6.112 * np.exp((17.67 * temperature_c) / (temperature_c + 243.5))
    es_td = 6.112 * np.exp((17.67 * dewpoint_c) / (dewpoint_c + 243.5))
    return float(np.clip(100.0 * es_td / es_t, 0.0, 100.0))


def day_of_year_cyclic(date: datetime) -> Tuple[float, float]:
    """Encode le jour de l'année en (sin, cos) sur un cycle de 366 jours."""
    angle = 2 * np.pi * date.timetuple().tm_yday / 366.0
    return float(np.sin(angle)), float(np.cos(angle))


def max_consecutive_dry_days(precip: pd.Series, threshold: float = 0.1) -> int:
    """Plus longue séquence de jours avec précipitation <= threshold."""
    longest = current = 0
    for dry in (precip <= threshold):
        current = current + 1 if dry else 0
        longest = max(longest, current)
    return longest


def check_completeness(df: pd.DataFrame, expected_days: int, source: str) -> None:
    """Lève DataUnavailableError si la série contient trop peu de jours."""
    if df.empty or len(df) < MIN_WEATHER_COMPLETENESS * expected_days:
        raise DataUnavailableError(
            f"{source} : {len(df)} jour(s) disponibles sur {expected_days} attendus. "
            f"Les données récentes peuvent ne pas être encore publiées : "
            f"choisissez une date d'analyse plus ancienne."
        )


# ---------------------------------------------------------------------------
# Sentinel-2
# ---------------------------------------------------------------------------
class SentinelDataExtractor:
    """Extraction et traitement des données Sentinel-2 depuis Google Earth Engine."""

    def create_geometry(self, coordinates: List[List[float]]) -> ee.Geometry:
        return ee.Geometry.Polygon(coordinates)

    def get_sentinel2_collection(
        self,
        geometry: ee.Geometry,
        start_date: str,
        end_date: str,
        max_cloud: float = 40.0,
    ) -> ee.ImageCollection:
        """Collection Sentinel-2 filtrée par date, emprise et couverture nuageuse de la tuile."""
        return (
            ee.ImageCollection(SENTINEL2_COLLECTION)
            .filterBounds(geometry)
            .filterDate(start_date, end_date)
            .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", max_cloud))
        )

    def mask_and_scale(self, image: ee.Image) -> ee.Image:
        """
        Masque nuages/ombres via la bande SCL (classes 4 et 5 conservées) et
        convertit les bandes optiques en réflectance [0, 1].
        """
        scl = image.select("SCL")
        mask = scl.eq(SCL_VALID_CLASSES[0]).Or(scl.eq(SCL_VALID_CLASSES[1]))
        optical = (
            image.select(["B2", "B4", "B8", "B11"])
            .multiply(S2_REFLECTANCE_SCALE)
        )
        return ee.Image(optical.updateMask(mask).copyProperties(image, ["system:time_start"]))

    def build_composite(self, collection: ee.ImageCollection) -> ee.Image:
        """Composite médian des images masquées de la fenêtre."""
        return collection.map(self.mask_and_scale).median()

    def calculate_ndvi(self, image: ee.Image) -> ee.Image:
        """NDVI = (NIR - Red) / (NIR + Red)"""
        return image.normalizedDifference(["B8", "B4"]).rename("NDVI")

    def calculate_ndwi(self, image: ee.Image) -> ee.Image:
        """NDWI (Gao) = (NIR - SWIR) / (NIR + SWIR)"""
        return image.normalizedDifference(["B8", "B11"]).rename("NDWI")

    def calculate_msi(self, image: ee.Image) -> ee.Image:
        """MSI = SWIR / NIR (valeurs élevées = stress hydrique)"""
        return image.select("B11").divide(image.select("B8")).rename("MSI")

    def calculate_savi(self, image: ee.Image, L: float = SAVI_L) -> ee.Image:
        """SAVI = ((NIR - Red) / (NIR + Red + L)) * (1 + L), réflectances en [0, 1]."""
        nir = image.select("B8")
        red = image.select("B4")
        return nir.subtract(red).multiply(1 + L).divide(nir.add(red).add(L)).rename("SAVI")

    def calculate_evi(self, image: ee.Image) -> ee.Image:
        """EVI = 2.5 * (NIR - Red) / (NIR + 6*Red - 7.5*Blue + 1), réflectances en [0, 1]."""
        nir = image.select("B8")
        red = image.select("B4")
        blue = image.select("B2")
        den = nir.add(red.multiply(6)).subtract(blue.multiply(7.5)).add(1).max(0.1)
        return nir.subtract(red).multiply(2.5).divide(den).rename("EVI")

    def compute_indices(self, image: ee.Image) -> ee.Image:
        """Retourne une image contenant les 5 indices spectraux."""
        return ee.Image.cat([
            self.calculate_ndvi(image),
            self.calculate_ndwi(image),
            self.calculate_msi(image),
            self.calculate_savi(image),
            self.calculate_evi(image),
        ])

    def valid_pixel_fraction(self, composite: ee.Image, geometry: ee.Geometry, scale: int = 10) -> float:
        """Part des pixels de la parcelle qui ont au moins une observation valide."""
        valid = composite.select("B8").mask().gt(0).rename("valid")
        stats = valid.unmask(0).reduceRegion(
            reducer=ee.Reducer.mean(), geometry=geometry, scale=scale,
            maxPixels=1e9, bestEffort=True,
        ).getInfo()
        return float(stats.get("valid") or 0.0)

    def extract_statistics(
        self,
        indices: ee.Image,
        geometry: ee.Geometry,
        scale: int = 10,
    ) -> Dict[str, Dict[str, float]]:
        """Moyenne, min, max et écart-type de chaque indice sur la parcelle (un seul appel)."""
        reducer = (
            ee.Reducer.mean()
            .combine(ee.Reducer.minMax(), sharedInputs=True)
            .combine(ee.Reducer.stdDev(), sharedInputs=True)
        )
        info = indices.reduceRegion(
            reducer=reducer, geometry=geometry, scale=scale,
            maxPixels=1e9, bestEffort=True,
        ).getInfo()

        stats = {}
        for idx in ["NDVI", "NDWI", "MSI", "SAVI", "EVI"]:
            values = {k: info.get(f"{idx}_{k}") for k in ["mean", "min", "max", "stdDev"]}
            if any(v is None for v in values.values()):
                raise DataUnavailableError(f"Sentinel-2 : aucune valeur valide pour {idx} sur la parcelle.")
            stats[idx] = {k: float(v) for k, v in values.items()}

        logger.info("✓ Statistiques Sentinel-2 extraites")
        return stats


# ---------------------------------------------------------------------------
# CHIRPS
# ---------------------------------------------------------------------------
class CHIRPSExtractor:
    """Précipitations CHIRPS quotidiennes via Earth Engine."""

    def get_precipitation_series(self, geometry: ee.Geometry, start_date: str, end_date: str) -> pd.DataFrame:
        """
        Série quotidienne [date, precipitation_mm] entre start_date (inclus)
        et end_date (exclu).
        """
        col = (
            ee.ImageCollection(CHIRPS_COLLECTION)
            .filterBounds(geometry)
            .filterDate(start_date, end_date)
        )

        def extract_feature(img):
            precip = img.reduceRegion(
                reducer=ee.Reducer.first(), geometry=geometry, scale=5000, maxPixels=1e9,
            ).get("precipitation")
            return ee.Feature(None, {"date": img.date().format("YYYY-MM-dd"), "precipitation_mm": precip})

        try:
            features = col.map(extract_feature).getInfo()
        except Exception as e:
            raise DataUnavailableError(f"CHIRPS : erreur Earth Engine ({e})") from e

        rows = [
            {"date": pd.to_datetime(f["properties"]["date"]),
             "precipitation_mm": float(f["properties"]["precipitation_mm"])}
            for f in features.get("features", [])
            if f["properties"].get("precipitation_mm") is not None
        ]
        df = pd.DataFrame(rows, columns=["date", "precipitation_mm"])
        df = df.sort_values("date").reset_index(drop=True)
        logger.info(f"✓ CHIRPS : {len(df)} jours extraits")
        return df

    def aggregate_features(self, df: pd.DataFrame) -> Dict[str, float]:
        """
        Features sur les WEATHER_WINDOW_DAYS derniers jours de la série :
        cumul 30 j, cumul 7 j, moyenne journalière, jours secs consécutifs max,
        nombre de jours de pluie (> 0.1 mm).
        """
        if df.empty:
            raise DataUnavailableError("CHIRPS : série vide.")
        window = df.tail(WEATHER_WINDOW_DAYS)
        precip = window["precipitation_mm"]
        return {
            "precipitation_total_30j": float(precip.sum()),
            "precipitation_total_7j": float(precip.tail(7).sum()),
            "precipitation_mean": float(precip.mean()),
            "max_consecutive_dry_days": float(max_consecutive_dry_days(precip)),
            "rainy_days_count": float((precip > 0.1).sum()),
        }


# ---------------------------------------------------------------------------
# ERA5-Land
# ---------------------------------------------------------------------------
class ERA5Extractor:
    """Température et humidité ERA5-Land (agrégats journaliers)."""

    BANDS = ["temperature_2m", "temperature_2m_min", "temperature_2m_max", "dewpoint_temperature_2m"]

    def get_climate_series(self, geometry: ee.Geometry, start_date: str, end_date: str) -> pd.DataFrame:
        """
        Série quotidienne [date, temperature_c, temperature_min_c, temperature_max_c,
        dewpoint_c, humidity_percent, humidity_min_percent].

        humidity_min_percent est estimée avec la température max du jour et le
        point de rosée moyen (approximation usuelle FAO-56).
        """
        col = (
            ee.ImageCollection(ERA5_COLLECTION)
            .filterBounds(geometry)
            .filterDate(start_date, end_date)
            .select(self.BANDS)
        )

        def extract_feature(img):
            stats = img.reduceRegion(
                reducer=ee.Reducer.first(), geometry=geometry, scale=11000, maxPixels=1e9,
            )
            props = {b: stats.get(b) for b in self.BANDS}
            props["date"] = img.date().format("YYYY-MM-dd")
            return ee.Feature(None, props)

        try:
            features = col.map(extract_feature).getInfo()
        except Exception as e:
            raise DataUnavailableError(f"ERA5-Land : erreur Earth Engine ({e})") from e

        rows = []
        for feat in features.get("features", []):
            p = feat["properties"]
            if any(p.get(b) is None for b in self.BANDS):
                continue
            t, tmin, tmax, td = (float(p[b]) - 273.15 for b in self.BANDS)
            rows.append({
                "date": pd.to_datetime(p["date"]),
                "temperature_c": t,
                "temperature_min_c": tmin,
                "temperature_max_c": tmax,
                "dewpoint_c": td,
                "humidity_percent": compute_humidity_relative(t, td),
                "humidity_min_percent": compute_humidity_relative(tmax, td),
            })

        columns = ["date", "temperature_c", "temperature_min_c", "temperature_max_c",
                   "dewpoint_c", "humidity_percent", "humidity_min_percent"]
        df = pd.DataFrame(rows, columns=columns).sort_values("date").reset_index(drop=True)
        logger.info(f"✓ ERA5-Land : {len(df)} jours extraits")
        return df

    def aggregate_features(self, df: pd.DataFrame) -> Dict[str, float]:
        """Features sur les WEATHER_WINDOW_DAYS derniers jours de la série."""
        if df.empty:
            raise DataUnavailableError("ERA5-Land : série vide.")
        window = df.tail(WEATHER_WINDOW_DAYS)
        return {
            "temperature_mean": float(window["temperature_c"].mean()),
            "temperature_max": float(window["temperature_max_c"].max()),
            "temperature_min": float(window["temperature_min_c"].min()),
            "humidity_mean": float(window["humidity_percent"].mean()),
            "humidity_min": float(window["humidity_min_percent"].min()),
        }


# ---------------------------------------------------------------------------
# Assemblage
# ---------------------------------------------------------------------------
def assemble_features(
    sentinel_stats: Dict[str, Dict[str, float]],
    chirps_features: Dict[str, float],
    era5_features: Dict[str, float],
    date: datetime,
    site_features: Dict[str, float],
) -> Dict[str, float]:
    """
    Construit le vecteur des 26 features attendu par le modèle.

    site_features : caractéristiques fixes du site (elevation_m,
    precip_annual_normal_mm) qui situent la parcelle dans son climat.
    """
    sin_doy, cos_doy = day_of_year_cyclic(date)
    s = sentinel_stats
    return {
        "NDVI_mean": s["NDVI"]["mean"],
        "NDWI_mean": s["NDWI"]["mean"],
        "MSI_mean": s["MSI"]["mean"],
        "SAVI_mean": s["SAVI"]["mean"],
        "EVI_mean": s["EVI"]["mean"],
        "NDVI_min": s["NDVI"]["min"],
        "NDVI_max": s["NDVI"]["max"],
        "NDVI_std": s["NDVI"]["stdDev"],
        "NDWI_std": s["NDWI"]["stdDev"],
        "MSI_min": s["MSI"]["min"],
        "MSI_max": s["MSI"]["max"],
        "MSI_std": s["MSI"]["stdDev"],
        **chirps_features,
        **era5_features,
        "day_of_year_sin": sin_doy,
        "day_of_year_cos": cos_doy,
        "elevation_m": float(site_features["elevation_m"]),
        "precip_annual_normal_mm": float(site_features["precip_annual_normal_mm"]),
    }


def get_site_features(point: ee.Geometry) -> Dict[str, float]:
    """
    Altitude (SRTM 30 m) et cumul annuel moyen de pluie CHIRPS 1991-2020 au
    centroïde de la parcelle, en un seul appel Earth Engine.
    """
    y0, y1 = CLIMATOLOGY_YEARS
    rain_normal = (
        ee.ImageCollection(CHIRPS_COLLECTION)
        .filterDate(f"{y0}-01-01", f"{y1 + 1}-01-01")
        .select("precipitation").sum().divide(y1 - y0 + 1).rename("rain")
    )
    elev = ee.Image(SRTM_IMAGE).select("elevation").rename("elev")
    info = ee.Dictionary({
        "elev": elev.reduceRegion(ee.Reducer.first(), point, 30).get("elev"),
        "rain": rain_normal.reduceRegion(ee.Reducer.first(), point, 5000).get("rain"),
    }).getInfo()
    if info.get("elev") is None or info.get("rain") is None:
        raise DataUnavailableError("Altitude ou normale de pluie indisponible pour ce site.")
    return {"elevation_m": float(info["elev"]), "precip_annual_normal_mm": float(info["rain"])}


class DataPipeline:
    """Combine Sentinel-2, CHIRPS et ERA5-Land en un vecteur de features."""

    def __init__(self, initialize: bool = True):
        if initialize:
            initialize_earth_engine()
        self.sentinel = SentinelDataExtractor()
        self.chirps = CHIRPSExtractor()
        self.era5 = ERA5Extractor()
        logger.info("✓ Pipeline de données initialisé")

    def extract_sentinel(
        self, ee_geometry: ee.Geometry, end_dt: datetime, lookback_days: int
    ) -> Tuple[Dict[str, Dict[str, float]], int, float, int]:
        """
        Composite Sentinel-2 sur la fenêtre ; élargit à 60 jours si aucune image
        ou trop de pixels masqués.

        Returns:
            (stats, nombre d'images, part de pixels valides, fenêtre utilisée)
        """
        end_str = (end_dt + timedelta(days=1)).strftime("%Y-%m-%d")
        for window in sorted({lookback_days, max(lookback_days, 60)}):
            start_str = (end_dt - timedelta(days=window)).strftime("%Y-%m-%d")
            collection = self.sentinel.get_sentinel2_collection(ee_geometry, start_str, end_str)
            count = collection.size().getInfo()
            logger.info(f"Sentinel-2 : {count} image(s) sur {window} jours")
            if count == 0:
                continue
            composite = self.sentinel.build_composite(collection)
            fraction = self.sentinel.valid_pixel_fraction(composite, ee_geometry)
            if fraction < MIN_VALID_PIXEL_FRACTION:
                logger.warning(f"Sentinel-2 : seulement {fraction:.0%} de pixels valides")
                continue
            stats = self.sentinel.extract_statistics(self.sentinel.compute_indices(composite), ee_geometry)
            return stats, count, fraction, window

        raise DataUnavailableError(
            "Sentinel-2 : pas assez d'images sans nuages sur la parcelle, même sur 60 jours."
        )

    def extract_all_data(
        self,
        coordinates: List[List[float]],
        analysis_date: str,
        lookback_days: int = 30,
    ) -> Dict[str, Any]:
        """
        Extrait toutes les données pour une parcelle et une date.

        Args:
            coordinates: Coordonnées GeoJSON [lon, lat]
            analysis_date: Date d'analyse (YYYY-MM-DD), incluse
            lookback_days: Fenêtre du composite Sentinel-2 et des graphiques météo.
                Les features météo du modèle portent toujours sur 30 jours.
        """
        logger.info(f"Extraction des données pour le {analysis_date}")
        validate_geometry(coordinates)

        end_dt = datetime.strptime(analysis_date, "%Y-%m-%d")
        weather_days = max(lookback_days, WEATHER_WINDOW_DAYS)
        weather_start = (end_dt - timedelta(days=weather_days - 1)).strftime("%Y-%m-%d")
        end_exclusive = (end_dt + timedelta(days=1)).strftime("%Y-%m-%d")

        ee_geometry = self.sentinel.create_geometry(coordinates)
        centroid = ee_geometry.centroid(maxError=1)

        sentinel_stats, s2_count, valid_fraction, s2_window = self.extract_sentinel(
            ee_geometry, end_dt, lookback_days
        )

        chirps_df = self.chirps.get_precipitation_series(centroid, weather_start, end_exclusive)
        check_completeness(chirps_df.tail(WEATHER_WINDOW_DAYS), WEATHER_WINDOW_DAYS, "CHIRPS")
        chirps_features = self.chirps.aggregate_features(chirps_df)

        era5_df = self.era5.get_climate_series(centroid, weather_start, end_exclusive)
        check_completeness(era5_df.tail(WEATHER_WINDOW_DAYS), WEATHER_WINDOW_DAYS, "ERA5-Land")
        era5_features = self.era5.aggregate_features(era5_df)

        site = get_site_features(centroid)
        features = assemble_features(sentinel_stats, chirps_features, era5_features, end_dt, site)

        lons = [c[0] for c in coordinates]
        lats = [c[1] for c in coordinates]
        zone_id, place, zone_km = zone_for_point(sum(lats) / len(lats), sum(lons) / len(lons))

        logger.info("✓ Extraction complète et assemblée")
        return {
            "features": features,
            "sentinel_stats": sentinel_stats,
            "sentinel_meta": {
                "image_count": s2_count,
                "valid_pixel_fraction": valid_fraction,
                "window_days": s2_window,
            },
            "chirps_series": chirps_df,
            "era5_series": era5_df,
            "extraction_date": datetime.now().isoformat(),
            "date_analyzed": analysis_date,
            "lookback_days": lookback_days,
            "zone": {"id": zone_id, "name": ZONES[zone_id]["name"], "nearest_place": place,
                     "distance_km": round(zone_km, 1)},
        }


if __name__ == "__main__":
    print("Pipeline d'extraction HydroStress (Maroc).")
