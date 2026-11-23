from datetime import date

import pandas as pd

from imagery import (
    LAYERS,
    SERIES_INDICES,
    THEMES,
    anomaly_years,
    clean_series,
    default_period,
    diff_layer,
    layers_for_theme,
    legend_html,
    trend,
)


def test_every_layer_has_a_theme_and_valid_range():
    for key, spec in LAYERS.items():
        assert spec["theme"] in THEMES, key
        assert spec["min"] < spec["max"], key
        if spec["palette"]:
            assert all(c.startswith("#") and len(c) == 7 for c in spec["palette"])
    for theme in THEMES:
        assert layers_for_theme(theme)
    assert set(SERIES_INDICES) <= set(LAYERS)


def test_three_monitoring_themes():
    assert {"NDMI", "MSI"} <= set(layers_for_theme("water"))
    assert {"NDRE", "PSRI"} <= set(layers_for_theme("health"))
    assert {"NDVI", "NDVI_ANOM", "NDVI_ZONES"} <= set(layers_for_theme("growth"))


def test_trend_reads_direction_per_index():
    assert trend("NDVI", 0.40, 0.50)["status"] == "better"
    assert trend("NDVI", 0.50, 0.40)["status"] == "worse"
    assert trend("NDVI", 0.50, 0.51)["status"] == "stable"
    # MSI et PSRI : une hausse est une dégradation
    assert trend("MSI", 0.8, 1.2)["status"] == "worse"
    assert trend("PSRI", 0.10, 0.02)["status"] == "better"
    assert trend("NDMI", None, 0.2)["status"] == "unknown"


def test_diff_layer_is_symmetric_and_reversed_when_high_is_bad():
    d = diff_layer("NDVI")
    assert d["min"] == -d["max"]
    assert diff_layer("MSI")["palette"] == list(reversed(d["palette"]))


def test_clean_series_keeps_clearest_tile_per_day():
    rows = [
        {"date": "2025-06-01", "clear": 0.95, "NDVI": 0.5, "NDMI": 0.2, "NDRE": 0.3, "PSRI": 0.0, "MSI": 0.8},
        {"date": "2025-06-01", "clear": 0.85, "NDVI": 0.4, "NDMI": 0.1, "NDRE": 0.2, "PSRI": 0.1, "MSI": 0.9},
        {"date": "2025-06-06", "clear": 0.30, "NDVI": 0.2, "NDMI": 0.0, "NDRE": 0.1, "PSRI": 0.1, "MSI": 1.0},
        {"date": "2025-05-27", "clear": 1.0, "NDVI": None},
    ]
    df = clean_series(rows)
    assert list(df["date"]) == [pd.Timestamp("2025-06-01")]
    assert df.loc[0, "NDVI"] == 0.5
    assert clean_series([]).empty


def test_anomaly_years_and_period():
    assert anomaly_years(date(2026, 7, 1)) == [2021, 2022, 2023, 2024, 2025]
    assert anomaly_years(date(2019, 7, 1)) == [2018]
    start, end = default_period(date(2026, 11, 23))
    assert end == date(2026, 11, 23) and 360 <= (end - start).days <= 370


def test_legend_html_contains_bounds():
    html = legend_html(-0.2, 0.2, ["#000000", "#ffffff"], "bas", "haut", "Titre")
    assert "-0.2" in html and "0.2" in html and "linear-gradient" in html and "Titre" in html
