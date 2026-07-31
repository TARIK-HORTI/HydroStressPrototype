"""
generate_training_data.py
=========================
Génère un dataset d'entraînement synthétique réaliste pour HydroStressPrototype.
À remplacer par vos vraies données annotées en production.
"""

import numpy as np
import pandas as pd


def generate_class_samples(n, class_idx):
    """
    Génère des échantillons cohérents pour une classe de stress hydrique.

    Classe 0 (Normal)  : NDVI élevé, NDWI élevé, MSI bas, pluie suffisante
    Classe 1 (Modéré)  : NDVI moyen, NDWI moyen, MSI moyen, pluie réduite  
    Classe 2 (Sévère)  : NDVI bas, NDWI bas, MSI élevé, sécheresse
    """
    if class_idx == 0:  # Normal
        ndvi_mean = np.random.uniform(0.55, 0.85, n)
        ndwi_mean = np.random.uniform(0.40, 0.70, n)
        msi_mean = np.random.uniform(0.40, 0.90, n)
        precip_30j = np.random.uniform(40, 120, n)
        temp_mean = np.random.uniform(20, 28, n)
        humidity = np.random.uniform(55, 80, n)
        dry_days = np.random.uniform(0, 5, n)
    elif class_idx == 1:  # Modéré
        ndvi_mean = np.random.uniform(0.30, 0.55, n)
        ndwi_mean = np.random.uniform(0.15, 0.40, n)
        msi_mean = np.random.uniform(0.90, 1.50, n)
        precip_30j = np.random.uniform(10, 40, n)
        temp_mean = np.random.uniform(28, 35, n)
        humidity = np.random.uniform(35, 55, n)
        dry_days = np.random.uniform(5, 15, n)
    else:  # Sévère
        ndvi_mean = np.random.uniform(0.05, 0.30, n)
        ndwi_mean = np.random.uniform(-0.10, 0.15, n)
        msi_mean = np.random.uniform(1.50, 2.50, n)
        precip_30j = np.random.uniform(0, 15, n)
        temp_mean = np.random.uniform(32, 42, n)
        humidity = np.random.uniform(15, 35, n)
        dry_days = np.random.uniform(15, 30, n)

    # Features dérivées cohérentes
    ndvi_min = ndvi_mean - np.random.uniform(0.05, 0.20, n)
    ndvi_max = ndvi_mean + np.random.uniform(0.05, 0.20, n)
    ndvi_std = np.random.uniform(0.03, 0.12, n)
    ndwi_std = np.random.uniform(0.02, 0.10, n)
    msi_min = msi_mean - np.random.uniform(0.05, 0.25, n)
    msi_max = msi_mean + np.random.uniform(0.05, 0.25, n)
    msi_std = np.random.uniform(0.05, 0.20, n)

    savi_mean = ndvi_mean * 0.9 + np.random.normal(0, 0.02, n)
    evi_mean = ndvi_mean * 0.75 + np.random.normal(0, 0.03, n)

    precip_7j = precip_30j * np.random.uniform(0.15, 0.35, n)
    precip_mean = precip_30j / 30.0
    rainy_days = np.random.uniform(3, 20, n)

    temp_max = temp_mean + np.random.uniform(3, 10, n)
    temp_min = temp_mean - np.random.uniform(3, 10, n)
    humidity_min = humidity - np.random.uniform(5, 20, n)

    # Jour de l'année cyclique
    doy = np.random.randint(1, 366, n)
    sin_doy = np.sin(2 * np.pi * doy / 366)
    cos_doy = np.cos(2 * np.pi * doy / 366)

    return pd.DataFrame({
        'NDVI_mean': ndvi_mean,
        'NDWI_mean': ndwi_mean,
        'MSI_mean': msi_mean,
        'SAVI_mean': savi_mean,
        'EVI_mean': evi_mean,
        'NDVI_min': ndvi_min,
        'NDVI_max': ndvi_max,
        'NDVI_std': ndvi_std,
        'NDWI_std': ndwi_std,
        'MSI_min': msi_min,
        'MSI_max': msi_max,
        'MSI_std': msi_std,
        'precipitation_total_30j': precip_30j,
        'precipitation_total_7j': precip_7j,
        'precipitation_mean': precip_mean,
        'max_consecutive_dry_days': dry_days,
        'rainy_days_count': rainy_days,
        'temperature_mean': temp_mean,
        'temperature_max': temp_max,
        'temperature_min': temp_min,
        'humidity_mean': humidity,
        'humidity_min': humidity_min,
        'day_of_year_sin': sin_doy,
        'day_of_year_cos': cos_doy,
        'stress_class': class_idx,
    })


if __name__ == "__main__":
    np.random.seed(42)
    n_total = 500

    # Génération équilibrée des 3 classes
    n_per_class = n_total // 3
    df = pd.concat([
        generate_class_samples(n_per_class, 0),
        generate_class_samples(n_per_class, 1),
        generate_class_samples(n_total - 2 * n_per_class, 2),
    ], ignore_index=True)

    # Mélange aléatoire
    df = df.sample(frac=1, random_state=42).reset_index(drop=True)

    # Sauvegarde
    output_file = "training_data.csv"
    df.to_csv(output_file, index=False)

    print(f"✅ Dataset généré : {output_file}")
    print(f"   {len(df)} échantillons")
    print(f"   Distribution : {dict(df['stress_class'].value_counts().sort_index())}")
