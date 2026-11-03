import pytest

from extract_data import polygon_area_km2, validate_geometry
from region import OASES, is_in_region, validate_in_region


def square(lon, lat, half_deg=0.005):
    return [
        [lon - half_deg, lat - half_deg],
        [lon + half_deg, lat - half_deg],
        [lon + half_deg, lat + half_deg],
        [lon - half_deg, lat + half_deg],
        [lon - half_deg, lat - half_deg],
    ]


def test_all_oases_inside_region():
    for lat, lon in OASES.values():
        assert is_in_region(lon, lat)


def test_valid_parcel_in_errachidia():
    poly = validate_geometry(square(-4.424, 31.931))
    # ~1.1 km x ~0.95 km à 31.9°N
    assert 0.9 < polygon_area_km2(poly) < 1.2


def test_unclosed_ring_is_closed():
    coords = square(-4.233, 31.433)[:-1]
    validate_geometry(coords)


def test_parcel_outside_region_rejected():
    marrakech = square(-7.98, 31.63)
    with pytest.raises(ValueError, match="hors zone"):
        validate_geometry(marrakech)
    with pytest.raises(ValueError):
        validate_in_region(marrakech)


def test_region_check_can_be_disabled():
    validate_geometry(square(-7.98, 31.63), require_region=False)


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
