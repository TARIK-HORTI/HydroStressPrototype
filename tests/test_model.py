import numpy as np
import pandas as pd
import pytest

from generate_training_data import generate_samples
from predict import CROP_TIPS, HydroStressPredictor
from train_model import FEATURE_COLUMNS, LABEL_COLUMN, train_production_model


@pytest.fixture(scope="module")
def synthetic():
    return generate_samples(600, np.random.default_rng(0))


def test_generator_columns_and_classes(synthetic):
    assert list(synthetic.columns) == FEATURE_COLUMNS + [LABEL_COLUMN]
    assert set(synthetic[LABEL_COLUMN].unique()) == {0, 1, 2}
    assert not synthetic.isna().any().any()
    # Contraintes physiques
    assert (synthetic["NDVI_min"] <= synthetic["NDVI_mean"]).all()
    assert (synthetic["NDVI_mean"] <= synthetic["NDVI_max"]).all()
    assert (synthetic["precipitation_total_7j"] <= synthetic["precipitation_total_30j"]).all()
    assert (synthetic["temperature_min"] < synthetic["temperature_max"]).all()


def test_generator_classes_overlap(synthetic):
    """Les classes ne doivent pas être séparables par un seul seuil de NDVI."""
    normal = synthetic.loc[synthetic[LABEL_COLUMN] == 0, "NDVI_mean"]
    severe = synthetic.loc[synthetic[LABEL_COLUMN] == 2, "NDVI_mean"]
    assert normal.min() < severe.max()


def test_train_and_predict_roundtrip(tmp_path, synthetic):
    csv = tmp_path / "train.csv"
    synthetic.to_csv(csv, index=False)
    out = tmp_path / "model" / "hs"
    model, results = train_production_model(str(csv), output_path=str(out), use_grid_search=False,
                                            data_source="synthetic")
    assert model.metadata["test_metrics"]["accuracy"] > 0.4
    assert model.metadata["data_source"] == "synthetic"

    predictor = HydroStressPredictor(model_path=str(out))
    row = synthetic.iloc[0][FEATURE_COLUMNS].to_dict()
    pred = predictor.predict(row)
    assert pred["class_index"] in (0, 1, 2)
    assert sum(pred["probabilities"].values()) == pytest.approx(100, abs=0.1)

    missing = dict(row)
    del missing["NDVI_mean"]
    with pytest.raises(ValueError):
        predictor.predict(missing)
    nan_row = dict(row, NDVI_mean=float("nan"))
    with pytest.raises(ValueError, match="NaN"):
        predictor.predict(nan_row)


def test_grouped_split_keeps_parcels_separate(tmp_path, synthetic):
    df = synthetic.copy()
    df["parcel_id"] = np.arange(len(df)) // 10
    csv = tmp_path / "grouped.csv"
    df.to_csv(csv, index=False)
    model, _ = train_production_model(str(csv), output_path=str(tmp_path / "g"), use_grid_search=False)
    assert model.metadata["test_metrics"]["samples"] > 0


def test_committed_model_loads_and_recommends():
    predictor = HydroStressPredictor()
    assert predictor.metadata["region"] == "Errachidia"
    row = generate_samples(1, np.random.default_rng(1)).iloc[0][FEATURE_COLUMNS].to_dict()
    pred = predictor.predict(row)
    pred["class_index"] = 2
    rec = predictor.get_recommendations(pred, crop="Palmier dattier")
    assert CROP_TIPS["Palmier dattier"][0] in rec["actions"]
    assert all("%%" not in a for a in rec["actions"])


def test_demo_extraction_and_html_report():
    from demo import make_demo_extraction
    from report import build_report, report_to_html

    coords = [[-4.236, 31.430], [-4.230, 31.430], [-4.230, 31.435], [-4.236, 31.435], [-4.236, 31.430]]
    data = make_demo_extraction(coords, "2024-07-15", 30)
    assert data["demo"] is True
    assert sorted(data["features"]) == sorted(FEATURE_COLUMNS)
    assert data["features"]["temperature_max"] == pytest.approx(data["era5_series"]["temperature_max_c"].max())

    predictor = HydroStressPredictor()
    pred = predictor.predict(data["features"])
    report = build_report(
        coordinates=coords, area_km2=0.3, zone="Erfoud (Tafilalet)", crop="Palmier dattier", data=data,
        prediction=pred, recommendations=predictor.get_recommendations(pred, "Palmier dattier"),
        interpretation=predictor.interpret_indices(data["features"]), model_meta=predictor.metadata,
    )
    assert report["parcel"]["area_ha"] == 30.0
    html = report_to_html(report)
    assert "DÉMONSTRATION" in html and "Erfoud" in html and "<script" not in html
