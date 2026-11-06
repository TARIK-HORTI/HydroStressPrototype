import pytest

from extract_data import polygon_area_km2, validate_geometry
from region import ZONES, is_in_region, validate_in_region, zone_for_point


def square(lon, lat, half_deg=0.005):
    return [
        [lon - half_deg, lat - half_deg],
        [lon + half_deg, lat - half_deg],
        [lon + half_deg, lat + half_deg],
        [lon - half_deg, lat + half_deg],
        [lon - half_deg, lat - half_deg],
    ]


def test_all_reference_places_inside_morocco():
    for zone in ZONES.values():
        for lat, lon in zone["places"].values():
            assert is_in_region(lon, lat)


def test_zone_detection():
    assert zone_for_point(31.63, -7.98)[0] == "haouz"
    assert zone_for_point(31.43, -4.23)[0] == "errachidia"
    assert zone_for_point(30.40, -9.30)[0] == "souss"
    assert zone_for_point(34.30, -6.20)[0] == "gharb"
    zone_id, place, km = zone_for_point(30.33, -5.84)
    assert zone_id == "draa" and place == "Zagora" and km < 1


def test_valid_parcel_in_errachidia():
    poly = validate_geometry(square(-4.424, 31.931))
    # ~1.1 km x ~0.95 km à 31.9°N
    assert 0.9 < polygon_area_km2(poly) < 1.2


def test_unclosed_ring_is_closed():
    coords = square(-4.233, 31.433)[:-1]
    validate_geometry(coords)


def test_parcels_across_morocco_accepted():
    for lon, lat in [(-7.98, 31.63), (-6.58, 34.26), (-9.37, 30.21), (-2.32, 34.92)]:
        validate_geometry(square(lon, lat))


def test_parcel_outside_morocco_rejected():
    seville = square(-5.98, 37.39)
    with pytest.raises(ValueError, match="hors zone"):
        validate_geometry(seville)
    with pytest.raises(ValueError):
        validate_in_region(seville)


def test_region_check_can_be_disabled():
    validate_geometry(square(-5.98, 37.39), require_region=False)


def test_parcel_too_large_rejected():
    with pytest.raises(ValueError, match="trop grande"):
        validate_geometry(square(-4.424, 31.931, half_deg=0.05))


def test_too_few_vertices_rejected():
    with pytest.raises(ValueError, match="minimum 3"):
        validate_geometry([[-4.42, 31.93], [-4.41, 31.93]])


def test_self_intersecting_rejected():
    bowtie = [[-4.43, 31.93], [-4.42, 31.94], [-4.42, 31.93], [-4.43, 31.94], [-4.43, 31.93]]
    with pytest.raises(ValueError, match="auto-intersecte"):
        validate_geometry(bowtie)
