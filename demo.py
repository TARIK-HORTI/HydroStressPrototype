"""
demo.py
=======
Données de DÉMONSTRATION pour visualiser le tableau de bord sans accès
Earth Engine. Les valeurs sont tirées du générateur synthétique calé sur le
climat d'Errachidia : elles ne décrivent pas la parcelle dessinée et sont
signalées comme telles dans l'interface et le rapport.
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List

import numpy as np
import pandas as pd

from extract_data import CHIRPSExtractor, ERA5Extractor, compute_humidity_relative
from generate_training_data import generate_samples
from region import MONTHLY_PRECIP_MM, MONTHLY_TEMP_MEAN_C
from train_model import FEATURE_COLUMNS


def make_demo_extraction(coordinates: List[List[float]], analysis_date: str, lookback_days: int = 30) -> Dict[str, Any]:
    """Retourne un résultat au même format que DataPipeline.extract_all_data, marqué demo=True."""
    end_dt = datetime.strptime(analysis_date, "%Y-%m-%d")
    seed = abs(hash((round(coordinates[0][0], 4), round(coordinates[0][1], 4), analysis_date))) % (2 ** 32)
    rng = np.random.default_rng(seed)

    row = generate_samples(1, rng).iloc[0]
    features = {c: float(row[c]) for c in FEATURE_COLUMNS}
    angle = 2 * np.pi * end_dt.timetuple().tm_yday / 366.0
    features["day_of_year_sin"], features["day_of_year_cos"] = float(np.sin(angle)), float(np.cos(angle))

    days = max(lookback_days, 30)
    dates = [end_dt - timedelta(days=days - 1 - i) for i in range(days)]
    month = end_dt.month - 1

    precip = np.where(rng.random(days) < 0.12, rng.gamma(1.2, MONTHLY_PRECIP_MM[month] / 3 + 0.5, days), 0.0)
    t_mean = MONTHLY_TEMP_MEAN_C[month] + rng.normal(0, 1.8, days)
    t_max = t_mean + rng.uniform(6, 9, days)
    t_min = t_mean - rng.uniform(6, 9, days)
    dew = t_mean - rng.uniform(12, 22, days)
    chirps = pd.DataFrame({"date": pd.to_datetime(dates), "precipitation_mm": precip})
    era5 = pd.DataFrame({
        "date": pd.to_datetime(dates),
        "temperature_c": t_mean,
        "temperature_min_c": t_min,
        "temperature_max_c": t_max,
        "dewpoint_c": dew,
        "humidity_percent": [compute_humidity_relative(t, d) for t, d in zip(t_mean, dew)],
        "humidity_min_percent": [compute_humidity_relative(t, d) for t, d in zip(t_max, dew)],
    })

    # Les features météo sont recalculées depuis les séries pour rester cohérentes avec les graphiques
    features.update(CHIRPSExtractor().aggregate_features(chirps))
    features.update(ERA5Extractor().aggregate_features(era5))

    stats = {}
    for idx in ["NDVI", "NDWI", "MSI", "SAVI", "EVI"]:
        mean = features[f"{idx}_mean"]
        std = features.get(f"{idx}_std", abs(mean) * 0.15 + 0.02)
        stats[idx] = {
            "mean": mean,
            "min": features.get(f"{idx}_min", mean - 2 * std),
            "max": features.get(f"{idx}_max", mean + 2 * std),
            "stdDev": std,
        }

    return {
        "features": features,
        "sentinel_stats": stats,
        "sentinel_meta": {"image_count": 6, "valid_pixel_fraction": 0.92, "window_days": lookback_days},
        "chirps_series": chirps,
        "era5_series": era5,
        "extraction_date": datetime.now().isoformat(),
        "date_analyzed": analysis_date,
        "lookback_days": lookback_days,
        "demo": True,
    }
