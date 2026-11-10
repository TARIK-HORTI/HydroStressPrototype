"""
farm.py
=======
Description d'une ferme réelle : localisation, culture, écartement (plantation),
sol et irrigation. Sert à construire un dataset d'entraînement à partir des
relevés de la ferme (voir farm_dataset.py).

L'écartement donne la densité de plantation et, avec le diamètre de la
couronne, le taux de couverture du sol. Celui-ci corrige le coefficient
cultural Kc (FAO-56, équation 98) : un verger jeune ou peu dense consomme
moins d'eau qu'un verger adulte qui couvre tout le sol.

Une ferme est enregistrée en JSON (farms/<identifiant>.json) :

    python farm_dataset.py init --name "Ferme Aoufous" --lat 31.70 --lon -4.17 \
        --crop palmier --spacing 8x8 --area-ha 12 --planting-year 2008 \
        --irrigation goutte --soil sableux
"""

import json
import math
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from region import ZONES, is_in_region, zone_for_point

# ---------------------------------------------------------------------------
# Cultures (FAO-56, tableaux 12 et 22 ; valeurs pour climat semi-aride)
# ---------------------------------------------------------------------------
# kc       : Kc mensuel (janvier -> décembre) d'une culture qui couvre bien le sol
# p        : fraction de la réserve utile consommable sans stress (FAO-56 tableau 22)
# root_m   : profondeur d'enracinement efficace (m)
# height_m : hauteur adulte (m), utilisée dans la correction de couverture
# canopy_m : diamètre adulte typique de la couronne (m) ; None = culture couvrante
# years_to_adult : âge auquel la couronne atteint canopy_m
CROPS: Dict[str, Dict] = {
    "olivier": {
        "name": "Olivier", "name_ar": "الزيتون",
        "kc": [0.65, 0.65, 0.65, 0.70, 0.70, 0.70, 0.70, 0.70, 0.70, 0.70, 0.65, 0.65],
        "p": 0.65, "root_m": 1.5, "height_m": 4.0, "canopy_m": 6.0, "years_to_adult": 12,
    },
    "palmier": {
        "name": "Palmier dattier", "name_ar": "النخيل",
        "kc": [0.90, 0.90, 0.95, 0.95, 0.95, 0.95, 0.95, 0.95, 0.95, 0.95, 0.90, 0.90],
        "p": 0.50, "root_m": 2.0, "height_m": 8.0, "canopy_m": 7.0, "years_to_adult": 10,
    },
    "agrumes": {
        "name": "Agrumes", "name_ar": "الحوامض",
        "kc": [0.70, 0.70, 0.65, 0.65, 0.65, 0.65, 0.65, 0.65, 0.65, 0.70, 0.70, 0.70],
        "p": 0.50, "root_m": 1.1, "height_m": 4.0, "canopy_m": 5.0, "years_to_adult": 10,
    },
    "amandier": {
        "name": "Amandier", "name_ar": "اللوز",
        "kc": [0.40, 0.40, 0.45, 0.60, 0.80, 0.90, 0.90, 0.90, 0.80, 0.65, 0.45, 0.40],
        "p": 0.40, "root_m": 1.4, "height_m": 5.0, "canopy_m": 6.0, "years_to_adult": 8,
    },
    "pommier": {
        "name": "Pommier", "name_ar": "التفاح",
        "kc": [0.45, 0.45, 0.50, 0.65, 0.85, 0.95, 0.95, 0.95, 0.85, 0.75, 0.50, 0.45],
        "p": 0.50, "root_m": 1.3, "height_m": 4.0, "canopy_m": 4.0, "years_to_adult": 7,
    },
    "vigne": {
        "name": "Vigne", "name_ar": "الدالية",
        "kc": [0.30, 0.30, 0.30, 0.40, 0.65, 0.85, 0.85, 0.85, 0.70, 0.45, 0.30, 0.30],
        "p": 0.35, "root_m": 1.2, "height_m": 2.0, "canopy_m": 2.5, "years_to_adult": 4,
    },
    "grenadier": {
        "name": "Grenadier", "name_ar": "الرمان",
        "kc": [0.40, 0.40, 0.50, 0.65, 0.80, 0.85, 0.85, 0.85, 0.80, 0.65, 0.45, 0.40],
        "p": 0.50, "root_m": 1.2, "height_m": 3.5, "canopy_m": 4.0, "years_to_adult": 6,
    },
    "avocatier": {
        "name": "Avocatier", "name_ar": "الأفوكا",
        "kc": [0.75, 0.75, 0.80, 0.85, 0.85, 0.85, 0.85, 0.85, 0.85, 0.80, 0.75, 0.75],
        "p": 0.70, "root_m": 0.8, "height_m": 4.0, "canopy_m": 6.0, "years_to_adult": 8,
    },
    "luzerne": {
        "name": "Luzerne", "name_ar": "الفصة",
        "kc": [0.50, 0.60, 0.80, 0.95, 0.95, 0.95, 0.95, 0.95, 0.90, 0.80, 0.60, 0.50],
        "p": 0.55, "root_m": 1.2, "height_m": 0.7, "canopy_m": None, "years_to_adult": 1,
    },
    "cereales": {
        "name": "Céréales (blé / orge)", "name_ar": "الحبوب",
        # Semis novembre, récolte juin
        "kc": [0.70, 1.00, 1.15, 1.15, 0.80, 0.30, 0.20, 0.20, 0.20, 0.20, 0.30, 0.40],
        "p": 0.55, "root_m": 1.2, "height_m": 1.0, "canopy_m": None, "years_to_adult": 1,
    },
    "maraichage": {
        "name": "Maraîchage", "name_ar": "الخضروات",
        "kc": [0.60, 0.70, 0.90, 1.05, 1.10, 1.05, 0.90, 0.80, 0.70, 0.60, 0.60, 0.60],
        "p": 0.40, "root_m": 0.6, "height_m": 0.6, "canopy_m": None, "years_to_adult": 1,
    },
}

# Réserve utile du sol (mm d'eau par m de sol), ordres de grandeur FAO-56 tableau 19
SOILS: Dict[str, Dict] = {
    "sableux": {"name": "Sableux", "taw_mm_per_m": 70.0},
    "limoneux": {"name": "Limoneux", "taw_mm_per_m": 140.0},
    "argileux": {"name": "Argileux", "taw_mm_per_m": 180.0},
}

# Efficience de l'irrigation : part de l'eau apportée réellement utilisée par la culture
IRRIGATION: Dict[str, Dict] = {
    "goutte": {"name": "Goutte-à-goutte", "efficiency": 0.90},
    "aspersion": {"name": "Aspersion", "efficiency": 0.75},
    "gravitaire": {"name": "Gravitaire (seguia, submersion)", "efficiency": 0.60},
    "pluvial": {"name": "Pluvial (sans irrigation)", "efficiency": 1.00},
}

KC_BARE_SOIL = 0.15            # Kc minimal (sol nu, FAO-56)
COVER_MULTIPLIER = 2.0         # ML de l'équation 98 (FAO-56)
DEFAULT_HALF_SIDE_M = 100.0    # parcelle de 200 m x 200 m si aucune limite n'est fournie


def _ascii(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower().strip()


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", _ascii(text)).strip("-") or "ferme"


def parse_spacing(text: str) -> Tuple[float, float]:
    """'6x4', '6 × 4', '6*4', '6,5x3' -> (entre rangs, sur le rang) en mètres."""
    parts = re.split(r"\s*[x×X*/]\s*", str(text).strip().replace(",", ".").replace("m", ""))
    if len(parts) == 1 and parts[0]:
        parts = [parts[0], parts[0]]
    if len(parts) != 2:
        raise ValueError(f"Écartement illisible : « {text} ». Exemple attendu : 6x4 (mètres).")
    row, tree = (float(p) for p in parts)
    if row <= 0 or tree <= 0 or row > 30 or tree > 30:
        raise ValueError(f"Écartement hors limites : {row} x {tree} m.")
    return row, tree


def resolve_crop(name: str) -> str:
    key = _ascii(name).replace(" ", "")
    aliases = {"olive": "olivier", "zitoun": "olivier", "zaytoun": "olivier", "nakhil": "palmier",
               "dattier": "palmier", "palmierdattier": "palmier", "citrus": "agrumes", "orange": "agrumes",
               "louz": "amandier", "amande": "amandier", "tofah": "pommier", "pomme": "pommier",
               "raisin": "vigne", "romane": "grenadier", "rommane": "grenadier", "avocat": "avocatier",
               "fessa": "luzerne", "ble": "cereales", "orge": "cereales", "cereale": "cereales",
               "legumes": "maraichage", "tomate": "maraichage"}
    if key in CROPS:
        return key
    if key in aliases:
        return aliases[key]
    for crop_id, crop in CROPS.items():
        if crop["name_ar"] == name.strip() or (key and key in _ascii(crop["name"]).replace(" ", "")):
            return crop_id
    raise ValueError(f"Culture inconnue : « {name} ». Choix : {', '.join(CROPS)}")


@dataclass
class Farm:
    name: str
    latitude: float
    longitude: float
    crop: str
    spacing_row_m: Optional[float] = None
    spacing_tree_m: Optional[float] = None
    area_ha: Optional[float] = None
    planting_year: Optional[int] = None
    canopy_diameter_m: Optional[float] = None
    irrigation: str = "goutte"
    soil: str = "limoneux"
    boundary: Optional[List[List[float]]] = None     # [[lon, lat], ...] (GeoJSON)
    notes: str = ""
    id: str = field(default="")

    def __post_init__(self):
        self.crop = resolve_crop(self.crop)
        if not self.id:
            self.id = slugify(self.name)
        if not is_in_region(self.longitude, self.latitude):
            raise ValueError(f"({self.latitude}, {self.longitude}) est hors du Maroc. "
                             "Vérifiez l'ordre latitude / longitude.")
        if self.irrigation not in IRRIGATION:
            raise ValueError(f"Irrigation inconnue : {self.irrigation}. Choix : {', '.join(IRRIGATION)}")
        if self.soil not in SOILS:
            raise ValueError(f"Sol inconnu : {self.soil}. Choix : {', '.join(SOILS)}")
        tree_crop = CROPS[self.crop]["canopy_m"] is not None
        if tree_crop and (self.spacing_row_m is None or self.spacing_tree_m is None):
            raise ValueError(f"Indiquez l'écartement de plantation pour « {CROPS[self.crop]['name']} » (ex. 6x4).")

    # --- Plantation --------------------------------------------------------
    @property
    def crop_info(self) -> Dict:
        return CROPS[self.crop]

    @property
    def density_per_ha(self) -> Optional[float]:
        if not self.spacing_row_m or not self.spacing_tree_m:
            return None
        return 10000.0 / (self.spacing_row_m * self.spacing_tree_m)

    def canopy_diameter(self, year: int) -> Optional[float]:
        """Diamètre de couronne pour une année : saisi, sinon croissance linéaire jusqu'à l'âge adulte."""
        crop = self.crop_info
        if crop["canopy_m"] is None:
            return None
        if self.canopy_diameter_m:
            return self.canopy_diameter_m
        if not self.planting_year:
            return crop["canopy_m"]
        age = max(0, year - self.planting_year)
        return crop["canopy_m"] * min(1.0, max(0.15, age / crop["years_to_adult"]))

    def ground_cover(self, year: int) -> float:
        """Fraction du sol couverte par la végétation (0-1)."""
        d = self.canopy_diameter(year)
        if d is None:
            return 1.0
        # La couronne ne déborde pas de l'espace alloué à l'arbre
        crown = math.pi * (d / 2) ** 2
        return min(1.0, crown / (self.spacing_row_m * self.spacing_tree_m))

    def kc(self, day: date) -> float:
        """Kc du jour, corrigé par la couverture du sol (FAO-56 éq. 98)."""
        crop = self.crop_info
        kc_full = crop["kc"][day.month - 1]
        if crop["canopy_m"] is None:
            return kc_full
        fc = self.ground_cover(day.year)
        kd = min(1.0, COVER_MULTIPLIER * fc, fc ** (1.0 / (1.0 + crop["height_m"])))
        return KC_BARE_SOIL + kd * (kc_full - KC_BARE_SOIL)

    @property
    def total_available_water_mm(self) -> float:
        return SOILS[self.soil]["taw_mm_per_m"] * self.crop_info["root_m"]

    # --- Géométrie ---------------------------------------------------------
    def parcel_coordinates(self) -> List[List[float]]:
        """Limites de la parcelle, ou carré centré sur le point (surface déclarée, sinon 200 m de côté)."""
        if self.boundary:
            return self.boundary
        half = DEFAULT_HALF_SIDE_M
        if self.area_ha:
            # On reste dans les limites d'une parcelle analysable (< 10 km²)
            half = min(1500.0, math.sqrt(self.area_ha * 10000.0) / 2)
        dlat = half / 111320.0
        dlon = half / (111320.0 * math.cos(math.radians(self.latitude)))
        lat, lon = self.latitude, self.longitude
        return [[lon - dlon, lat - dlat], [lon + dlon, lat - dlat], [lon + dlon, lat + dlat],
                [lon - dlon, lat + dlat], [lon - dlon, lat - dlat]]

    @property
    def zone(self) -> Tuple[str, str, float]:
        return zone_for_point(self.latitude, self.longitude)

    def summary(self) -> str:
        zone_id, place, km = self.zone
        lines = [
            f"{self.name} ({self.id})",
            f"  Position     : {self.latitude:.5f}, {self.longitude:.5f} — {ZONES[zone_id]['name']}, {km:.0f} km de {place}",
            f"  Culture      : {self.crop_info['name']}",
        ]
        if self.density_per_ha:
            lines.append(f"  Écartement   : {self.spacing_row_m:g} x {self.spacing_tree_m:g} m "
                         f"({self.density_per_ha:.0f} plants/ha)")
            year = date.today().year
            lines.append(f"  Couverture   : {self.ground_cover(year):.0%} du sol en {year} "
                         f"(couronne {self.canopy_diameter(year):.1f} m)")
        if self.area_ha:
            lines.append(f"  Surface      : {self.area_ha:g} ha")
        lines.append(f"  Irrigation   : {IRRIGATION[self.irrigation]['name']} ; sol {SOILS[self.soil]['name'].lower()} "
                     f"(réserve utile {self.total_available_water_mm:.0f} mm)")
        return "\n".join(lines)

    # --- Sauvegarde --------------------------------------------------------
    def to_dict(self) -> Dict:
        return asdict(self)

    def save(self, directory: str = "farms") -> Path:
        path = Path(directory) / f"{self.id}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    @classmethod
    def load(cls, path: str) -> "Farm":
        return cls(**json.loads(Path(path).read_text(encoding="utf-8")))
