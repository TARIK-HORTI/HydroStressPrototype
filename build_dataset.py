"""
build_dataset.py
================
Construit un dataset d'entraînement à partir de données RÉELLES dans les
grandes zones agricoles du Maroc (region.ZONES), avec des étiquettes dérivées
du Vegetation Health Index (VHI, Kogan 1995) calculé sur MODIS.

Pour chaque parcelle échantillonnée et chaque date :
- les 26 features sont extraites avec DataPipeline (Sentinel-2, CHIRPS,
  ERA5-Land, altitude, normale de pluie) ;
- l'étiquette vient du VHI = 0.5 * VCI + 0.5 * TCI, où
    VCI = (NDVI - NDVImin) / (NDVImax - NDVImin)   (MODIS MOD13Q1, même période, 2001+)
    TCI = (LSTmax - LST) / (LSTmax - LSTmin)       (MODIS MOD11A2, même période, 2001+)
  Classes : VHI >= 40 -> 0 Normal, 20 <= VHI < 40 -> 1 Modéré, VHI < 20 -> 2 Sévère.

Le VHI est un indicateur d'anomalie par rapport à l'historique du pixel. Il
reste une étiquette indirecte : dès que des observations de terrain
(ORMVA-TF, agriculteurs) sont disponibles, elles doivent la remplacer ou la valider.

Utilisation (Earth Engine doit être authentifié, voir README) :
    # Tout le Maroc (toutes les zones)
    python build_dataset.py --points-per-place 4 --start 2019-01-01 --end 2024-12-31 \
        --every-days 45 --output data/maroc_vhi.csv
    # Une seule zone
    python build_dataset.py --zones haouz souss --points-per-place 6 --output data/haouz_souss.csv
"""

import argparse
import logging
from datetime import datetime, timedelta
from pathlib import Path

import ee
import pandas as pd

from extract_data import DataPipeline, DataUnavailableError
from region import ZONES

logger = logging.getLogger("build_dataset")

WORLDCOVER = "ESA/WorldCover/v200"
WORLDCOVER_CLASSES = [10, 40]          # 10 = couvert arboré (palmeraies), 40 = cultures
MODIS_NDVI = "MODIS/061/MOD13Q1"
MODIS_LST = "MODIS/061/MOD11A2"
HISTORY_START_YEAR = 2001
PLACE_BUFFER_M = 15000
PARCEL_HALF_SIDE_M = 100               # parcelles de 200 m x 200 m
VHI_THRESHOLDS = (20.0, 40.0)


def sample_parcels(points_per_place: int, seed: int, zone_ids):
    """Tire des points sur des pixels cultivés autour de chaque localité des zones choisies."""
    cover = ee.Image(ee.ImageCollection(WORLDCOVER).first()).select("Map")
    cultivated = cover.remap(WORLDCOVER_CLASSES, [1] * len(WORLDCOVER_CLASSES), 0).selfMask()

    parcels = []
    for zone_id in zone_ids:
        # Les oasis sont plus petites : rayon d'échantillonnage réduit
        buffer_m = 6000 if ZONES[zone_id]["ndvi_healthy_min"] <= 0.25 else PLACE_BUFFER_M
        for name, (lat, lon) in ZONES[zone_id]["places"].items():
            area = ee.Geometry.Point([lon, lat]).buffer(buffer_m)
            pts = cultivated.stratifiedSample(
                numPoints=points_per_place, classBand="remapped", region=area,
                scale=10, seed=seed, geometries=True,
            ).getInfo()
            for i, feat in enumerate(pts["features"]):
                plon, plat = feat["geometry"]["coordinates"]
                square = ee.Geometry.Point([plon, plat]).buffer(PARCEL_HALF_SIDE_M).bounds()
                coords = square.coordinates().getInfo()[0]
                slug = "".join(ch for ch in name.split()[0] if ch.isalnum())
                parcels.append({"zone": zone_id, "place": name, "parcel_id": f"{zone_id}_{slug}_{i}",
                                "coordinates": coords})
            logger.info(f"{ZONES[zone_id]['name']} / {name} : {len(pts['features'])} parcelle(s)")
    return parcels


def _condition_index(collection_id: str, band: str, scale: float, geometry, date: datetime,
                     period_days: int, invert: bool) -> float:
    """VCI ou TCI (0-100) d'une parcelle à une date, relativement à l'historique du même jour de l'année."""
    doy = date.timetuple().tm_yday
    doy_start = max(1, doy - period_days)
    col = ee.ImageCollection(collection_id).select(band)
    history = col.filter(ee.Filter.calendarRange(HISTORY_START_YEAR, date.year, "year")) \
                 .filter(ee.Filter.calendarRange(doy_start, doy, "day_of_year"))
    current = col.filterDate((date - timedelta(days=period_days)).strftime("%Y-%m-%d"),
                             (date + timedelta(days=1)).strftime("%Y-%m-%d")).mean()
    vmin, vmax = history.min(), history.max()
    if invert:
        index = vmax.subtract(current).divide(vmax.subtract(vmin))
    else:
        index = current.subtract(vmin).divide(vmax.subtract(vmin))
    value = index.multiply(100).rename("ci").reduceRegion(
        ee.Reducer.mean(), geometry, scale=scale, bestEffort=True
    ).get("ci").getInfo()
    if value is None:
        raise DataUnavailableError(f"{collection_id} : pas de valeur pour la date {date:%Y-%m-%d}")
    return float(max(0.0, min(100.0, value)))


def vhi_label(coordinates, date: datetime):
    """Calcule le VHI et la classe de stress associée."""
    geometry = ee.Geometry.Polygon(coordinates)
    vci = _condition_index(MODIS_NDVI, "NDVI", 250, geometry, date, 16, invert=False)
    tci = _condition_index(MODIS_LST, "LST_Day_1km", 1000, geometry, date, 8, invert=True)
    vhi = 0.5 * vci + 0.5 * tci
    if vhi < VHI_THRESHOLDS[0]:
        label = 2
    elif vhi < VHI_THRESHOLDS[1]:
        label = 1
    else:
        label = 0
    return vhi, vci, tci, label


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--points-per-place", type=int, default=4)
    parser.add_argument("--zones", nargs="+", choices=list(ZONES), default=list(ZONES),
                        help="Zones à échantillonner (défaut : toutes)")
    parser.add_argument("--start", default="2019-01-01")
    parser.add_argument("--end", default="2024-12-31")
    parser.add_argument("--every-days", type=int, default=45)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", default="data/maroc_vhi.csv")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    pipeline = DataPipeline()
    parcels = sample_parcels(args.points_per_place, args.seed, args.zones)

    start = datetime.strptime(args.start, "%Y-%m-%d")
    end = datetime.strptime(args.end, "%Y-%m-%d")
    dates = []
    d = start
    while d <= end:
        dates.append(d)
        d += timedelta(days=args.every_days)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    rows, skipped = [], 0
    for p in parcels:
        for date in dates:
            try:
                data = pipeline.extract_all_data(p["coordinates"], date.strftime("%Y-%m-%d"), lookback_days=30)
                vhi, vci, tci, label = vhi_label(p["coordinates"], date)
            except (DataUnavailableError, ee.EEException, ValueError) as e:
                skipped += 1
                logger.warning(f"{p['parcel_id']} {date:%Y-%m-%d} ignoré : {e}")
                continue
            rows.append({**data["features"], "stress_class": label, "VHI": vhi, "VCI": vci, "TCI": tci,
                         "zone": p["zone"], "place": p["place"], "parcel_id": p["parcel_id"], "date": date.strftime("%Y-%m-%d")})
        # Sauvegarde incrémentale pour ne rien perdre en cas d'interruption
        pd.DataFrame(rows).to_csv(out, index=False)

    df = pd.DataFrame(rows)
    logger.info(f"✓ {len(df)} échantillons écrits dans {out} ({skipped} ignorés)")
    if not df.empty:
        logger.info(f"  Distribution : {df['stress_class'].value_counts().sort_index().to_dict()}")


if __name__ == "__main__":
    main()
