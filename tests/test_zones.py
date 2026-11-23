import json
from datetime import date

import pytest

try:
    from shapely.geometry import shape
except ImportError:  # environnement sans shapely
    pytest.skip("shapely requis", allow_module_level=True)

from imagery import build_zones, navigation_url, zones_geojson, zones_kml  # noqa: E402


def square(lon, lat, d=0.0005):
    return {"type": "Polygon", "coordinates": [[[lon, lat], [lon + d, lat], [lon + d, lat + d],
                                                [lon, lat + d], [lon, lat]]]}


def feature(cat, count, deltas, lon=-4.155, lat=31.887):
    props = {"cat": cat, "count": count}
    for k, v in deltas.items():
        props[f"D_{k}"] = v
        props[f"A_{k}"] = 0.4
        props[f"B_{k}"] = 0.4 + v
    return {"type": "Feature", "geometry": square(lon, lat), "properties": props}


WATER = {"NDVI": -0.02, "NDMI": -0.12, "NDRE": -0.01, "PSRI": 0.0}
HEALTH = {"NDVI": -0.03, "NDMI": 0.0, "NDRE": -0.09, "PSRI": 0.06}
VIGOR = {"NDVI": -0.12, "NDMI": 0.0, "NDRE": 0.0, "PSRI": 0.0}


def test_zones_ranked_and_explained():
    feats = [feature(4, 40, VIGOR), feature(1, 12, WATER, lon=-4.150), feature(2, 9, HEALTH, lon=-4.152)]
    zones = build_zones(feats, date(2026, 6, 1), date(2026, 7, 1), crop="Olivier")
    assert [z["id"] for z in zones] == [1, 2, 3]
    # 12 pixels de perte d'eau (poids 3) passent avant 40 pixels de vigueur seule ? 3*1200=3600 < 1*4000
    assert zones[0]["category"] == "vigor" and zones[1]["category"] == "water"
    water = zones[1]
    assert water["changed"] == ["NDMI"]
    assert water["hypotheses"][0]["title"] == "Stress hydrique"
    assert any("goutteurs" in c for c in water["checks"])
    health = zones[2]
    assert {"NDRE", "PSRI"} <= set(health["changed"])
    assert "Problème sanitaire : maladie ou ravageur" in [h["title"] for h in health["hypotheses"]]
    # le point d'arrivée est dans la zone
    for z in zones:
        assert shape(z["geometry"]).buffer(1e-9).contains(shape({"type": "Point", "coordinates": [z["lon"], z["lat"]]}))
        assert z["nav_url"] == navigation_url(z["lat"], z["lon"])


def test_zone_texts_follow_language():
    zones = build_zones([feature(1, 12, WATER)], date(2026, 6, 1), date(2026, 7, 1), lang="ar")
    assert zones[0]["hypotheses"][0]["title"] == "إجهاد مائي"


def test_invalid_features_are_skipped():
    bad = feature(1, 12, WATER)
    bad["properties"]["D_NDMI"] = None
    assert build_zones([bad, feature(9, 10, WATER)], date(2026, 6, 1), date(2026, 7, 1)) == []


def test_exports():
    zones = build_zones([feature(3, 20, {**WATER, "NDRE": -0.08})], date(2026, 6, 1), date(2026, 7, 1))
    gj = zones_geojson(zones)
    assert gj["features"][0]["properties"]["zone"] == 1
    json.dumps(gj)
    kml = zones_kml(zones, "Test & co")
    assert kml.startswith("<?xml") and "<Point>" in kml and "Test &amp; co" in kml
    assert "maps/dir/?api=1&destination=" in navigation_url(31.88, -4.15)
