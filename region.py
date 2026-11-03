"""
region.py
=========
Configuration régionale : Province d'Errachidia (Région Drâa-Tafilalet, Maroc).

Toute l'exploitation de l'application (carte, validation des parcelles,
données d'entraînement, seuils d'interprétation, recommandations) est
contrainte à cette zone.

Les valeurs climatiques ci-dessous sont des ordres de grandeur issus des
normales de la station d'Errachidia (climat aride, ~120 mm/an). Elles servent
au générateur de données et aux contrôles de cohérence ; elles doivent être
affinées avec des données locales (ORMVA-TF, DMN) dès qu'elles sont disponibles.
"""

from typing import Dict, List, Tuple

REGION_NAME = "Province d'Errachidia — Drâa-Tafilalet"

# Centre de la carte : ville d'Errachidia
MAP_CENTER: Tuple[float, float] = (31.93, -4.42)  # (lat, lon)
MAP_ZOOM = 9

# Emprise approximative de la province (lon_min, lat_min, lon_max, lat_max).
# Couvre la vallée du Ziz, le Tafilalet (Erfoud, Rissani), le Ghéris
# (Goulmima, Tinejdad), Boudnib et le sud jusqu'à Taouz.
REGION_BBOX: Tuple[float, float, float, float] = (-5.75, 30.45, -2.90, 32.75)

# Nom de la province dans FAO GAUL (niveau 2) pour un contrôle côté Earth Engine
GAUL_ADM2_NAME = "Errachidia"

# Oasis / zones agricoles principales (lat, lon)
OASES: Dict[str, Tuple[float, float]] = {
    "Errachidia (vallée du Ziz)": (31.931, -4.424),
    "Aoufous": (31.680, -4.172),
    "Erfoud (Tafilalet)": (31.433, -4.233),
    "Jorf": (31.493, -4.403),
    "Rissani (Tafilalet)": (31.282, -4.265),
    "Goulmima (Ghéris)": (31.694, -4.958),
    "Tinejdad (Ferkla)": (31.508, -5.025),
    "Boudnib (Guir)": (31.948, -3.601),
}

# Cultures dominantes de la zone
CROPS: List[str] = [
    "Palmier dattier",
    "Luzerne",
    "Céréales (blé / orge)",
    "Olivier",
    "Maraîchage",
]

# Normales mensuelles approximatives (Errachidia), index 0 = janvier
MONTHLY_TEMP_MEAN_C = [9.5, 11.8, 15.2, 18.6, 23.0, 28.4, 32.0, 31.0, 26.0, 19.8, 14.0, 10.0]
MONTHLY_DIURNAL_RANGE_C = [13, 13, 13, 14, 14, 15, 15, 14, 13, 12, 12, 12]
MONTHLY_PRECIP_MM = [9.0, 8.0, 12.0, 10.0, 9.0, 4.0, 3.0, 8.0, 15.0, 17.0, 12.0, 10.0]
MONTHLY_RH_MEAN = [55, 50, 44, 40, 35, 28, 24, 27, 36, 45, 52, 57]


def is_in_region(lon: float, lat: float) -> bool:
    """Indique si un point (lon, lat) est dans l'emprise de la province."""
    lon_min, lat_min, lon_max, lat_max = REGION_BBOX
    return lon_min <= lon <= lon_max and lat_min <= lat <= lat_max


def validate_in_region(coordinates: List[List[float]]) -> None:
    """
    Vérifie que tous les sommets de la parcelle sont dans la province d'Errachidia.

    Args:
        coordinates: Liste de [lon, lat]

    Raises:
        ValueError: si un sommet est hors de la zone
    """
    outside = [c for c in coordinates if not is_in_region(c[0], c[1])]
    if outside:
        lon, lat = outside[0][0], outside[0][1]
        raise ValueError(
            f"Parcelle hors zone : le point ({lat:.4f}, {lon:.4f}) est en dehors de la "
            f"{REGION_NAME}. L'application est calibrée uniquement pour cette province."
        )
