"""
extract_data.py
================
Module d'extraction des données satellitaires (Sentinel-2, CHIRPS, ERA5-Land)
et calcul des indices spectraux pour l'analyse du stress hydrique.

Fonctionnalités corrigées :
- Extraction Sentinel-2 (B2, B3, B4, B5, B8, B11, B12) avec masquage SCL strict
- Calcul des indices : NDVI, NDWI, MSI, SAVI, EVI
- CHIRPS via Earth Engine avec réduction côté serveur
- ERA5-Land DAILY avec calcul de l'humidité relative depuis le point de rosée
- Feature engineering temporel (cumuls, jours secs, cyclicité journalière)
- Validation des géométries avec Shapely
- Paramètres GEE sécurisés (maxPixels, bestEffort)
"""

import ee
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Any
import logging
from shapely.geometry import Polygon, mapping
from shapely.ops import unary_union

# Configuration du logging
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

# Classes SCL Sentinel-2 à conserver : 4=végétation, 5=sol nu
SCL_VALID_CLASSES = [4, 5]

# Seuil maximal de surface d'une parcelle (km²)
MAX_PARCEL_AREA_KM2 = 10.0

# Facteur de correction du sol pour SAVI (L=0.5 : couverture moyenne)
SAVI_L = 0.5


# ---------------------------------------------------------------------------
# Utilitaires
# ---------------------------------------------------------------------------
def validate_geometry(coordinates: List[List[float]]) -> Polygon:
    """
    Valide et retourne un polygone Shapely à partir des coordonnées GeoJSON.

    Vérifie :
    - Au moins 3 points distincts
    - Polygone fermé (premier == dernier)
    - Pas d'auto-intersection
    - Surface < MAX_PARCEL_AREA_KM2

    Args:
        coordinates: Liste de [lon, lat] au format GeoJSON

    Returns:
        Polygon: Géométrie validée

    Raises:
        ValueError: Si la géométrie est invalide ou trop grande
    """
    if len(coordinates) < 4:
        raise ValueError(
            f"Polygone invalide : {len(coordinates)} points (minimum 4 pour un polygone fermé)."
        )

    # Vérifie que le polygone est fermé
    if coordinates[0] != coordinates[-1]:
        coordinates = coordinates + [coordinates[0]]

    # Création du polygone Shapely (attention : GeoJSON = lon,lat ; Shapely = x,y)
    poly = Polygon(coordinates)

    if not poly.is_valid:
        # Tente de réparer les auto-intersections
        poly = unary_union(poly)
        if not poly.is_valid:
            raise ValueError("Géométrie invalide : auto-intersection détectée et non réparable.")

    area_km2 = poly.area * 111.32 * 111.32  # approximation grossière en km²
    if area_km2 > MAX_PARCEL_AREA_KM2:
        raise ValueError(
            f"Parcelle trop grande : {area_km2:.2f} km² (max {MAX_PARCEL_AREA_KM2} km²)."
        )

    logger.info(f"✓ Géométrie validée : {area_km2:.4f} km², {len(coordinates)} points")
    return poly


def compute_humidity_relative(temperature_c: float, dewpoint_c: float) -> float:
    """
    Calcule l'humidité relative (%) depuis la température et le point de rosée.

    Formule de Magnus-Tetens :
        HR = 100 * es(Td) / es(T)
        es(T) = 6.112 * exp((17.67 * T) / (T + 243.5))

    Args:
        temperature_c: Température à 2m (°C)
        dewpoint_c: Point de rosée à 2m (°C)

    Returns:
        float: Humidité relative en %, clampée entre [0, 100]
    """
    if temperature_c <= dewpoint_c:
        return 100.0

    es_t = 6.112 * np.exp((17.67 * temperature_c) / (temperature_c + 243.5))
    es_td = 6.112 * np.exp((17.67 * dewpoint_c) / (dewpoint_c + 243.5))
    hr = 100.0 * (es_td / es_t)
    return float(np.clip(hr, 0.0, 100.0))


def day_of_year_cyclic(date: datetime) -> tuple:
    """
    Encode le jour de l'année de manière cyclique via sin/cos.

    Cela permet au modèle de comprendre que le 31 décembre est proche
    du 1er janvier, ce qu'un entier brut ne capture pas.

    Args:
        date: Date à encoder

    Returns:
        tuple: (sin_component, cos_component)
    """
    doy = date.timetuple().tm_yday
    angle = 2 * np.pi * doy / 366.0
    return np.sin(angle), np.cos(angle)


# ---------------------------------------------------------------------------
# Sentinel-2
# ---------------------------------------------------------------------------
class SentinelDataExtractor:
    """
    Extraction et traitement des données Sentinel-2 depuis Google Earth Engine.
    """

    def __init__(self):
        """Initialise la connexion à Google Earth Engine."""
        try:
            ee.Initialize()
            logger.info("✓ Connexion Google Earth Engine établie")
        except Exception as e:
            logger.error(f"✗ Erreur connexion EE : {e}")
            raise RuntimeError("Impossible d'initialiser Earth Engine. "
                               "Exécutez 'earthengine authenticate'.") from e

    def create_geometry(self, coordinates: List[List[float]]) -> ee.Geometry:
        """
        Crée une géométrie Earth Engine à partir des coordonnées de la parcelle.

        Args:
            coordinates: Liste de [lon, lat] formant un polygone fermé

        Returns:
            ee.Geometry: Géométrie Earth Engine
        """
        return ee.Geometry.Polygon(coordinates)

    def get_sentinel2_collection(
        self,
        geometry: ee.Geometry,
        start_date: str,
        end_date: str,
        max_cloud: float = 20.0
    ) -> ee.ImageCollection:
        """
        Récupère la collection Sentinel-2 filtrée par date, localisation et couverture nuageuse.

        Args:
            geometry: Géométrie de la zone d'intérêt
            start_date: Date de début (YYYY-MM-DD)
            end_date: Date de fin (YYYY-MM-DD)
            max_cloud: Pourcentage maximal de nuages accepté

        Returns:
            ee.ImageCollection: Collection d'images Sentinel-2 filtrées
        """
        collection = (
            ee.ImageCollection(SENTINEL2_COLLECTION)
            .filterBounds(geometry)
            .filterDate(start_date, end_date)
            .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", max_cloud))
        )
        count = collection.size().getInfo()
        logger.info(f"Collection Sentinel-2 : {count} image(s) trouvée(s)")
        return collection

    def mask_clouds(self, image: ee.Image) -> ee.Image:
        """
        Masque les nuages, ombres et pixels non végétaux via la bande SCL.

        Classes SCL conservées :
        - 4 : Végétation
        - 5 : Sol nu

        Args:
            image: Image Sentinel-2 avec bande SCL

        Returns:
            ee.Image: Image avec masque appliqué
        """
        scl = image.select("SCL")
        # Masque binaire : 1 si classe dans [4, 5], sinon 0
        mask = scl.eq(4).Or(scl.eq(5))
        return image.updateMask(mask)

    def calculate_ndvi(self, image: ee.Image) -> ee.Image:
        """NDVI = (NIR - Red) / (NIR + Red)"""
        nir = image.select("B8")
        red = image.select("B4")
        ndvi = nir.subtract(red).divide(nir.add(red)).rename("NDVI")
        return ndvi

    def calculate_ndwi(self, image: ee.Image) -> ee.Image:
        """NDWI = (NIR - SWIR) / (NIR + SWIR)"""
        nir = image.select("B8")
        swir = image.select("B11")
        ndwi = nir.subtract(swir).divide(nir.add(swir)).rename("NDWI")
        return ndwi

    def calculate_msi(self, image: ee.Image) -> ee.Image:
        """MSI = SWIR / NIR (valeurs élevées = stress hydrique)"""
        swir = image.select("B11")
        nir = image.select("B8")
        msi = swir.divide(nir).rename("MSI")
        return msi

    def calculate_savi(self, image: ee.Image, L: float = SAVI_L) -> ee.Image:
        """
        SAVI = ((NIR - Red) / (NIR + Red + L)) * (1 + L)
        Corrige le NDVI pour l'effet du sol nu.
        """
        nir = image.select("B8")
        red = image.select("B4")
        num = nir.subtract(red).multiply(1 + L)
        den = nir.add(red).add(L)
        savi = num.divide(den).rename("SAVI")
        return savi

    def calculate_evi(self, image: ee.Image) -> ee.Image:
        """
        EVI = 2.5 * (NIR - Red) / (NIR + 6*Red - 7.5*Blue + 1)
        Moins saturé que NDVI pour couverture dense.
        """
        nir = image.select("B8")
        red = image.select("B4")
        blue = image.select("B2")

        num = nir.subtract(red).multiply(2.5)
        den = nir.add(red.multiply(6)).subtract(blue.multiply(7.5)).add(1)
        # Protection contre division par zéro ou valeurs négatives extrêmes
        den = den.max(0.1)
        evi = num.divide(den).rename("EVI")
        return evi

    def compute_indices(self, image: ee.Image) -> ee.Image:
        """
        Calcule tous les indices spectraux et les ajoute comme bandes.

        Args:
            image: Image Sentinel-2 avec nuages masqués

        Returns:
            ee.Image: Image enrichie des 5 indices spectraux
        """
        indices = [
            self.calculate_ndvi(image),
            self.calculate_ndwi(image),
            self.calculate_msi(image),
            self.calculate_savi(image),
            self.calculate_evi(image),
        ]
        return image.addBands(indices)

    def extract_statistics(
        self,
        image: ee.Image,
        geometry: ee.Geometry,
        scale: int = 10
    ) -> Dict[str, Dict[str, float]]:
        """
        Extrait les statistiques (moyenne, min, max, écart-type) des indices
        sur la parcelle via reduceRegion.

        Args:
            image: Image avec indices spectraux
            geometry: Géométrie de la parcelle
            scale: Résolution spatiale en mètres

        Returns:
            Dict: Statistiques par indice
        """
        indices = ["NDVI", "NDWI", "MSI", "SAVI", "EVI"]
        stats = {}

        reducer = (
            ee.Reducer.mean()
            .combine(ee.Reducer.minMax(), sharedInputs=True)
            .combine(ee.Reducer.stdDev(), sharedInputs=True)
        )

        for idx in indices:
            band = image.select(idx)
            result = band.reduceRegion(
                reducer=reducer,
                geometry=geometry,
                scale=scale,
                maxPixels=1e13,
                bestEffort=True,
            )
            info = result.getInfo()
            stats[idx] = {
                "mean": float(info.get(f"{idx}_mean", np.nan)),
                "min": float(info.get(f"{idx}_min", np.nan)),
                "max": float(info.get(f"{idx}_max", np.nan)),
                "stdDev": float(info.get(f"{idx}_stdDev", np.nan)),
            }

        logger.info("✓ Statistiques Sentinel-2 extraites")
        return stats


# ---------------------------------------------------------------------------
# CHIRPS
# ---------------------------------------------------------------------------
class CHIRPSExtractor:
    """
    Extraction des précipitations CHIRPS via Earth Engine avec réduction côté serveur.
    """

    def __init__(self):
        logger.info("✓ CHIRPSExtractor initialisé")

    def get_precipitation_series(
        self,
        geometry: ee.Geometry,
        start_date: str,
        end_date: str
    ) -> pd.DataFrame:
        """
        Récupère la série temporelle des précipitations CHIRPS quotidiennes.

        Args:
            geometry: Géométrie EE (point centroiïde recommandé)
            start_date: Date de début (YYYY-MM-DD)
            end_date: Date de fin (YYYY-MM-DD)

        Returns:
            pd.DataFrame: Colonnes [date, precipitation_mm]
        """
        try:
            col = (
                ee.ImageCollection(CHIRPS_COLLECTION)
                .filterBounds(geometry)
                .filterDate(start_date, end_date)
            )

            def extract_feature(img):
                date_str = img.date().format("YYYY-MM-dd")
                precip = img.reduceRegion(
                    reducer=ee.Reducer.first(),
                    geometry=geometry,
                    scale=5000,
                    maxPixels=1e9,
                ).get("precipitation")
                return ee.Feature(None, {"date": date_str, "precipitation_mm": precip})

            features = col.map(extract_feature).getInfo()
            rows = []
            for feat in features.get("features", []):
                props = feat["properties"]
                rows.append({
                    "date": pd.to_datetime(props["date"]),
                    "precipitation_mm": float(props.get("precipitation_mm", 0.0) or 0.0),
                })

            df = pd.DataFrame(rows).sort_values("date").reset_index(drop=True)
            logger.info(f"✓ CHIRPS : {len(df)} jours extraits")
            return df

        except Exception as e:
            logger.error(f"Erreur CHIRPS : {e}")
            return pd.DataFrame(columns=["date", "precipitation_mm"])

    def aggregate_features(self, df: pd.DataFrame) -> Dict[str, float]:
        """
        Calcule les features agrégées à partir de la série CHIRPS.

        Features :
        - precipitation_total_30j : cumul sur la fenêtre
        - precipitation_total_7j : cumul sur les 7 derniers jours
        - precipitation_mean : moyenne journalière
        - max_consecutive_dry_days : plus longue séquence sans pluie (>0.1mm)
        - rainy_days_count : nombre de jours avec pluie

        Args:
            df: DataFrame CHIRPS avec colonnes [date, precipitation_mm]

        Returns:
            Dict: Features agrégées
        """
        if df.empty:
            return {
                "precipitation_total_30j": 0.0,
                "precipitation_total_7j": 0.0,
                "precipitation_mean": 0.0,
                "max_consecutive_dry_days": 0.0,
                "rainy_days_count": 0.0,
            }

        total_30j = df["precipitation_mm"].sum()
        total_7j = df["precipitation_mm"].tail(7).sum() if len(df) >= 7 else total_30j
        mean_daily = df["precipitation_mm"].mean()
        rainy_days = (df["precipitation_mm"] > 0.1).sum()

        # Calcul des jours secs consécutifs maximum
        dry = (df["precipitation_mm"] <= 0.1).astype(int)
        max_dry = 0
        current = 0
        for val in dry:
            if val:
                current += 1
                max_dry = max(max_dry, current)
            else:
                current = 0

        return {
            "precipitation_total_30j": float(total_30j),
            "precipitation_total_7j": float(total_7j),
            "precipitation_mean": float(mean_daily),
            "max_consecutive_dry_days": float(max_dry),
            "rainy_days_count": float(rainy_days),
        }


# ---------------------------------------------------------------------------
# ERA5-Land
# ---------------------------------------------------------------------------
class ERA5Extractor:
    """
    Extraction des données ERA5-Land (température, point de rosée)
    et calcul de l'humidité relative.
    """

    def __init__(self):
        logger.info("✓ ERA5Extractor initialisé")

    def get_climate_series(
        self,
        geometry: ee.Geometry,
        start_date: str,
        end_date: str
    ) -> pd.DataFrame:
        """
        Récupère les données ERA5-Land quotidiennes.

        Bandes utilisées :
        - temperature_2m : température à 2m (K)
        - dewpoint_temperature_2m : point de rosée à 2m (K)

        L'humidité relative est calculée post-extraction.

        Args:
            geometry: Géométrie EE
            start_date: Date de début (YYYY-MM-DD)
            end_date: Date de fin (YYYY-MM-DD)

        Returns:
            pd.DataFrame: Colonnes [date, temperature_c, dewpoint_c, humidity_percent]
        """
        try:
            col = (
                ee.ImageCollection(ERA5_COLLECTION)
                .filterBounds(geometry)
                .filterDate(start_date, end_date)
                .select(["temperature_2m", "dewpoint_temperature_2m"])
            )

            def extract_feature(img):
                date_str = img.date().format("YYYY-MM-dd")
                stats = img.reduceRegion(
                    reducer=ee.Reducer.mean(),
                    geometry=geometry,
                    scale=10000,
                    maxPixels=1e9,
                )
                return ee.Feature(None, {
                    "date": date_str,
                    "temperature_2m": stats.get("temperature_2m"),
                    "dewpoint_temperature_2m": stats.get("dewpoint_temperature_2m"),
                })

            features = col.map(extract_feature).getInfo()
            rows = []
            for feat in features.get("features", []):
                props = feat["properties"]
                t_k = float(props.get("temperature_2m", np.nan))
                td_k = float(props.get("dewpoint_temperature_2m", np.nan))

                # Conversion Kelvin -> Celsius
                t_c = t_k - 273.15 if not np.isnan(t_k) else np.nan
                td_c = td_k - 273.15 if not np.isnan(td_k) else np.nan
                hr = compute_humidity_relative(t_c, td_c) if not np.isnan(t_c) else np.nan

                rows.append({
                    "date": pd.to_datetime(props["date"]),
                    "temperature_c": t_c,
                    "dewpoint_c": td_c,
                    "humidity_percent": hr,
                })

            df = pd.DataFrame(rows).sort_values("date").reset_index(drop=True)
            logger.info(f"✓ ERA5-Land : {len(df)} jours extraits")
            return df

        except Exception as e:
            logger.error(f"Erreur ERA5-Land : {e}")
            return pd.DataFrame(columns=["date", "temperature_c", "dewpoint_c", "humidity_percent"])

    def aggregate_features(self, df: pd.DataFrame) -> Dict[str, float]:
        """
        Agrège les données climatiques sur la fenêtre temporelle.

        Args:
            df: DataFrame ERA5 avec colonnes [date, temperature_c, humidity_percent]

        Returns:
            Dict: Features agrégées (moyennes, extrêmes)
        """
        if df.empty:
            return {
                "temperature_mean": 25.0,
                "temperature_max": 30.0,
                "temperature_min": 20.0,
                "humidity_mean": 60.0,
                "humidity_min": 40.0,
            }

        return {
            "temperature_mean": float(df["temperature_c"].mean()),
            "temperature_max": float(df["temperature_c"].max()),
            "temperature_min": float(df["temperature_c"].min()),
            "humidity_mean": float(df["humidity_percent"].mean()),
            "humidity_min": float(df["humidity_percent"].min()),
        }


# ---------------------------------------------------------------------------
# Pipeline global
# ---------------------------------------------------------------------------
class DataPipeline:
    """
    Pipeline complet d'extraction et d'agrégation des données.
    Combine Sentinel-2, CHIRPS et ERA5-Land en un vecteur de features unique.
    """

    def __init__(self):
        """Initialise les extracteurs."""
        self.sentinel = SentinelDataExtractor()
        self.chirps = CHIRPSExtractor()
        self.era5 = ERA5Extractor()
        logger.info("✓ Pipeline de données initialisé")

    def extract_all_data(
        self,
        coordinates: List[List[float]],
        analysis_date: str,
        lookback_days: int = 30
    ) -> Dict[str, Any]:
        """
        Extrait toutes les données pour une parcelle et une date donnée.

        Args:
            coordinates: Coordonnées GeoJSON [lon, lat] de la parcelle
            analysis_date: Date d'analyse (YYYY-MM-DD)
            lookback_days: Fenêtre temporelle en jours (défaut 30)

        Returns:
            Dict: Dictionnaire structuré avec toutes les features
        """
        logger.info(f"Extraction des données pour le {analysis_date}")

        # Validation de la géométrie
        shapely_poly = validate_geometry(coordinates)

        # Fenêtre temporelle
        end_dt = datetime.strptime(analysis_date, "%Y-%m-%d")
        start_dt = end_dt - timedelta(days=lookback_days)
        start_str = start_dt.strftime("%Y-%m-%d")
        end_str = end_dt.strftime("%Y-%m-%d")

        # Géométrie Earth Engine
        ee_geometry = self.sentinel.create_geometry(coordinates)
        centroid = ee_geometry.centroid()

        # -------------------------------------------------------------------
        # 1. Sentinel-2
        # -------------------------------------------------------------------
        s2_collection = self.sentinel.get_sentinel2_collection(
            ee_geometry, start_str, end_str
        )

        s2_count = s2_collection.size().getInfo()
        if s2_count == 0:
            logger.warning("Aucune image Sentinel-2 disponible, élargissement de la fenêtre...")
            # Fallback : fenêtre de 60 jours
            start_dt = end_dt - timedelta(days=60)
            start_str = start_dt.strftime("%Y-%m-%d")
            s2_collection = self.sentinel.get_sentinel2_collection(
                ee_geometry, start_str, end_str
            )
            s2_count = s2_collection.size().getInfo()
            if s2_count == 0:
                raise RuntimeError("Aucune image Sentinel-2 disponible même avec fenêtre élargie.")

        # Image la plus récente
        latest = s2_collection.sort("system:time_start", False).first()
        masked = self.sentinel.mask_clouds(latest)
        indexed = self.sentinel.compute_indices(masked)
        sentinel_stats = self.sentinel.extract_statistics(indexed, ee_geometry)

        # -------------------------------------------------------------------
        # 2. CHIRPS
        # -------------------------------------------------------------------
        chirps_df = self.chirps.get_precipitation_series(centroid, start_str, end_str)
        chirps_features = self.chirps.aggregate_features(chirps_df)

        # -------------------------------------------------------------------
        # 3. ERA5-Land
        # -------------------------------------------------------------------
        era5_df = self.era5.get_climate_series(centroid, start_str, end_str)
        era5_features = self.era5.aggregate_features(era5_df)

        # -------------------------------------------------------------------
        # 4. Features temporelles cycliques
        # -------------------------------------------------------------------
        sin_doy, cos_doy = day_of_year_cyclic(end_dt)

        # -------------------------------------------------------------------
        # 5. Assemblage du vecteur de features
        # -------------------------------------------------------------------
        features = {
            # Indices spectraux — moyennes
            "NDVI_mean": sentinel_stats["NDVI"]["mean"],
            "NDWI_mean": sentinel_stats["NDWI"]["mean"],
            "MSI_mean": sentinel_stats["MSI"]["mean"],
            "SAVI_mean": sentinel_stats["SAVI"]["mean"],
            "EVI_mean": sentinel_stats["EVI"]["mean"],
            # Indices spectraux — min / max / std
            "NDVI_min": sentinel_stats["NDVI"]["min"],
            "NDVI_max": sentinel_stats["NDVI"]["max"],
            "NDVI_std": sentinel_stats["NDVI"]["stdDev"],
            "NDWI_std": sentinel_stats["NDWI"]["stdDev"],
            "MSI_min": sentinel_stats["MSI"]["min"],
            "MSI_max": sentinel_stats["MSI"]["max"],
            "MSI_std": sentinel_stats["MSI"]["stdDev"],
            # CHIRPS
            "precipitation_total_30j": chirps_features["precipitation_total_30j"],
            "precipitation_total_7j": chirps_features["precipitation_total_7j"],
            "precipitation_mean": chirps_features["precipitation_mean"],
            "max_consecutive_dry_days": chirps_features["max_consecutive_dry_days"],
            "rainy_days_count": chirps_features["rainy_days_count"],
            # ERA5-Land
            "temperature_mean": era5_features["temperature_mean"],
            "temperature_max": era5_features["temperature_max"],
            "temperature_min": era5_features["temperature_min"],
            "humidity_mean": era5_features["humidity_mean"],
            "humidity_min": era5_features["humidity_min"],
            # Temporel cyclique
            "day_of_year_sin": float(sin_doy),
            "day_of_year_cos": float(cos_doy),
        }

        result = {
            "features": features,
            "sentinel_stats": sentinel_stats,
            "chirps_series": chirps_df,
            "era5_series": era5_df,
            "extraction_date": datetime.now().isoformat(),
            "date_analyzed": analysis_date,
            "lookback_days": lookback_days,
        }

        logger.info("✓ Extraction complète et assemblée")
        return result


# ---------------------------------------------------------------------------
# Point d'entrée test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("Pipeline d'extraction HydroStress initialisé.")
    print("Utilisation : pipeline = DataPipeline(); pipeline.extract_all_data(coords, date)")
