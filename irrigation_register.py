"""
irrigation_register.py
======================
Lecture des registres d'irrigation Excel d'une ferme (un fichier par
campagne, une feuille par mois ou une seule feuille pour la campagne).

Les registres changent de mise en page d'une année à l'autre. Pour chaque
feuille, on cherche la ligne d'en-tête qui contient « DATE », puis la colonne
du volume, par ordre de préférence :
  1. « dif /m3 » (différence de compteur d'eau) ou « m3 » : volume de l'apport ;
  2. « m3/ha » : volume par hectare, converti avec la surface du bloc.
Les colonnes « cumul » ne sont jamais utilisées comme volume.

Lignes retenues :
- une ligne datée avec un volume numérique ;
- une ligne sans date mais avec un secteur (« lieu ») : second secteur irrigué
  le même jour que la ligne précédente.
Les lignes de total (sans date ni secteur) sont ignorées.

Chaque fichier couvre une campagne (octobre -> septembre) : les erreurs
d'année fréquentes (2020-10-02 au milieu d'octobre 2021) sont corrigées en
remettant chaque date dans la campagne majoritaire du fichier.

Sortie : une ligne par jour -> date, irrigation_m3, irrigation_mm, apports.
"""

import datetime as dt
import logging
import re
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)

HEADER_SCAN_ROWS = 40


def _norm(value) -> str:
    if value is None:
        return ""
    text = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", "", text)


def _number(value) -> Optional[float]:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _find_columns(header: List[str], sub: List[str]) -> Optional[Dict[str, int]]:
    cols: Dict[str, int] = {}
    if "date" in header:
        cols["date"] = header.index("date")
    elif "ladate" in header:
        cols["date"] = header.index("ladate")
    else:
        return None
    if "lieu" in header:
        cols["lieu"] = header.index("lieu")
    for i, name in enumerate(sub):
        if name in ("dif/m3", "m3"):
            cols["m3"] = i
            break
    else:
        if "m3" in header:
            cols["m3"] = header.index("m3")
    if "m3/ha" in header:
        cols["m3_ha"] = header.index("m3/ha")
    if "m3" not in cols and "m3_ha" not in cols:
        return None
    return cols


def read_sheet(rows: List[tuple], area_ha: float, label: str = "") -> List[Dict]:
    """Extrait les apports d'une feuille (liste de lignes de cellules)."""
    header_idx, cols = None, None
    for i, row in enumerate(rows[:HEADER_SCAN_ROWS]):
        header = [_norm(c) for c in row]
        sub = [_norm(c) for c in rows[i + 1]] if i + 1 < len(rows) else []
        cols = _find_columns(header, sub)
        if cols:
            header_idx = i
            break
    if header_idx is None:
        return []

    def cell(row, key):
        idx = cols.get(key)
        return row[idx] if idx is not None and idx < len(row) else None

    events, current = [], None
    for row in rows[header_idx + 1:]:
        d = cell(row, "date")
        if isinstance(d, dt.datetime):
            current = d.date()
            carried = False
        elif isinstance(d, dt.date):
            current = d
            carried = False
        elif d in (None, ""):
            carried = True
        else:
            continue          # « cumul », « l'arrêt d'irrigation »...
        if current is None:
            continue
        lieu = cell(row, "lieu")
        if carried and not (isinstance(lieu, str) and lieu.strip() and _norm(lieu) not in ("cumul", "total")):
            continue          # ligne de total
        m3 = _number(cell(row, "m3"))
        if m3 is None:
            per_ha = _number(cell(row, "m3_ha"))
            m3 = per_ha * area_ha if per_ha is not None else None
        if m3 is None or m3 < 0:
            continue
        events.append({"date": current, "m3": m3, "lieu": str(lieu).strip() if lieu else "", "sheet": label})

    return events


def fix_campaign_years(events: List[Dict], first_month: int = 10) -> None:
    """
    Un registre couvre une campagne (octobre -> septembre). On retient la
    campagne majoritaire du fichier et on remet chaque date dans cette campagne :
    corrige les années mal saisies (2020-10-02 au milieu d'octobre 2021).
    """
    if not events:
        return
    starts = Counter(e["date"].year if e["date"].month >= first_month else e["date"].year - 1 for e in events)
    start = starts.most_common(1)[0][0]
    for e in events:
        year = start if e["date"].month >= first_month else start + 1
        if e["date"].year != year:
            logger.info(f"Date corrigée : {e['date']} -> année {year} ({e['sheet']})")
            e["date"] = e["date"].replace(year=year)


def read_workbook(path: str, area_ha: float, one_campaign: bool = True) -> List[Dict]:
    import openpyxl

    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    events = []
    for ws in wb.worksheets:
        rows = [tuple(r) for r in ws.iter_rows(values_only=True)]
        found = read_sheet(rows, area_ha, label=f"{Path(path).name} / {ws.title}")
        if found:
            logger.info(f"{Path(path).name} / {ws.title} : {len(found)} apport(s)")
        events.extend(found)
    wb.close()
    if one_campaign:
        fix_campaign_years(events)
    return events


def read_registers(paths: Iterable[str], area_ha: float) -> pd.DataFrame:
    """
    Lit plusieurs registres (xlsx ou csv déjà propre avec date + m3) et
    renvoie une série quotidienne triée : date, irrigation_m3, irrigation_mm, apports.
    """
    events = []
    for p in paths:
        if str(p).lower().endswith(".csv"):
            df = pd.read_csv(p, parse_dates=["date"])
            for d, m3 in zip(df["date"], df["irrigation_m3"]):
                events.append({"date": d.date(), "m3": float(m3), "lieu": "", "sheet": Path(p).name})
        else:
            events.extend(read_workbook(p, area_ha))
    if not events:
        raise ValueError("Aucun apport d'irrigation trouvé dans les fichiers.")
    df = pd.DataFrame(events)
    daily = df.groupby("date").agg(irrigation_m3=("m3", "sum"), apports=("m3", "size")).reset_index()
    daily["date"] = pd.to_datetime(daily["date"])
    # 1 mm sur 1 ha = 10 m3
    daily["irrigation_mm"] = daily["irrigation_m3"] / (area_ha * 10.0)
    return daily.sort_values("date").reset_index(drop=True)


def campaign_of(day: pd.Timestamp, first_month: int = 10) -> str:
    """Campagne agricole (octobre -> septembre par défaut) : 2021-10-05 -> '2021/2022'."""
    y = day.year if day.month >= first_month else day.year - 1
    return f"{y}/{y + 1}"


def coverage_report(daily: pd.DataFrame) -> pd.DataFrame:
    """Volume et nombre de jours irrigués par mois, pour repérer les mois manquants."""
    by_month = daily.groupby(daily["date"].dt.to_period("M")).agg(
        jours_irrigues=("irrigation_m3", "size"), m3=("irrigation_m3", "sum"), mm=("irrigation_mm", "sum"))
    full = pd.period_range(by_month.index.min(), by_month.index.max(), freq="M")
    return by_month.reindex(full, fill_value=0)


def covered_months(daily: pd.DataFrame, max_gap_months: int = 3) -> set:
    """
    Mois pour lesquels le registre est considéré complet : mois avec au moins
    un apport, plus les trous de `max_gap_months` mois au plus entre deux mois
    renseignés (arrêt d'irrigation en hiver). Au-delà, les mois sont inconnus
    (registre manquant) et ne doivent pas servir à étiqueter.
    """
    months = sorted(set(daily["date"].dt.to_period("M")))
    covered = set(months)
    for a, b in zip(months, months[1:]):
        gap = (b - a).n - 1
        if 0 < gap <= max_gap_months:
            covered.update(pd.period_range(a + 1, b - 1, freq="M"))
    return covered
