"""
imagery.py
==========
Cartes satellite Sentinel-2 de la parcelle, pour la suivre à distance et
comparer deux dates image contre image.

Trois volets, chacun avec ses couches :

- Stress hydrique : NDMI (eau dans les feuilles), MSI
- État sanitaire : NDRE (chlorophylle, bande red-edge), PSRI (jaunissement / sénescence)
- Développement de la végétation : NDVI, anomalie NDVI par rapport aux années
  précédentes, zones faibles (écart à la médiane de la parcelle)

plus l'image en couleurs naturelles.

Les fonctions « pures » (couches, légendes, tendances, choix des dates) ne
dépendent pas d'Earth Engine et sont testées sans compte ; les fonctions
préfixées `ee_` construisent les images côté Earth Engine.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Sequence, Tuple

import pandas as pd

try:
    import ee
except ImportError:  # tests et mode démonstration sans Earth Engine
    ee = None

from extract_data import S2_REFLECTANCE_SCALE, SCL_VALID_CLASSES, SENTINEL2_COLLECTION

# Bandes utilisées : bleu, vert, rouge, red-edge 1 et 2 (20 m), PIR, SWIR 1 (20 m)
IMAGERY_BANDS = ["B2", "B3", "B4", "B5", "B6", "B8", "B11"]

# Sentinel-2 L2A est complet sur le Maroc à partir de 2018
FIRST_YEAR = 2018

# Une image est retenue si au moins cette part de la parcelle est visible (hors nuages / ombres)
MIN_CLEAR_FRACTION = 0.8

# Anomalie : images des années précédentes à ± N jours de la même date
ANOMALY_HALF_WINDOW_DAYS = 20
ANOMALY_MAX_YEARS = 5

# Tuiles CLOUDY_PIXEL_PERCENTAGE au-dessus de ce seuil : ignorées d'office
MAX_TILE_CLOUD = 70

RDYLGN = ["#a50026", "#f46d43", "#fee08b", "#a6d96a", "#1a9850"]
WATER = ["#8c510a", "#d8b365", "#f6e8c3", "#5ab4ac", "#01665e"]
DIVERGING = ["#b2182b", "#ef8a62", "#f7f7f7", "#91cf60", "#1a9850"]

THEMES = {
    "water": "💧 Stress hydrique",
    "health": "🩺 État sanitaire",
    "growth": "🌱 Développement de la végétation",
    "rgb": "🛰️ Image réelle",
}

# min / max : bornes de la palette ; higher_is_better : sens de lecture (False = valeurs hautes = problème)
LAYERS: Dict[str, Dict[str, Any]] = {
    "NDMI": {
        "theme": "water", "label": "NDMI · eau dans les feuilles",
        "min": -0.1, "max": 0.4, "palette": WATER, "higher_is_better": True,
        "low": "feuillage sec", "high": "bien alimenté",
        "description": "Teneur en eau du feuillage (PIR / SWIR). Une baisse entre deux dates sans baisse "
                       "du NDVI signale un manque d'eau avant que les arbres ne jaunissent.",
    },
    "MSI": {
        "theme": "water", "label": "MSI · indice de stress hydrique",
        "min": 0.4, "max": 1.6, "palette": list(reversed(RDYLGN)), "higher_is_better": False,
        "low": "sans stress", "high": "stress fort",
        "description": "SWIR / PIR : plus il est élevé, plus la végétation manque d'eau.",
    },
    "NDRE": {
        "theme": "health", "label": "NDRE · chlorophylle",
        "min": 0.05, "max": 0.45, "palette": RDYLGN, "higher_is_better": True,
        "low": "peu de chlorophylle", "high": "feuillage sain",
        "description": "Bande red-edge, sensible à la chlorophylle et à l'azote : baisse plus tôt que le "
                       "NDVI en cas de carence, de maladie ou de dépérissement.",
    },
    "PSRI": {
        "theme": "health", "label": "PSRI · jaunissement / sénescence",
        "min": -0.05, "max": 0.25, "palette": list(reversed(RDYLGN)), "higher_is_better": False,
        "low": "feuillage vert", "high": "jaunissement",
        "description": "Rapport caroténoïdes / chlorophylle : augmente quand les feuilles jaunissent "
                       "(maladie, carence, sénescence, chute des feuilles).",
    },
    "NDVI": {
        "theme": "growth", "label": "NDVI · vigueur et couvert",
        "min": 0.0, "max": 0.8, "palette": RDYLGN, "higher_is_better": True,
        "low": "sol nu", "high": "végétation dense",
        "description": "Densité et vigueur du couvert végétal : suit la croissance des arbres et des cultures.",
    },
    "NDVI_ANOM": {
        "theme": "growth", "label": "Anomalie NDVI vs années précédentes",
        "min": -0.2, "max": 0.2, "palette": DIVERGING, "higher_is_better": True,
        "low": "en retard", "high": "en avance",
        "description": "NDVI de la date moins la médiane des mêmes semaines des années précédentes "
                       "(jusqu'à 5 ans) : rouge = végétation moins développée que d'habitude à cette période.",
    },
    "NDVI_ZONES": {
        "theme": "growth", "label": "Zones faibles de la parcelle",
        "min": -30, "max": 30, "palette": DIVERGING, "higher_is_better": True,
        "low": "-30 % vs parcelle", "high": "+30 % vs parcelle",
        "description": "Écart du NDVI de chaque pixel (10 m) à la médiane de la parcelle, en % : repère les "
                       "rangs ou les arbres en retard, une fuite ou un bouchage du goutte-à-goutte.",
    },
    "RGB": {
        "theme": "rgb", "label": "Couleurs naturelles",
        "min": 0.0, "max": 0.3, "palette": None, "higher_is_better": None,
        "low": "", "high": "",
        "description": "Image Sentinel-2 telle que vue de l'espace (10 m).",
    },
}

# Indices suivis dans la courbe d'évolution (moyenne de la parcelle à chaque image)
SERIES_INDICES = ["NDVI", "NDMI", "NDRE", "PSRI", "MSI"]

# Écart minimal entre deux dates pour parler d'évolution (unités de l'indice)
TREND_THRESHOLDS = {"NDVI": 0.03, "NDMI": 0.03, "NDRE": 0.02, "PSRI": 0.02, "MSI": 0.08}


# ---------------------------------------------------------------------------
# Fonctions pures
# ---------------------------------------------------------------------------
def layers_for_theme(theme: str) -> List[str]:
    return [k for k, v in LAYERS.items() if v["theme"] == theme]


def diff_layer(layer: str) -> Dict[str, Any]:
    """Paramètres de la carte de différence (date B - date A) d'une couche."""
    spec = LAYERS[layer]
    span = (spec["max"] - spec["min"]) / 2
    better_up = spec["higher_is_better"] is not False
    return {
        "min": -span, "max": span,
        "palette": DIVERGING if better_up else list(reversed(DIVERGING)),
        "low": "baisse" if better_up else "baisse (mieux)",
        "high": "hausse" if better_up else "hausse (pire)",
    }


def legend_html(vmin: float, vmax: float, palette: Sequence[str], low: str = "", high: str = "",
                title: str = "") -> str:
    """Barre de couleurs HTML (palette, bornes et sens de lecture)."""
    gradient = ", ".join(palette)
    fmt = (lambda v: f"{v:g}")
    return (
        "<div style='font-size:.8rem;color:#CBD5E1;margin:4px 0 10px'>"
        + (f"<div style='margin-bottom:3px'>{title}</div>" if title else "")
        + f"<div style='height:10px;border-radius:5px;background:linear-gradient(90deg,{gradient})'></div>"
        "<div style='display:flex;justify-content:space-between;color:#94A3B8;margin-top:2px'>"
        f"<span>{fmt(vmin)} · {low}</span><span>{high} · {fmt(vmax)}</span></div></div>"
    )


def default_period(today: Optional[date] = None, months: int = 12) -> Tuple[date, date]:
    """Période de recherche par défaut : les 12 derniers mois."""
    today = today or date.today()
    return today - timedelta(days=round(months * 30.44)), today


def clean_series(rows: List[Dict[str, Any]], min_clear: float = MIN_CLEAR_FRACTION) -> pd.DataFrame:
    """
    Série d'images : une ligne par date (la plus dégagée si plusieurs tuiles le même jour),
    seulement les dates où la parcelle est assez visible.
    """
    cols = ["date", "clear"] + SERIES_INDICES
    if not rows:
        return pd.DataFrame(columns=cols)
    df = pd.DataFrame(rows)
    for c in cols:
        if c not in df:
            df[c] = None
    df = df[cols].dropna(subset=["date", "clear", "NDVI"])
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    df["clear"] = df["clear"].astype(float)
    df = df[df["clear"] >= min_clear]
    df = df.sort_values(["date", "clear"]).drop_duplicates("date", keep="last")
    return df.reset_index(drop=True)


def trend(layer: str, value_a: Optional[float], value_b: Optional[float]) -> Dict[str, Any]:
    """Évolution d'un indice entre deux dates, lue dans le bon sens (amélioration / dégradation)."""
    if value_a is None or value_b is None or pd.isna(value_a) or pd.isna(value_b):
        return {"delta": None, "status": "unknown", "label": "—"}
    delta = float(value_b) - float(value_a)
    threshold = TREND_THRESHOLDS.get(layer, 0.03)
    if abs(delta) < threshold:
        return {"delta": delta, "status": "stable", "label": "Stable"}
    better = delta > 0 if LAYERS[layer]["higher_is_better"] is not False else delta < 0
    return {"delta": delta, "status": "better" if better else "worse",
            "label": "Amélioration" if better else "Dégradation"}


def anomaly_years(target: date, first_year: int = FIRST_YEAR, max_years: int = ANOMALY_MAX_YEARS) -> List[int]:
    """Années de référence de l'anomalie : jusqu'à 5 années complètes avant la date."""
    return [y for y in range(target.year - max_years, target.year) if y >= first_year]


def to_date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return pd.Timestamp(value).date()


# ---------------------------------------------------------------------------
# Earth Engine
# ---------------------------------------------------------------------------
def _require_ee():
    if ee is None:
        raise RuntimeError("earthengine-api n'est pas installé : pip install earthengine-api")


def ee_mask_scale(image):
    """Masque nuages / ombres (SCL 4 et 5 conservées) et convertit en réflectance [0, 1]."""
    scl = image.select("SCL")
    mask = scl.eq(SCL_VALID_CLASSES[0]).Or(scl.eq(SCL_VALID_CLASSES[1]))
    optical = image.select(IMAGERY_BANDS).multiply(S2_REFLECTANCE_SCALE)
    return ee.Image(optical.updateMask(mask).copyProperties(image, ["system:time_start"]))


def ee_indices(img):
    """NDVI, NDMI, MSI, NDRE et PSRI d'une image en réflectance."""
    ndvi = img.normalizedDifference(["B8", "B4"]).rename("NDVI")
    ndmi = img.normalizedDifference(["B8", "B11"]).rename("NDMI")
    msi = img.select("B11").divide(img.select("B8")).rename("MSI")
    ndre = img.normalizedDifference(["B8", "B5"]).rename("NDRE")
    psri = img.select("B4").subtract(img.select("B2")).divide(img.select("B6").max(0.01)).rename("PSRI")
    return ee.Image.cat([ndvi, ndmi, msi, ndre, psri])


def ee_collection(geometry, start: str, end: str):
    _require_ee()
    return (
        ee.ImageCollection(SENTINEL2_COLLECTION)
        .filterBounds(geometry)
        .filterDate(start, end)
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", MAX_TILE_CLOUD))
    )


def ee_image_series(coordinates: List[List[float]], start: date, end: date) -> pd.DataFrame:
    """
    Toutes les images Sentinel-2 de la période : part visible de la parcelle et moyenne
    des indices. Un seul appel Earth Engine.
    """
    _require_ee()
    geometry = ee.Geometry.Polygon(coordinates)
    collection = ee_collection(geometry, start.isoformat(), (end + timedelta(days=1)).isoformat())

    def summarize(image):
        scaled = ee_mask_scale(image)
        clear = scaled.select("B8").mask().gt(0).unmask(0).rename("clear")
        stats = ee.Image.cat([clear, ee_indices(scaled)]).reduceRegion(
            reducer=ee.Reducer.mean(), geometry=geometry, scale=20, maxPixels=1e9, bestEffort=True,
        )
        return ee.Feature(None, stats).set("date", image.date().format("YYYY-MM-dd"))

    info = ee.FeatureCollection(collection.map(summarize)).getInfo()
    rows = [f["properties"] for f in info.get("features", [])]
    return clean_series(rows)


def ee_scene(geometry, day: date):
    """Image (mosaïque des tuiles) d'une date, masquée et en réflectance."""
    col = ee_collection(geometry, day.isoformat(), (day + timedelta(days=1)).isoformat())
    return col.map(ee_mask_scale).mosaic()


def ee_ndvi_history(geometry, day: date):
    """Médiane du NDVI des mêmes semaines des années précédentes (None si aucune image)."""
    merged = None
    for year in anomaly_years(day):
        try:
            center = day.replace(year=year)
        except ValueError:  # 29 février
            center = day.replace(year=year, day=28)
        start = center - timedelta(days=ANOMALY_HALF_WINDOW_DAYS)
        end = center + timedelta(days=ANOMALY_HALF_WINDOW_DAYS + 1)
        col = ee_collection(geometry, start.isoformat(), end.isoformat())
        merged = col if merged is None else merged.merge(col)
    if merged is None or merged.size().getInfo() == 0:
        return None
    return merged.map(lambda im: ee_indices(ee_mask_scale(im)).select("NDVI")).median()


def ee_layer_image(coordinates: List[List[float]], layer: str, day: date):
    """Image d'une couche pour une date, découpée sur la parcelle."""
    _require_ee()
    geometry = ee.Geometry.Polygon(coordinates)
    scene = ee_scene(geometry, day)
    if layer == "RGB":
        return scene.select(["B4", "B3", "B2"]).clip(geometry.buffer(150))
    indices = ee_indices(scene)
    if layer == "NDVI_ANOM":
        history = ee_ndvi_history(geometry, day)
        if history is None:
            raise ValueError("Pas d'images des années précédentes à cette période pour calculer l'anomalie.")
        return indices.select("NDVI").subtract(history).rename(layer).clip(geometry)
    if layer == "NDVI_ZONES":
        ndvi = indices.select("NDVI")
        median = ee.Number(ndvi.reduceRegion(
            reducer=ee.Reducer.median(), geometry=geometry, scale=10, maxPixels=1e9, bestEffort=True,
        ).get("NDVI"))
        return ndvi.subtract(median).divide(median.max(0.05)).multiply(100).rename(layer).clip(geometry)
    return indices.select(layer).clip(geometry)


def ee_tile_url(image, vmin: float, vmax: float, palette: Optional[Sequence[str]]) -> str:
    vis = {"min": vmin, "max": vmax}
    if palette:
        vis["palette"] = [c.lstrip("#") for c in palette]
    return image.getMapId(vis)["tile_fetcher"].url_format


def ee_geotiff_url(image, coordinates: List[List[float]]) -> str:
    """Lien de téléchargement GeoTIFF (10 m) de l'image sur la parcelle."""
    region = ee.Geometry.Polygon(coordinates)
    return image.getDownloadURL({"scale": 10, "region": region, "format": "GEO_TIFF", "crs": "EPSG:4326"})


def layer_maps(coordinates: List[List[float]], layer: str, day_a: date, day_b: date) -> Dict[str, Any]:
    """
    URLs des tuiles pour la date A, la date B et la différence B - A, plus le lien GeoTIFF
    de la date B. La différence n'existe pas pour l'image réelle ni pour les zones faibles
    (chaque date est déjà relative à sa propre médiane).
    """
    spec = LAYERS[layer]
    img_a = ee_layer_image(coordinates, layer, day_a)
    img_b = ee_layer_image(coordinates, layer, day_b)
    out = {
        "a": ee_tile_url(img_a, spec["min"], spec["max"], spec["palette"]),
        "b": ee_tile_url(img_b, spec["min"], spec["max"], spec["palette"]),
        "diff": None,
        "geotiff_b": ee_geotiff_url(img_b, coordinates),
    }
    if layer not in ("RGB", "NDVI_ZONES"):
        d = diff_layer(layer)
        out["diff"] = ee_tile_url(img_b.subtract(img_a), d["min"], d["max"], d["palette"])
    return out
