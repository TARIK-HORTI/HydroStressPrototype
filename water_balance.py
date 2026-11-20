"""
water_balance.py
================
Bilan hydrique quotidien de la zone racinaire (FAO-56, chapitre 8) à partir
du climat téléchargé et des apports d'irrigation réels de la ferme.

    Dr(j) = Dr(j-1) - Pluie_efficace(j) - Irrigation_nette(j) + ETc_réelle(j)
    ETc_réelle = Ks x Kc x ET0
    Ks = 1 si Dr <= RAW, sinon (TAW - Dr) / (TAW - RAW)

- TAW (réserve utile) = réserve du sol (mm/m) x profondeur racinaire ;
- RAW = p x TAW, la part consommable sans stress ;
- Kc vient de la culture et de la couverture du sol (écartement, âge : farm.py) ;
- Irrigation nette = apport x efficience du système (goutte-à-goutte 90 %...).

Ks mesure la contrainte hydrique subie par la culture (1 = aucune). Sa
moyenne sur les jours précédant une date donne l'étiquette du modèle :
    Ks moyen >= 0.85 -> 0 Normal ; 0.60 - 0.85 -> 1 Modéré ; < 0.60 -> 2 Sévère.
Ces seuils sont ceux couramment utilisés pour le pilotage (Ks 0.85 ≈ début de
fermeture des stomates) ; ils se règlent avec --ks-thresholds.

Limites : réserve du sol et profondeur racinaire sont des valeurs types ; les
apports de pluie < 5 mm sont considérés comme perdus par évaporation.
"""

from typing import Optional, Tuple

import pandas as pd

from farm import IRRIGATION, Farm

EFFECTIVE_RAIN_MIN_MM = 5.0
EFFECTIVE_RAIN_FRACTION = 0.8
KS_THRESHOLDS: Tuple[float, float] = (0.60, 0.85)
LABEL_WINDOW_DAYS = 10


def effective_rain(p_mm: float) -> float:
    return 0.0 if p_mm < EFFECTIVE_RAIN_MIN_MM else EFFECTIVE_RAIN_FRACTION * p_mm


def run_water_balance(climate: pd.DataFrame, irrigation: Optional[pd.DataFrame], farm: Farm,
                      initial_depletion: float = 0.0) -> pd.DataFrame:
    """
    climate : date, precipitation_mm, et0_mm (climate_history)
    irrigation : date, irrigation_mm (irrigation_register) ; None = culture en sec
    Renvoie une ligne par jour avec kc, etc_mm, eta_mm, depletion_mm, ks.
    """
    df = climate[["date", "precipitation_mm", "et0_mm"]].copy().sort_values("date").reset_index(drop=True)
    df["et0_mm"] = df["et0_mm"].interpolate(limit_direction="both")
    df["precipitation_mm"] = df["precipitation_mm"].fillna(0.0)
    if irrigation is not None and not irrigation.empty:
        irr = irrigation.groupby("date")["irrigation_mm"].sum()
        df["irrigation_mm"] = df["date"].map(irr).fillna(0.0)
    else:
        df["irrigation_mm"] = 0.0

    taw = farm.total_available_water_mm
    raw = farm.crop_info["p"] * taw
    efficiency = IRRIGATION[farm.irrigation]["efficiency"]

    dr = min(max(initial_depletion, 0.0), taw)
    kcs, etcs, etas, drs, kss, peffs = [], [], [], [], [], []
    for day, p, et0, irr in zip(df["date"], df["precipitation_mm"], df["et0_mm"], df["irrigation_mm"]):
        kc = farm.kc(day.date())
        etc = kc * et0
        ks = 1.0 if dr <= raw else max(0.0, (taw - dr) / (taw - raw))
        eta = ks * etc
        peff = effective_rain(p)
        # Ce qui dépasse la réserve utile est perdu (percolation)
        dr = min(taw, max(0.0, dr - peff - irr * efficiency + eta))
        kcs.append(kc); etcs.append(etc); etas.append(eta); drs.append(dr); kss.append(ks); peffs.append(peff)

    df["kc"], df["etc_mm"], df["eta_mm"] = kcs, etcs, etas
    df["effective_rain_mm"], df["depletion_mm"], df["ks"] = peffs, drs, kss
    df["taw_mm"], df["raw_mm"] = taw, raw
    return df


def ks_to_class(ks: float, thresholds: Tuple[float, float] = KS_THRESHOLDS) -> int:
    severe, moderate = thresholds
    if ks >= moderate:
        return 0
    if ks >= severe:
        return 1
    return 2


def label_at(balance: pd.DataFrame, on: pd.Timestamp, window_days: int = LABEL_WINDOW_DAYS,
             thresholds: Tuple[float, float] = KS_THRESHOLDS) -> Tuple[int, float]:
    """Classe de stress et Ks moyen sur les `window_days` jours finissant à `on`."""
    on = pd.Timestamp(on)
    win = balance[(balance["date"] > on - pd.Timedelta(days=window_days)) & (balance["date"] <= on)]
    if win.empty:
        raise ValueError(f"Pas de bilan hydrique pour le {on:%Y-%m-%d}")
    ks = float(win["ks"].mean())
    return ks_to_class(ks, thresholds), ks
