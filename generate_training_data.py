"""
generate_training_data.py
=========================
Génère un dataset d'entraînement SYNTHÉTIQUE calé sur les climats des
grandes zones agricoles du Maroc (du Gharb humide aux oasis du Drâa).

Ce dataset sert uniquement à faire tourner le prototype de bout en bout.
Il ne remplace pas des données de terrain annotées : utilisez
build_dataset.py (étiquettes VHI dérivées de MODIS) ou vos propres relevés
pour un modèle exploitable.

Principe :
1. Une zone, une date et une météo sont tirées autour des normales mensuelles
   de la zone (region.ZONES), avec l'altitude et le cumul annuel moyen du site.
2. Chaque parcelle a un niveau d'approvisionnement en eau (irrigation, khettara,
   crue du Ziz) et un potentiel de végétation (palmeraie, luzerne, céréales...).
3. Un score de stress latent combine manque d'eau, chaleur et sécheresse.
4. Les indices spectraux découlent du score avec du bruit ; l'étiquette découle
   du score avec du bruit. Les classes se chevauchent donc comme sur le terrain.
"""

import argparse

import numpy as np
import pandas as pd

from typing import Optional

from region import ZONES

STRESS_THRESHOLDS = (0.40, 0.62)  # normal < 0.40 <= modéré < 0.62 <= sévère
LABEL_NOISE = 0.05


def _month_from_doy(doy: np.ndarray) -> np.ndarray:
    dates = pd.to_datetime("2023-01-01") + pd.to_timedelta(doy - 1, unit="D")
    return dates.month.values - 1


def generate_samples(n: int, rng: np.random.Generator, zone_id: Optional[str] = None) -> pd.DataFrame:
    """
    Génère n parcelles-dates synthétiques.

    Args:
        zone_id: zone de region.ZONES ; si None, les zones sont tirées au hasard
    """
    zone_ids = np.array([zone_id] * n) if zone_id else rng.choice(list(ZONES), n)
    norm = {k: np.array([ZONES[z][k] for z in zone_ids]) for k in ("temp", "diurnal", "precip", "rh")}
    doy = rng.integers(1, 366, n)
    month = _month_from_doy(doy)
    rows = np.arange(n)

    # Site : altitude et normale annuelle de pluie
    elev_lo = np.array([ZONES[z]["elevation"][0] for z in zone_ids])
    elev_hi = np.array([ZONES[z]["elevation"][1] for z in zone_ids])
    elevation = rng.uniform(elev_lo, elev_hi)
    annual_normal = norm["precip"].sum(axis=1) * rng.normal(1.0, 0.15, n).clip(0.6, 1.5)
    rain_factor = annual_normal / norm["precip"].sum(axis=1)

    # --- Météo ------------------------------------------------------------
    temp_anom = rng.normal(0, 2.0, n)
    temp_mean = norm["temp"][rows, month] + temp_anom
    diurnal = norm["diurnal"][rows, month] + rng.normal(0, 1.5, n)
    temp_max = temp_mean + diurnal / 2 + rng.uniform(2, 6, n)   # max absolu sur 30 j
    temp_min = temp_mean - diurnal / 2 - rng.uniform(2, 5, n)   # min absolu sur 30 j

    normal_rain = norm["precip"][rows, month] * rain_factor
    has_rain = rng.random(n) < 0.65
    precip_30j = np.where(has_rain, rng.gamma(0.8, normal_rain / 0.8 * 1.3), 0.0)
    precip_7j = precip_30j * rng.beta(1.2, 3.0, n)
    rainy_days = np.where(precip_30j > 0, np.clip(np.round(precip_30j / 4 + rng.poisson(1, n)), 1, 12), 0)
    dry_days = np.clip(30 - rainy_days * rng.uniform(1.5, 3.5, n), 3, 30).round()

    rh_mean = np.clip(norm["rh"][rows, month] - 1.5 * temp_anom + precip_30j / 4 + rng.normal(0, 5, n), 8, 90)
    rh_min = np.clip(rh_mean - rng.uniform(12, 25, n), 3, rh_mean)

    # --- Parcelle -----------------------------------------------------------
    water_supply = rng.beta(2.0, 1.6, n)            # 0 = aucune irrigation, 1 = optimale
    # Potentiel de végétation : plus élevé dans les zones humides (Gharb) que dans les oasis
    humid = np.clip((annual_normal - 100) / 500, 0, 1)
    ndvi_potential = rng.uniform(0.40, 0.68, n) + 0.10 * humid

    # --- Score de stress latent --------------------------------------------
    heat = np.clip((temp_max - 30) / 18, 0, 1)
    drought = 1 - np.clip(precip_30j / (2 * normal_rain + 5), 0, 1)
    dryness_air = 1 - rh_mean / 90
    stress = (
        0.55 * (1 - water_supply)
        + 0.20 * heat
        + 0.10 * drought
        + 0.15 * dryness_air
        + rng.normal(0, 0.04, n)
    )
    stress = np.clip(stress, 0, 1)

    # --- Indices spectraux ---------------------------------------------------
    ndvi = np.clip(ndvi_potential * (1 - 0.80 * stress) + rng.normal(0, 0.035, n), 0.03, 0.9)
    ndvi_std = rng.uniform(0.04, 0.14, n)
    ndvi_min = np.clip(ndvi - rng.uniform(1.2, 2.5, n) * ndvi_std, -0.1, ndvi)
    ndvi_max = np.clip(ndvi + rng.uniform(1.2, 2.5, n) * ndvi_std, ndvi, 0.95)

    ndwi = np.clip(-0.22 + 0.85 * ndvi - 0.12 * stress + rng.normal(0, 0.03, n), -0.4, 0.6)
    ndwi_std = rng.uniform(0.03, 0.10, n)

    msi = (1 - ndwi) / (1 + ndwi) * rng.normal(1.0, 0.03, n)   # MSI = SWIR/NIR
    msi_std = rng.uniform(0.05, 0.20, n)
    msi_min = np.clip(msi - rng.uniform(1.2, 2.5, n) * msi_std, 0.1, msi)
    msi_max = msi + rng.uniform(1.2, 2.5, n) * msi_std

    savi = np.clip(0.72 * ndvi + rng.normal(0, 0.02, n), -0.1, 0.9)
    evi = np.clip(0.62 * ndvi + rng.normal(0, 0.025, n), -0.1, 0.9)

    # --- Étiquettes ------------------------------------------------------------
    label = np.digitize(stress, STRESS_THRESHOLDS)
    flip = rng.random(n) < LABEL_NOISE
    label[flip] = np.clip(label[flip] + rng.choice([-1, 1], flip.sum()), 0, 2)

    angle = 2 * np.pi * doy / 366.0
    return pd.DataFrame({
        "NDVI_mean": ndvi,
        "NDWI_mean": ndwi,
        "MSI_mean": msi,
        "SAVI_mean": savi,
        "EVI_mean": evi,
        "NDVI_min": ndvi_min,
        "NDVI_max": ndvi_max,
        "NDVI_std": ndvi_std,
        "NDWI_std": ndwi_std,
        "MSI_min": msi_min,
        "MSI_max": msi_max,
        "MSI_std": msi_std,
        "precipitation_total_30j": precip_30j,
        "precipitation_total_7j": precip_7j,
        "precipitation_mean": precip_30j / 30.0,
        "max_consecutive_dry_days": dry_days,
        "rainy_days_count": rainy_days,
        "temperature_mean": temp_mean,
        "temperature_max": temp_max,
        "temperature_min": temp_min,
        "humidity_mean": rh_mean,
        "humidity_min": rh_min,
        "day_of_year_sin": np.sin(angle),
        "day_of_year_cos": np.cos(angle),
        "elevation_m": elevation,
        "precip_annual_normal_mm": annual_normal,
        "stress_class": label.astype(int),
        "zone": zone_ids,
    })


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-n", "--samples", type=int, default=3000)
    parser.add_argument("-o", "--output", default="training_data.csv")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--zone", choices=list(ZONES), default=None,
                        help="Limiter à une zone (par défaut : toutes les zones du Maroc)")
    args = parser.parse_args()

    df = generate_samples(args.samples, np.random.default_rng(args.seed), args.zone)
    df.to_csv(args.output, index=False)
    print(f"✅ Dataset synthétique (Maroc) : {args.output}")
    print(f"   {len(df)} échantillons")
    print(f"   Distribution : {df['stress_class'].value_counts().sort_index().to_dict()}")


if __name__ == "__main__":
    main()
