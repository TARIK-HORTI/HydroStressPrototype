import pandas as pd
import pytest

from stations import compare_with_grids, nearest_stations, parse_gsod, parse_station_list

ISD = '''"USAF","WBAN","STATION NAME","CTRY","STATE","ICAO","LAT","LON","ELEV(M)","BEGIN","END"
"601550","99999","CASABLANCA","MO","","GMMC","+33.567","-007.667","+0057.0","19730101","20251231"
"602300","99999","MARRAKECH","MO","","GMMX","+31.607","-008.036","+0466.0","19730101","20251231"
"601150","99999","OLD STATION","MO","","","+34.000","-005.000","+0400.0","19730101","20051231"
"082840","99999","SEVILLA","SP","","LEZL","+37.417","-005.900","+0034.0","19730101","20251231"
'''

GSOD = '''"STATION","DATE","LATITUDE","LONGITUDE","ELEVATION","NAME","TEMP","TEMP_ATTRIBUTES","DEWP","DEWP_ATTRIBUTES","SLP","SLP_ATTRIBUTES","STP","STP_ATTRIBUTES","VISIB","VISIB_ATTRIBUTES","WDSP","WDSP_ATTRIBUTES","MXSPD","GUST","MAX","MAX_ATTRIBUTES","MIN","MIN_ATTRIBUTES","PRCP","PRCP_ATTRIBUTES","SNDP","FRSHTT"
"60230099999","2024-07-01","31.607","-8.036","466.0","MARRAKECH, MO","  86.0","24","  50.0","24","1012.0","8","958.0","8","  6.2","24","  5.0","24","  9.9","999.9"," 104.0","*","  68.0","*","  0.00","G","999.9","000000"
"60230099999","2024-07-02","31.607","-8.036","466.0","MARRAKECH, MO","  88.0","24","9999.9","0","1012.0","8","958.0","8","  6.2","24","  5.0","24","  9.9","999.9"," 106.0","*","  70.0","*"," 99.99"," ","999.9","000000"
"60230099999","2024-07-03","31.607","-8.036","466.0","MARRAKECH, MO","  80.6","24","  48.0","24","1012.0","8","958.0","8","  6.2","24","  5.0","24","  9.9","999.9","  95.0","*","  66.2","*","  0.20","G","999.9","000000"
'''


def test_station_list_keeps_active_moroccan_stations():
    st = parse_station_list(ISD)
    assert list(st["station"]) == ["60155099999", "60230099999"]
    assert st.loc[1, "name"] == "Marrakech"


def test_nearest_station():
    st = parse_station_list(ISD)
    near = nearest_stations(st, 31.63, -7.98, n=2)
    assert near.loc[0, "name"] == "Marrakech"
    assert near.loc[0, "distance_km"] < 10
    assert nearest_stations(st, 29.0, -10.5, max_km=50).empty


def test_parse_gsod_units_and_missing_values():
    df = parse_gsod(GSOD)
    assert df.loc[0, "temperature_c"] == pytest.approx(30.0)
    assert df.loc[0, "temperature_max_c"] == pytest.approx(40.0)
    assert pd.isna(df.loc[1, "dewpoint_c"])
    assert pd.isna(df.loc[1, "precipitation_mm"])
    assert df.loc[2, "precipitation_mm"] == pytest.approx(5.08)


def test_compare_with_grids():
    station = parse_gsod(GSOD)
    era5 = pd.DataFrame({"date": station["date"], "temperature_c": [31.0, 32.0, 28.0],
                         "temperature_max_c": [41.0, 42.0, 36.0]})
    chirps = pd.DataFrame({"date": station["date"], "precipitation_mm": [0.0, 1.0, 4.0]})
    m = compare_with_grids(station, chirps, era5)
    assert m["temperature_mean"]["days"] == 3
    assert m["temperature_mean"]["bias"] > 0
    assert m["precipitation"]["days"] == 2
    assert m["precipitation"]["total_station_mm"] == pytest.approx(5.1)
