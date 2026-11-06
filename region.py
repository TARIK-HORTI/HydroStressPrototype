"""
region.py
=========
Configuration géographique : Maroc et grandes zones agricoles.

L'application couvre tout le Maroc. Chaque parcelle est rattachée à la zone
agricole de référence la plus proche, qui fournit :
- les normales climatiques mensuelles (générateur de données, valeurs par défaut),
- les cultures dominantes,
- les seuils d'interprétation des indices,
- l'organisme d'encadrement à contacter.

Les normales sont des ordres de grandeur (stations principales de chaque zone)
et doivent être affinées avec des données locales (DGM, ORMVA, DPA).
Les données météo utilisées pour l'analyse (CHIRPS, ERA5-Land) couvrent tout
le pays et ne dépendent pas de ces normales.
"""

import math
from typing import Dict, List, Optional, Tuple

REGION_NAME = "Maroc"

# Emprise approximative du Maroc (lon_min, lat_min, lon_max, lat_max), provinces du Sud incluses
REGION_BBOX: Tuple[float, float, float, float] = (-17.20, 20.70, -0.95, 35.95)

MAP_CENTER: Tuple[float, float] = (31.80, -6.80)  # (lat, lon)
MAP_ZOOM = 6

# Au-delà de cette distance de toute localité de référence, la zone est signalée comme approximative
MAX_ZONE_DISTANCE_KM = 150.0

ZONES: Dict[str, Dict] = {
    "gharb": {
        "name": "Gharb – Loukkos",
        "places": {
            "Kénitra": (34.261, -6.580), "Sidi Slimane": (34.265, -5.925), "Sidi Kacem": (34.226, -5.707),
            "Souk El Arbaa": (34.684, -5.998), "Ksar El Kébir": (35.002, -5.905),
        },
        "crops": ["Agrumes", "Canne à sucre", "Betterave sucrière", "Riz", "Céréales (blé / orge)", "Maraîchage"],
        "temp": [12.6, 13.3, 14.9, 16.2, 18.6, 21.3, 23.6, 23.9, 22.5, 19.7, 16.2, 13.6],
        "diurnal": [10, 10, 11, 11, 11, 11, 12, 12, 11, 11, 10, 10],
        "precip": [85, 75, 60, 50, 20, 5, 1, 2, 10, 55, 100, 110],
        "rh": [80, 79, 77, 75, 74, 74, 74, 74, 75, 77, 79, 80],
        "elevation": (10, 150),
        "ndvi_healthy_min": 0.35,
        "contact": "l'ORMVA du Gharb ou du Loukkos",
    },
    "sais": {
        "name": "Saïs – Meknès – Fès",
        "places": {
            "Meknès": (33.895, -5.555), "Fès": (34.033, -5.000), "El Hajeb": (33.686, -5.371),
            "Sefrou": (33.830, -4.835),
        },
        "crops": ["Céréales (blé / orge)", "Olivier", "Vigne", "Arboriculture (pommier, prunier)", "Maraîchage"],
        "temp": [9.6, 10.8, 13.0, 14.8, 18.3, 22.4, 26.0, 26.1, 22.8, 18.5, 13.6, 10.5],
        "diurnal": [11, 12, 13, 13, 14, 15, 16, 16, 14, 13, 12, 11],
        "precip": [70, 65, 60, 55, 30, 10, 2, 3, 15, 45, 70, 75],
        "rh": [78, 75, 70, 68, 62, 55, 48, 50, 58, 66, 75, 78],
        "elevation": (400, 900),
        "ndvi_healthy_min": 0.35,
        "contact": "la DPA de Meknès ou de Fès",
    },
    "tadla": {
        "name": "Tadla – Béni Mellal",
        "places": {
            "Béni Mellal": (32.337, -6.361), "Fquih Ben Salah": (32.502, -6.688), "Souk Sebt": (32.293, -6.710),
            "Kasba Tadla": (32.598, -6.268),
        },
        "crops": ["Betterave sucrière", "Céréales (blé / orge)", "Agrumes", "Olivier", "Luzerne"],
        "temp": [10.5, 12.0, 14.8, 17.0, 20.8, 25.5, 29.5, 29.3, 25.5, 20.7, 15.2, 11.5],
        "diurnal": [13, 13, 14, 14, 15, 16, 17, 17, 15, 14, 13, 13],
        "precip": [45, 45, 45, 40, 20, 5, 1, 3, 10, 35, 50, 50],
        "rh": [72, 70, 65, 62, 56, 48, 42, 44, 52, 60, 68, 72],
        "elevation": (350, 600),
        "ndvi_healthy_min": 0.32,
        "contact": "l'ORMVA du Tadla",
    },
    "haouz": {
        "name": "Haouz – Marrakech",
        "places": {
            "Marrakech": (31.629, -7.981), "Aït Ourir": (31.564, -7.663), "Chichaoua": (31.545, -8.765),
            "El Kelâa des Sraghna": (32.048, -7.408),
        },
        "crops": ["Olivier", "Céréales (blé / orge)", "Agrumes", "Maraîchage", "Luzerne"],
        "temp": [12.0, 13.5, 16.0, 17.8, 21.2, 24.8, 28.9, 29.0, 25.6, 21.6, 16.4, 12.9],
        "diurnal": [14, 14, 15, 15, 16, 16, 17, 17, 16, 15, 14, 14],
        "precip": [32, 38, 38, 35, 18, 6, 2, 3, 7, 24, 40, 31],
        "rh": [66, 64, 60, 57, 54, 50, 45, 46, 51, 58, 64, 67],
        "elevation": (350, 700),
        "ndvi_healthy_min": 0.30,
        "contact": "l'ORMVA du Haouz",
    },
    "chaouia": {
        "name": "Chaouia – Doukkala",
        "places": {
            "Settat": (33.001, -7.616), "Berrechid": (33.265, -7.587), "Sidi Bennour": (32.651, -8.426),
            "El Jadida": (33.254, -8.506),
        },
        "crops": ["Céréales (blé / orge)", "Betterave sucrière", "Maraîchage", "Légumineuses"],
        "temp": [11.5, 12.5, 14.5, 15.8, 18.5, 21.6, 24.4, 24.7, 22.7, 19.6, 15.6, 12.6],
        "diurnal": [11, 12, 12, 13, 13, 14, 15, 15, 14, 13, 12, 11],
        "precip": [50, 45, 45, 35, 15, 3, 1, 1, 7, 35, 55, 60],
        "rh": [78, 77, 75, 73, 72, 72, 71, 72, 73, 75, 77, 78],
        "elevation": (50, 400),
        "ndvi_healthy_min": 0.32,
        "contact": "l'ORMVA des Doukkala ou la DPA de Settat",
    },
    "souss": {
        "name": "Souss – Massa",
        "places": {
            "Agadir": (30.420, -9.598), "Ouled Teima": (30.395, -9.209), "Taroudant": (30.470, -8.877),
            "Biougra (Chtouka)": (30.215, -9.373), "Tiznit": (29.698, -9.731),
        },
        "crops": ["Agrumes", "Maraîchage sous serre", "Arganier", "Bananier", "Olivier"],
        "temp": [14.0, 15.3, 17.2, 18.2, 20.0, 22.0, 24.5, 24.8, 23.2, 21.0, 17.6, 14.8],
        "diurnal": [11, 12, 12, 12, 12, 12, 13, 13, 13, 13, 12, 11],
        "precip": [40, 35, 25, 12, 4, 1, 0, 1, 5, 22, 40, 45],
        "rh": [70, 72, 73, 74, 76, 78, 78, 78, 76, 72, 70, 69],
        "elevation": (20, 300),
        "ndvi_healthy_min": 0.30,
        "contact": "l'ORMVA du Souss-Massa",
    },
    "oriental": {
        "name": "Oriental – Moulouya",
        "places": {
            "Berkane": (34.920, -2.320), "Oujda": (34.681, -1.908), "Zaïo": (34.940, -2.733),
            "Taourirt": (34.407, -2.897),
        },
        "crops": ["Agrumes", "Olivier", "Céréales (blé / orge)", "Maraîchage", "Vigne"],
        "temp": [10.5, 11.6, 13.4, 15.3, 18.5, 22.3, 25.8, 26.3, 23.4, 19.4, 14.8, 11.6],
        "diurnal": [12, 12, 13, 13, 13, 14, 15, 15, 14, 13, 12, 12],
        "precip": [40, 35, 40, 35, 25, 8, 2, 4, 15, 30, 45, 40],
        "rh": [72, 71, 69, 67, 65, 62, 60, 62, 65, 68, 71, 72],
        "elevation": (50, 600),
        "ndvi_healthy_min": 0.30,
        "contact": "l'ORMVA de la Moulouya",
    },
    "errachidia": {
        "name": "Errachidia – Tafilalet",
        "places": {
            "Errachidia (vallée du Ziz)": (31.931, -4.424), "Aoufous": (31.680, -4.172),
            "Erfoud (Tafilalet)": (31.433, -4.233), "Jorf": (31.493, -4.403), "Rissani (Tafilalet)": (31.282, -4.265),
            "Goulmima (Ghéris)": (31.694, -4.958), "Tinejdad (Ferkla)": (31.508, -5.025), "Boudnib (Guir)": (31.948, -3.601),
        },
        "crops": ["Palmier dattier", "Luzerne", "Céréales (blé / orge)", "Olivier", "Maraîchage"],
        "temp": [9.5, 11.8, 15.2, 18.6, 23.0, 28.4, 32.0, 31.0, 26.0, 19.8, 14.0, 10.0],
        "diurnal": [13, 13, 13, 14, 14, 15, 15, 14, 13, 12, 12, 12],
        "precip": [9.0, 8.0, 12.0, 10.0, 9.0, 4.0, 3.0, 8.0, 15.0, 17.0, 12.0, 10.0],
        "rh": [55, 50, 44, 40, 35, 28, 24, 27, 36, 45, 52, 57],
        "elevation": (750, 1100),
        "ndvi_healthy_min": 0.25,
        "contact": "l'ORMVA du Tafilalet",
    },
    "draa": {
        "name": "Drâa – Ouarzazate – Zagora",
        "places": {
            "Ouarzazate": (30.920, -6.893), "Skoura": (31.060, -6.560), "Kelâat M'Gouna": (31.240, -6.128),
            "Tinghir": (31.514, -5.532), "Agdz": (30.697, -6.450), "Zagora": (30.332, -5.838),
        },
        "crops": ["Palmier dattier", "Luzerne", "Céréales (blé / orge)", "Rosier à parfum", "Olivier"],
        "temp": [9.0, 11.6, 15.3, 18.8, 23.0, 28.0, 31.7, 30.8, 26.0, 19.8, 13.7, 9.6],
        "diurnal": [15, 15, 16, 16, 16, 17, 17, 16, 15, 15, 15, 15],
        "precip": [7, 6, 10, 6, 5, 3, 2, 6, 12, 12, 10, 8],
        "rh": [52, 46, 40, 35, 30, 26, 23, 26, 33, 42, 50, 55],
        "elevation": (700, 1500),
        "ndvi_healthy_min": 0.25,
        "contact": "l'ORMVA de Ouarzazate",
    },
}

# Toutes les cultures connues (union des zones, ordre stable)
CROPS: List[str] = list(dict.fromkeys(c for z in ZONES.values() for c in z["crops"]))


def distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distance orthodromique (km)."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(a))


def zone_for_point(lat: float, lon: float) -> Tuple[str, str, float]:
    """
    Zone agricole de référence la plus proche d'un point.

    Returns:
        (identifiant de zone, localité la plus proche, distance en km)
    """
    best = None
    for zone_id, zone in ZONES.items():
        for place, (plat, plon) in zone["places"].items():
            d = distance_km(lat, lon, plat, plon)
            if best is None or d < best[2]:
                best = (zone_id, place, d)
    return best


def zone_normals(zone_id: str) -> Dict[str, List[float]]:
    """Normales mensuelles d'une zone (index 0 = janvier)."""
    z = ZONES[zone_id]
    return {k: z[k] for k in ("temp", "diurnal", "precip", "rh")}


def is_in_region(lon: float, lat: float) -> bool:
    """Indique si un point (lon, lat) est dans l'emprise du Maroc."""
    lon_min, lat_min, lon_max, lat_max = REGION_BBOX
    return lon_min <= lon <= lon_max and lat_min <= lat <= lat_max


def validate_in_region(coordinates: List[List[float]]) -> None:
    """
    Vérifie que tous les sommets de la parcelle sont au Maroc.

    Raises:
        ValueError: si un sommet est hors de l'emprise
    """
    outside = [c for c in coordinates if not is_in_region(c[0], c[1])]
    if outside:
        lon, lat = outside[0][0], outside[0][1]
        raise ValueError(
            f"Parcelle hors zone : le point ({lat:.4f}, {lon:.4f}) est en dehors du Maroc."
        )


def zone_label(zone_id: Optional[str]) -> str:
    return ZONES[zone_id]["name"] if zone_id in ZONES else "—"
