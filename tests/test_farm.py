"""Tests de l'entraînement sur données de ferme (sans réseau ni Earth Engine)."""
import datetime as dt

import numpy as np
import pandas as pd
import pytest

import climate_history
import farm_dataset
from farm import Farm, parse_spacing, resolve_crop
from irrigation_register import covered_months, fix_campaign_years, read_registers, read_sheet
from train_model import FEATURE_COLUMNS
from water_balance import label_at, ks_to_class, run_water_balance


def make_farm(**kw):
    args = dict(name="Bloc 4", latitude=31.887705, longitude=-4.155879, crop="amandier",
                spacing_row_m=7, spacing_tree_m=5, area_ha=102, planting_year=2018, soil="sableux")
    args.update(kw)
    return Farm(**args)


# --- Ferme -------------------------------------------------------------------
@pytest.mark.parametrize("text,expected", [("6x4", (6, 4)), ("7 × 5", (7, 5)), ("6,5*3", (6.5, 3)), ("8", (8, 8))])
def test_parse_spacing(text, expected):
    assert parse_spacing(text) == expected


def test_parse_spacing_rejects_garbage():
    with pytest.raises(ValueError):
        parse_spacing("abc")


def test_resolve_crop_aliases():
    assert resolve_crop("Amandier") == "amandier"
    assert resolve_crop("louz") == "amandier"
    assert resolve_crop("النخيل") == "palmier"
    with pytest.raises(ValueError):
        resolve_crop("baobab")


def test_farm_density_cover_and_kc():
    f = make_farm()
    assert f.density_per_ha == pytest.approx(10000 / 35)
    # Jeune verger : couverture et Kc plus faibles qu'à l'âge adulte
    assert f.ground_cover(2019) < f.ground_cover(2026)
    assert f.kc(dt.date(2019, 7, 1)) < f.kc(dt.date(2026, 7, 1)) <= 0.90
    assert f.total_available_water_mm == pytest.approx(70 * 1.4)


def test_farm_rejects_outside_morocco_and_missing_spacing():
    with pytest.raises(ValueError):
        make_farm(latitude=48.85, longitude=2.35)
    with pytest.raises(ValueError):
        make_farm(spacing_row_m=None)


def test_farm_save_load_roundtrip(tmp_path):
    f = make_farm()
    loaded = Farm.load(f.save(tmp_path))
    assert loaded == f
    coords = loaded.parcel_coordinates()
    assert coords[0] == coords[-1] and len(coords) == 5


# --- Registres d'irrigation ---------------------------------------------------
def test_read_sheet_meter_layout_with_second_sector_and_totals():
    rows = [
        (" Irrigation bloc 4 ",),
        ("DATE", "lieu", "compteur heur", None, None, "compteur eau", None, None, "m3/h", "m3/ha", "Cumul m3/ha"),
        (None, None, "du", "au", "dif/h", "du", "au", "dif /m3"),
        (dt.datetime(2023, 7, 1), "B4S1", None, None, 10, 100, 3474, 3374, 337.4, 33.08, 4853.7),
        (None, "B4S2", None, None, 10, 3474, 6870, 3396, 339.6, 33.29, 4887.0),
        (dt.datetime(2023, 7, 2), "B4S1", None, None, 10, 0, 0, 3534, 353.4, 34.6, 4921.7),
        (None, None, None, None, None, None, None, None, None, 1437.6, None),   # total du mois
        ("cumul", 60961),
    ]
    events = read_sheet(rows, area_ha=102)
    assert [e["m3"] for e in events] == [3374, 3396, 3534]
    assert events[1]["date"] == dt.date(2023, 7, 1)


def test_read_sheet_m3_per_ha_only():
    rows = [("DATE", "lieu", "m3/h", "m3/ha", "Cumul culture amandier m3/ha"),
            (dt.datetime(2024, 10, 1), "B4S1", 364.7, 10.0, 10.0)]
    assert read_sheet(rows, area_ha=102)[0]["m3"] == pytest.approx(1020)


def test_campaign_year_typos_are_fixed():
    events = [{"date": dt.date(2021, 10, 1), "sheet": ""}, {"date": dt.date(2020, 10, 2), "sheet": ""},
              {"date": dt.date(2021, 10, 3), "sheet": ""}, {"date": dt.date(2022, 5, 1), "sheet": ""}]
    fix_campaign_years(events)
    assert [e["date"].year for e in events] == [2021, 2021, 2021, 2022]


def test_read_registers_xlsx(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "octobre 2020"
    ws.append(["registre irrigation bloc 4"])
    ws.append(["DATE", "lieu", "durée", "m3", "cumul", "m3 / ha"])
    ws.append([dt.datetime(2020, 10, 1), "bloc 4", 6, 1020, 1020, 10])
    ws.append([dt.datetime(2020, 10, 3), "_", 6, 2040, 3060, 30])
    path = tmp_path / "irrigation 2020-2021.xlsx"
    wb.save(path)
    daily = read_registers([str(path)], area_ha=102)
    assert daily["irrigation_mm"].tolist() == pytest.approx([1.0, 2.0])


def test_covered_months_fills_short_winter_stops_only():
    dates = pd.to_datetime(["2023-11-05", "2024-02-10", "2024-10-01"])
    covered = covered_months(pd.DataFrame({"date": dates}))
    assert pd.Period("2024-01", "M") in covered
    assert pd.Period("2024-06", "M") not in covered


# --- Climat --------------------------------------------------------------------
class FakeResponse:
    def __init__(self, payload, status=200):
        self.payload, self.status_code = payload, status

    def json(self):
        return self.payload

    def raise_for_status(self):
        pass


class FakeSession:
    def __init__(self, payload):
        self.payload, self.calls = payload, []

    def get(self, url, params=None, timeout=None):
        self.calls.append((url, params))
        return FakeResponse(self.payload)


def test_fetch_open_meteo_maps_columns():
    payload = {"elevation": 1040, "daily": {
        "time": ["2020-07-01", "2020-07-02"],
        "precipitation_sum": [0.0, 3.2], "temperature_2m_mean": [31, 30],
        "temperature_2m_min": [22, 21], "temperature_2m_max": [40, 39],
        "relative_humidity_2m_mean": [20, 25], "relative_humidity_2m_min": [8, 10],
        "et0_fao_evapotranspiration": [8.1, 7.9]}}
    session = FakeSession(payload)
    df = climate_history.fetch_open_meteo(31.88, -4.15, "2020-07-01", "2020-07-02", session=session)
    assert list(df.columns) == climate_history.COLUMNS
    assert df["et0_mm"].tolist() == [8.1, 7.9]
    assert session.calls[0][1]["models"] == "era5_land"
    assert df.attrs["elevation_m"] == 1040


def test_fetch_nasa_power_computes_et0_and_rh_min():
    days = {"20200701": 0, "20200702": 0}
    payload = {"header": {"fill_value": -999}, "geometry": {"coordinates": [-4.15, 31.88, 1050]},
               "properties": {"parameter": {
                   "PRECTOTCORR": {k: 0.0 for k in days}, "T2M": {k: 31.0 for k in days},
                   "T2M_MIN": {k: 22.0 for k in days}, "T2M_MAX": {"20200701": 40.0, "20200702": -999},
                   "RH2M": {k: 20.0 for k in days}, "T2MDEW": {k: 2.0 for k in days}}}}
    df = climate_history.fetch_nasa_power(31.88, -4.15, "2020-07-01", "2020-07-02", session=FakeSession(payload))
    assert 6 < df.loc[0, "et0_mm"] < 10        # été à Errachidia
    assert df.loc[0, "humidity_min_percent"] < df.loc[0, "humidity_percent"]
    assert np.isnan(df.loc[1, "et0_mm"])


def synthetic_climate(start="2018-01-01", end="2024-12-31", seed=0):
    rng = np.random.default_rng(seed)
    d = pd.date_range(start, end)
    m = d.month - 1
    et0 = np.array([2.2, 3, 4.3, 5.5, 6.8, 8, 8.5, 7.6, 5.8, 4, 2.6, 2])[m]
    t = np.array([8, 11, 14, 18, 22, 27, 31, 30, 25, 19, 13, 9])[m] + rng.normal(0, 1, len(d))
    return pd.DataFrame({
        "date": d, "precipitation_mm": np.where(rng.random(len(d)) < 0.05, 8.0, 0.0),
        "temperature_c": t, "temperature_min_c": t - 7, "temperature_max_c": t + 8,
        "humidity_percent": 40.0, "humidity_min_percent": 18.0, "et0_mm": et0,
    })


def test_weather_features_match_model_columns():
    feats = climate_history.weather_features(synthetic_climate(), pd.Timestamp("2020-07-15"))
    assert set(feats) <= set(FEATURE_COLUMNS) and len(feats) == 10
    assert feats["temperature_max"] > feats["temperature_mean"] > feats["temperature_min"]


def test_download_climate_splits_by_year_and_caches(tmp_path, monkeypatch):
    calls = []

    def fake(lat, lon, start, end, session=None):
        calls.append((start, end))
        df = synthetic_climate(start, end)[climate_history.COLUMNS]
        df.attrs["source"] = "fake"
        return df

    monkeypatch.setitem(climate_history.FETCHERS, "open-meteo", fake)
    cache = tmp_path / "climat.csv"
    df = climate_history.download_climate(31.88, -4.15, "2019-06-01", "2021-03-31", cache_file=str(cache))
    assert calls == [("2019-06-01", "2019-12-31"), ("2020-01-01", "2020-12-31"), ("2021-01-01", "2021-03-31")]
    assert len(df) == pd.Timestamp("2021-03-31").dayofyear + 366 + 214
    climate_history.download_climate(31.88, -4.15, "2019-06-01", "2021-03-31", cache_file=str(cache))
    assert len(calls) == 3          # relu depuis le cache


def test_annual_rain_normal_uses_complete_years():
    clim = synthetic_climate("2019-01-01", "2020-06-30")
    assert climate_history.annual_rain_normal(clim) == pytest.approx(
        clim[clim.date.dt.year == 2019].precipitation_mm.sum())


# --- Bilan hydrique ---------------------------------------------------------------
def test_water_balance_stress_without_irrigation_and_none_when_irrigated():
    farm = make_farm(planting_year=2010)
    clim = synthetic_climate("2020-01-01", "2020-09-30")
    dry = run_water_balance(clim, None, farm)
    assert dry["ks"].iloc[-1] < 0.6
    assert (dry["depletion_mm"] <= farm.total_available_water_mm).all()

    irr = pd.DataFrame({"date": clim["date"], "irrigation_mm": clim["et0_mm"] * 1.2})
    wet = run_water_balance(clim, irr, farm)
    assert wet["ks"].min() == 1.0
    assert label_at(wet, pd.Timestamp("2020-08-01")) == (0, 1.0)
    assert label_at(dry, pd.Timestamp("2020-08-01"))[0] == 2


def test_ks_to_class_thresholds():
    assert [ks_to_class(k) for k in (1.0, 0.85, 0.7, 0.59)] == [0, 0, 1, 2]


def test_labelled_dates_skip_months_missing_from_register():
    clim = synthetic_climate("2018-12-01", "2024-12-31")
    farm = make_farm()
    irr_dates = pd.date_range("2018-12-01", "2024-03-31")
    irr = pd.DataFrame({"date": irr_dates, "irrigation_mm": 2.0})
    balance = run_water_balance(clim, irr, farm)
    dates = farm_dataset.labelled_dates(balance, irr, every_days=10)
    assert dates[0] >= pd.Timestamp("2019-01-30")
    assert max(dates) <= pd.Timestamp("2024-03-31")


# --- Chaîne complète (Earth Engine simulé) --------------------------------------------
def test_cli_end_to_end_with_mocked_earth_engine(tmp_path, monkeypatch, capsys):
    import extract_data

    monkeypatch.chdir(tmp_path)
    farm_dataset.main(["init", "--name", "Bloc 4", "--lat", "31.887705", "--lon", "-4.155879",
                       "--crop", "amandier", "--spacing", "7x5", "--area-ha", "102",
                       "--planting-year", "2016", "--soil", "sableux"])
    farm_file = "farms/bloc-4.json"
    (tmp_path / "data/bloc-4").mkdir(parents=True)
    synthetic_climate().to_csv("data/bloc-4/climat.csv", index=False)

    # Irrigation : correcte sauf en été 2021 et 2023 (stress)
    days = pd.date_range("2018-01-01", "2024-12-31")
    mm = np.where(((days.year == 2021) | (days.year == 2023)) & days.month.isin([6, 7, 8]), 0.3, 6.0)
    pd.DataFrame({"date": days, "irrigation_m3": mm * 1020}).to_csv(tmp_path / "irr.csv", index=False)
    farm_dataset.main(["irrigation", farm_file, str(tmp_path / "irr.csv")])
    farm_dataset.main(["balance", farm_file, "--every-days", "15"])
    labels = pd.read_csv("data/bloc-4/etiquettes.csv")
    assert set(labels["stress_class"]) >= {0, 2}

    class FakeGeometry:
        def centroid(self, maxError=1):
            return self

    class FakePipeline:
        def __init__(self):
            self.sentinel = type("S", (), {"create_geometry": staticmethod(lambda c: FakeGeometry())})()

        def extract_sentinel(self, geometry, end_dt, lookback):
            stats = {k: {"mean": 0.3, "min": 0.1, "max": 0.5, "stdDev": 0.05} for k in ("NDVI", "NDWI", "MSI", "SAVI", "EVI")}
            return stats, 3, 0.9, 30

    monkeypatch.setattr(extract_data, "DataPipeline", FakePipeline)
    monkeypatch.setattr(extract_data, "get_site_features",
                        lambda g: {"elevation_m": 1050.0, "precip_annual_normal_mm": 110.0})
    farm_dataset.main(["build", farm_file, "--every-days", "15"])
    ds = pd.read_csv("data/bloc-4/dataset.csv")
    assert not ds[FEATURE_COLUMNS].isna().any().any()
    assert ds["campagne"].nunique() >= 5
    assert (ds["stress_class"] == labels.set_index("date").loc[ds["date"], "stress_class"].values).all()
