from datetime import datetime

import numpy as np
import pandas as pd
import pytest

from extract_data import (
    CHIRPSExtractor,
    DataUnavailableError,
    ERA5Extractor,
    assemble_features,
    check_completeness,
    compute_humidity_relative,
    day_of_year_cyclic,
    max_consecutive_dry_days,
)
from train_model import FEATURE_COLUMNS


def chirps_df(values):
    dates = pd.date_range("2024-06-01", periods=len(values), freq="D")
    return pd.DataFrame({"date": dates, "precipitation_mm": values})


def test_dry_days_sequence():
    assert max_consecutive_dry_days(pd.Series([0, 0, 5, 0, 0, 0, 1, 0])) == 3
    assert max_consecutive_dry_days(pd.Series([2, 3])) == 0


def test_chirps_features_use_last_30_days():
    values = [10.0] * 10 + [0.0] * 23 + [1.0, 2.0, 0.0, 0.0, 0.5, 0.0, 0.0]
    feats = CHIRPSExtractor().aggregate_features(chirps_df(values))
    assert feats["precipitation_total_30j"] == pytest.approx(3.5)
    assert feats["precipitation_total_7j"] == pytest.approx(3.5)
    assert feats["rainy_days_count"] == 3
    assert feats["max_consecutive_dry_days"] == 23


def test_chirps_empty_raises():
    with pytest.raises(DataUnavailableError):
        CHIRPSExtractor().aggregate_features(chirps_df([]))


def test_era5_features_use_daily_extremes():
    df = pd.DataFrame({
        "date": pd.date_range("2024-07-01", periods=3),
        "temperature_c": [30.0, 32.0, 34.0],
        "temperature_min_c": [22.0, 24.0, 25.0],
        "temperature_max_c": [40.0, 43.0, 41.0],
        "dewpoint_c": [5.0, 6.0, 4.0],
        "humidity_percent": [20.0, 19.0, 15.0],
        "humidity_min_percent": [9.0, 8.0, 7.0],
    })
    feats = ERA5Extractor().aggregate_features(df)
    assert feats["temperature_max"] == 43.0
    assert feats["temperature_min"] == 22.0
    assert feats["humidity_min"] == 7.0


def test_era5_empty_raises():
    with pytest.raises(DataUnavailableError):
        ERA5Extractor().aggregate_features(pd.DataFrame())


def test_completeness_check():
    check_completeness(chirps_df([0.0] * 30), 30, "CHIRPS")
    with pytest.raises(DataUnavailableError, match="CHIRPS"):
        check_completeness(chirps_df([0.0] * 10), 30, "CHIRPS")


def test_humidity():
    assert compute_humidity_relative(20.0, 20.0) == 100.0
    assert 40 < compute_humidity_relative(25.0, 12.0) < 50
    assert np.isnan(compute_humidity_relative(float("nan"), 10.0))


def test_day_of_year_cyclic_is_unit_circle():
    s, c = day_of_year_cyclic(datetime(2024, 7, 15))
    assert s ** 2 + c ** 2 == pytest.approx(1.0)


def test_assemble_features_matches_model_columns():
    stats = {i: {"mean": 0.3, "min": 0.1, "max": 0.5, "stdDev": 0.05} for i in ["NDVI", "NDWI", "MSI", "SAVI", "EVI"]}
    chirps = CHIRPSExtractor().aggregate_features(chirps_df([0.0] * 30))
    era5 = {"temperature_mean": 30.0, "temperature_max": 42.0, "temperature_min": 20.0,
            "humidity_mean": 25.0, "humidity_min": 8.0}
    site = {"elevation_m": 450.0, "precip_annual_normal_mm": 280.0}
    feats = assemble_features(stats, chirps, era5, datetime(2024, 7, 15), site)
    assert sorted(feats) == sorted(FEATURE_COLUMNS)


def test_service_account_secret_formats():
    from extract_data import parse_service_account_secrets

    raw = '{"type": "service_account", "project_id": "p1", "private_key": "-----BEGIN\\nKEY\\n-----END\\n"}'
    info = parse_service_account_secrets({"GCP_SERVICE_ACCOUNT_JSON": raw})
    assert info["project_id"] == "p1"
    assert info["private_key"].count("\n") == 3

    # JSON collé avec de vrais retours à la ligne dans la clé
    raw_newlines = raw.replace("\\n", "\n")
    assert parse_service_account_secrets({"GCP_SERVICE_ACCOUNT_JSON": raw_newlines})["project_id"] == "p1"

    table = {"GCP_SERVICE_ACCOUNT": {"type": "service_account", "project_id": "p2"}}
    assert parse_service_account_secrets(table)["project_id"] == "p2"
    assert parse_service_account_secrets({}) is None


def test_service_account_from_env_json(monkeypatch):
    import pytest
    from extract_data import _service_account_from_env
    monkeypatch.delenv("EE_SERVICE_ACCOUNT_FILE", raising=False)
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    monkeypatch.setenv("EE_SERVICE_ACCOUNT_JSON", '{"client_email": "a@b.iam", "project_id": "p3"}')
    assert _service_account_from_env()["project_id"] == "p3"
    monkeypatch.setenv("EE_SERVICE_ACCOUNT_JSON", "pas du json")
    with pytest.raises(ValueError):
        _service_account_from_env()
    monkeypatch.delenv("EE_SERVICE_ACCOUNT_JSON")
    assert _service_account_from_env() is None


def test_demo_extraction_is_reproducible_across_processes():
    import subprocess
    import sys
    code = ("from demo import make_demo_extraction;"
            "c=[[-4.233,31.433],[-4.231,31.433],[-4.231,31.431],[-4.233,31.433]];"
            "print(make_demo_extraction(c,'2024-08-15')['features']['NDVI_mean'])")
    runs = {subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True).stdout
            for _ in range(2)}
    assert len(runs) == 1


def test_demo_works_without_earthengine():
    import subprocess
    import sys
    code = ("import sys; sys.modules['ee'] = None;"  # simule earthengine-api absent
            "from demo import make_demo_extraction;"
            "c=[[-4.233,31.433],[-4.231,31.433],[-4.231,31.431],[-4.233,31.433]];"
            "print(len(make_demo_extraction(c,'2024-08-15')['features']))")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
