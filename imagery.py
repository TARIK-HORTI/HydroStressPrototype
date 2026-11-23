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


# ---------------------------------------------------------------------------
# Guide des indices (affiché sur le site)
# ---------------------------------------------------------------------------
GLOSSARY: Dict[str, Dict[str, str]] = {
    "NDVI": {
        "name": "NDVI — Indice de végétation par différence normalisée",
        "formula": "(PIR − Rouge) / (PIR + Rouge) · bandes B8 et B4 · 10 m",
        "meaning": "Une feuille verte absorbe le rouge pour la photosynthèse et renvoie fortement le proche "
                   "infrarouge. Plus il y a de feuillage vert et vigoureux, plus le NDVI est élevé.",
        "reading": "< 0,2 : sol nu ou très peu de végétation · 0,2–0,4 : couvert faible ou jeune · "
                   "0,4–0,6 : couvert moyen · > 0,6 : végétation dense et vigoureuse.",
        "use": "Suivre la croissance et le développement du couvert, comparer les blocs, repérer les arbres "
               "ou les rangs en retard. C'est l'indice de référence, mais il réagit tard : quand il baisse, "
               "le problème est souvent déjà installé.",
    },
    "NDMI": {
        "name": "NDMI — Indice d'humidité par différence normalisée",
        "formula": "(PIR − SWIR) / (PIR + SWIR) · bandes B8 et B11 · 20 m",
        "meaning": "L'eau contenue dans les feuilles absorbe l'infrarouge à ondes courtes (SWIR). Une feuille "
                   "bien hydratée renvoie peu de SWIR, donc un NDMI élevé.",
        "reading": "< 0 : feuillage sec ou sol nu · 0–0,2 : teneur en eau faible à moyenne · "
                   "> 0,2 : feuillage bien alimenté en eau.",
        "use": "Détecter le stress hydrique tôt, avant que les feuilles ne jaunissent ou ne tombent, et "
               "vérifier que l'irrigation arrive partout dans la parcelle (secteurs, bouts de lignes).",
    },
    "MSI": {
        "name": "MSI — Indice de stress hydrique",
        "formula": "SWIR / PIR · bandes B11 et B8 · 20 m",
        "meaning": "Même information que le NDMI, lue à l'envers : il augmente quand la végétation perd de l'eau.",
        "reading": "< 0,8 : pas de stress · 0,8–1,2 : stress modéré · > 1,2 : stress fort ou sol nu.",
        "use": "Confirmer un stress hydrique signalé par le NDMI.",
    },
    "NDRE": {
        "name": "NDRE — Indice red-edge par différence normalisée",
        "formula": "(PIR − Red-edge) / (PIR + Red-edge) · bandes B8 et B5 · 20 m",
        "meaning": "Le « red-edge » est la zone où la réflectance de la feuille passe du rouge au proche "
                   "infrarouge. Sa position dépend directement de la chlorophylle (et donc de l'azote).",
        "reading": "< 0,15 : peu de chlorophylle · 0,15–0,3 : moyen · > 0,3 : feuillage riche en chlorophylle.",
        "use": "Indicateur de l'état sanitaire et nutritionnel : il baisse avant le NDVI en cas de carence "
               "(azote, fer), de maladie, d'attaque de ravageurs ou de dépérissement, et il sature moins "
               "que le NDVI sur les vergers denses.",
    },
    "PSRI": {
        "name": "PSRI — Indice de réflectance de la sénescence des plantes",
        "formula": "(Rouge − Bleu) / Red-edge 2 · bandes B4, B2 et B6 · 20 m",
        "meaning": "Mesure le rapport entre pigments jaunes (caroténoïdes) et chlorophylle. Quand la "
                   "chlorophylle disparaît, les feuilles jaunissent et le PSRI augmente.",
        "reading": "< 0 : feuillage vert et actif · 0–0,1 : début de jaunissement · "
                   "> 0,1 : jaunissement net, sénescence ou dessèchement.",
        "use": "Repérer le jaunissement : maladie, carence, attaque de ravageurs, stress prolongé, mais aussi "
               "maturité des cultures annuelles et chute des feuilles en automne.",
    },
}


# ---------------------------------------------------------------------------
# Interprétation automatique du changement entre deux dates
# ---------------------------------------------------------------------------
DECIDUOUS_KEYWORDS = ("amandier", "vigne", "pommier", "prunier", "arboriculture", "rosier", "pêcher",
                      "abricotier", "cerisier", "noyer", "grenadier", "figuier")
ANNUAL_KEYWORDS = ("céréale", "blé", "orge", "betterave", "maraîchage", "légumineuse", "riz", "luzerne",
                   "canne", "maïs", "fourrage")

# Part de la parcelle en baisse : au-dessous, rien ; entre les deux, par taches ; au-dessus, généralisé
PATCHY_MIN, GENERAL_MIN = 0.10, 0.60

DISCLAIMER = (
    "Cette lecture est automatique et indicative. Le satellite mesure un changement de couleur, d'eau ou de "
    "chlorophylle du feuillage ; il ne voit ni l'insecte, ni le champignon, ni le goutte-à-goutte bouché. "
    "Plusieurs causes donnent la même image : seule une visite au champ (et si besoin l'avis d'un conseiller "
    "agricole ou d'un laboratoire) permet de conclure."
)


def crop_kind(crop: Optional[str]) -> str:
    """deciduous (feuilles caduques), annual (culture annuelle / fauchée) ou evergreen."""
    c = (crop or "").lower()
    if any(k in c for k in DECIDUOUS_KEYWORDS):
        return "deciduous"
    if any(k in c for k in ANNUAL_KEYWORDS):
        return "annual"
    return "evergreen"


def _extent(fraction: Optional[float]) -> str:
    if fraction is None:
        return "unknown"
    if fraction >= GENERAL_MIN:
        return "general"
    if fraction >= PATCHY_MIN:
        return "patchy"
    return "none"


def _pct(x: Optional[float]) -> str:
    return "—" if x is None else f"{x:.0%}"


def interpret_change(
    a: Dict[str, float], b: Dict[str, float], day_a: date, day_b: date,
    crop: Optional[str] = None, fractions: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """
    Lecture du changement entre deux dates : constat, causes possibles classées, vérifications au
    champ et avertissement. `a` et `b` : moyennes de la parcelle ; `fractions` : part de la parcelle
    où l'indice s'est dégradé (ndvi_down, ndmi_down, ndre_down, psri_up).
    """
    fractions = fractions or {}
    t = {k: trend(k, a.get(k), b.get(k)) for k in SERIES_INDICES}
    worse = {k for k, v in t.items() if v["status"] == "worse"}
    better = {k for k, v in t.items() if v["status"] == "better"}
    water = bool({"NDMI", "MSI"} & worse)
    chloro = "NDRE" in worse
    yellow = "PSRI" in worse
    vigor = "NDVI" in worse
    extent = _extent(fractions.get("ndvi_down"))
    extents = {k: _extent(fractions.get(k)) for k in ("ndvi_down", "ndmi_down", "ndre_down", "psri_up")}
    patchy_only = not worse and any(e in ("patchy", "general") for e in extents.values())
    kind = crop_kind(crop)
    gap = (day_b - day_a).days
    autumn_winter = day_b.month in (10, 11, 12, 1, 2)

    observations = []
    for k in SERIES_INDICES:
        v = t[k]
        if v["delta"] is not None:
            observations.append(f"{k} : {a[k]:.2f} → {b[k]:.2f} ({v['delta']:+.2f}, {v['label'].lower()})")
    if fractions:
        observations.append(
            f"Part de la parcelle en baisse : NDVI {_pct(fractions.get('ndvi_down'))}, "
            f"NDMI {_pct(fractions.get('ndmi_down'))}, NDRE {_pct(fractions.get('ndre_down'))} ; "
            f"jaunissement (PSRI en hausse) sur {_pct(fractions.get('psri_up'))}."
        )

    hypotheses: List[Dict[str, str]] = []
    checks: List[str] = []

    def add(title, likelihood, detail, *todo):
        hypotheses.append({"title": title, "likelihood": likelihood, "detail": detail})
        for c in todo:
            if c not in checks:
                checks.append(c)

    if gap < 0:
        status, headline = "unknown", "La date A est postérieure à la date B : inversez les dates."
    elif not worse and not patchy_only:
        if better:
            status = "better"
            headline = "La parcelle s'est améliorée entre les deux dates."
            add("Croissance ou reprise de la végétation", "probable",
                "Hausse de vigueur, d'eau ou de chlorophylle : développement normal de la culture, feuillaison, "
                "reprise après une irrigation, une pluie ou une fertilisation.")
            if "NDVI" in better and kind != "annual":
                add("Développement d'adventices (mauvaises herbes)", "possible",
                    "Entre les rangs, l'herbe fait aussi monter le NDVI sans que les arbres aillent mieux.",
                    "Regarder si l'inter-rang est enherbé.")
        else:
            status = "stable"
            headline = "Pas de changement notable de la parcelle entre les deux dates."
            add("Situation stable", "probable", "Les indices restent dans la marge normale de variation.")
            checks.append("Continuer la surveillance : comparer de nouveau dans 2 à 3 semaines.")
    else:
        status = "worse"
        where = {"general": "sur la plus grande partie de la parcelle", "patchy": "par taches",
                 "none": "", "unknown": ""}[extent]
        signs = []
        if vigor:
            signs.append("baisse de vigueur")
        if water:
            signs.append("perte d'eau du feuillage")
        if chloro:
            signs.append("baisse de chlorophylle")
        if yellow:
            signs.append("jaunissement")
        if patchy_only:
            headline = ("La moyenne de la parcelle tient, mais certaines zones reculent : "
                        "repérez-les sur la carte du changement B − A.")
        else:
            headline = f"La parcelle a reculé {where} : {', '.join(signs)}.".replace("  ", " ")

        # Causes naturelles ou culturales d'abord : elles ne demandent pas d'intervention
        if kind == "deciduous" and autumn_winter and (vigor or yellow):
            add("Chute naturelle des feuilles (repos hivernal)", "probable",
                f"La culture ({crop}) perd ses feuilles en automne-hiver : NDVI et NDRE baissent et le PSRI "
                "monte chaque année à cette période, sans problème.",
                "Comparer avec la carte « Anomalie NDVI » : si la baisse est la même que les autres années, "
                "c'est le cycle normal.")
        if kind == "annual" and (vigor or yellow):
            add("Maturité, récolte ou fauche", "probable" if extent == "general" else "possible",
                "Une culture qui mûrit, est récoltée ou fauchée (luzerne) fait chuter les indices sur toute la "
                "parcelle.", "Vérifier le calendrier de récolte ou de coupe entre les deux dates.")
        if vigor and not (chloro or yellow or water) and kind != "annual":
            add("Taille, désherbage ou travail du sol", "possible",
                "Une taille sévère ou la suppression de l'herbe entre les rangs fait baisser le NDVI sans "
                "que les arbres souffrent.", "Vérifier les travaux réalisés entre les deux dates.")

        if water:
            add("Stress hydrique", "probable" if not (chloro or yellow) or "NDMI" in worse else "possible",
                "Le feuillage contient moins d'eau. Causes fréquentes : apports d'irrigation insuffisants pour "
                "la demande (chaleur, chergui, vent), panne de pompe ou coupure d'eau, goutteurs bouchés, "
                "fuites, pression trop faible en bout de ligne, salinité de l'eau ou du sol.",
                "Contrôler la pompe, la pression et le débit des goutteurs, surtout en bout de ligne.",
                "Sonder l'humidité du sol à 30–60 cm (tarière) dans les zones en recul et dans une zone saine.",
                "Comparer avec le registre d'irrigation et la météo (pic de chaleur, vent).")
        if (chloro or yellow) and not water:
            add("Problème sanitaire : maladie ou ravageur", "possible",
                "Chlorophylle en baisse ou jaunissement sans perte d'eau marquée : peut venir d'une maladie "
                "(champignon, bactérie, virus), d'une attaque de ravageurs (acariens, pucerons, cochenilles, "
                "chenilles, scolytes) ou de nématodes au niveau des racines.",
                "Observer les feuilles (dessus et dessous), les rameaux et le tronc dans les zones en recul : "
                "taches, déformations, insectes, toiles, gomme, galeries.",
                "Prendre des photos et des échantillons pour un conseiller agricole ou un laboratoire.")
            add("Carence nutritionnelle", "possible",
                "Une carence en azote ou une chlorose ferrique (fréquente sur sols calcaires) fait baisser le "
                "NDRE et jaunir les feuilles.",
                "Vérifier le programme de fertilisation ; analyse foliaire ou de sol si le doute persiste.")
        if (chloro or yellow) and water:
            add("Stress prolongé ou dépérissement", "possible",
                "Perte d'eau et de chlorophylle ensemble : stress hydrique installé depuis un moment, asphyxie "
                "ou pourriture des racines, salinité, ou attaque qui affaiblit les arbres (maladie du bois, "
                "scolytes).", "Examiner les racines et le collet de quelques arbres en recul.")
        if extent == "patchy" or patchy_only:
            add("Problème localisé", "possible",
                "Une baisse par taches oriente vers une cause localisée : secteur ou ligne d'irrigation, "
                "goutteurs bouchés, zone de sol différente (sable, calcaire, sel), foyer de maladie ou de "
                "ravageurs qui démarre, arbres morts ou arrachés.",
                "Aller d'abord dans les zones rouges de la carte du changement B − A, puis comparer avec une "
                "zone restée verte.")
        if not hypotheses:
            add("Recul modéré de la végétation", "possible",
                "Le recul est réel mais ne correspond pas à un profil net : plusieurs causes peuvent se mêler.",
                "Visiter la parcelle en commençant par les zones rouges de la carte du changement.")

    notes = []
    if 0 <= gap < 10:
        notes.append("Les deux dates sont proches (moins de 10 jours) : les petits écarts peuvent venir de "
                     "l'atmosphère ou de l'angle de prise de vue.")
    if gap > 120:
        notes.append("Plus de 4 mois séparent les deux dates : une partie du changement est saisonnière. "
                     "La carte « Anomalie NDVI » aide à séparer le saisonnier de l'anormal.")
    if kind == "evergreen" and autumn_winter and (vigor or yellow):
        notes.append(f"La culture ({crop or 'non précisée'}) garde ses feuilles : une baisse en automne-hiver "
                     "n'est pas due à la chute des feuilles.")

    return {"status": status, "headline": headline, "observations": observations,
            "hypotheses": hypotheses, "checks": checks, "notes": notes, "disclaimer": DISCLAIMER}


def ee_change_fractions(coordinates: List[List[float]], day_a: date, day_b: date) -> Dict[str, float]:
    """Part de la parcelle où chaque indice s'est dégradé entre A et B (un seul appel Earth Engine)."""
    _require_ee()
    geometry = ee.Geometry.Polygon(coordinates)
    ia = ee_indices(ee_scene(geometry, day_a))
    ib = ee_indices(ee_scene(geometry, day_b))
    d = ib.subtract(ia)
    flags = ee.Image.cat([
        d.select("NDVI").lt(-TREND_THRESHOLDS["NDVI"]).rename("ndvi_down"),
        d.select("NDMI").lt(-TREND_THRESHOLDS["NDMI"]).rename("ndmi_down"),
        d.select("NDRE").lt(-TREND_THRESHOLDS["NDRE"]).rename("ndre_down"),
        d.select("PSRI").gt(TREND_THRESHOLDS["PSRI"]).rename("psri_up"),
    ])
    info = flags.reduceRegion(reducer=ee.Reducer.mean(), geometry=geometry, scale=10,
                              maxPixels=1e9, bestEffort=True).getInfo()
    return {k: float(v) for k, v in info.items() if v is not None}
