"""
imagery_ui.py
=============
Section Streamlit « Suivi satellite de la parcelle » : cartes Sentinel-2 du
stress hydrique, de l'état sanitaire et du développement de la végétation,
comparaison image contre image entre deux dates, carte des différences et
courbe d'évolution de la parcelle.
"""

from __future__ import annotations

import json
import logging
from datetime import date
from typing import List

import folium
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from shapely.geometry import Polygon
from streamlit_folium import st_folium

from imagery import (
    LAYERS,
    SERIES_INDICES,
    THEMES,
    default_period,
    diff_layer,
    layer_maps,
    layers_for_theme,
    legend_html,
    to_date,
    trend,
)

logger = logging.getLogger(__name__)

SERIES_COLORS = {"NDVI": "#4ADE80", "NDMI": "#38BDF8", "NDRE": "#FACC15", "PSRI": "#F97316", "MSI": "#F87171"}
LABEL_STATUS = {"Amélioration": "better", "Dégradation": "worse", "Stable": "stable"}
TREND_COLORS = {"better": "#22C55E", "worse": "#EF4444", "stable": "#94A3B8", "unknown": "#94A3B8"}


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def _series(coords_json: str, start: date, end: date) -> pd.DataFrame:
    from extract_data import initialize_earth_engine
    from imagery import ee_image_series
    initialize_earth_engine()
    return ee_image_series(json.loads(coords_json), start, end)


@st.cache_data(ttl=2 * 3600, show_spinner=False)  # les URL de tuiles Earth Engine expirent
def _maps(coords_json: str, layer: str, day_a: date, day_b: date) -> dict:
    from extract_data import initialize_earth_engine
    initialize_earth_engine()
    return layer_maps(json.loads(coords_json), layer, day_a, day_b)


def _map(coordinates: List[List[float]], tile_url: str, name: str, key: str, height: int = 380):
    poly = Polygon(coordinates)
    minx, miny, maxx, maxy = poly.bounds
    m = folium.Map(location=[poly.centroid.y, poly.centroid.x], zoom_start=15, tiles=None,
                   control_scale=True, zoom_control=True)
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Esri World Imagery", name="Fond satellite",
    ).add_to(m)
    folium.TileLayer(tiles=tile_url, attr="Copernicus Sentinel-2 · Google Earth Engine", name=name,
                     overlay=True, max_zoom=20, max_native_zoom=18).add_to(m)
    folium.GeoJson(
        {"type": "Polygon", "coordinates": [coordinates]},
        style_function=lambda _: {"color": "#F8FAFC", "weight": 2, "fillOpacity": 0},
    ).add_to(m)
    m.fit_bounds([[miny, minx], [maxy, maxx]], padding=(20, 20))
    st_folium(m, height=height, use_container_width=True, returned_objects=[], key=key)


def _plot_series(df: pd.DataFrame, indices: List[str], day_a: date, day_b: date) -> go.Figure:
    fig = go.Figure()
    for idx in indices:
        fig.add_trace(go.Scatter(x=df["date"], y=df[idx], name=idx, mode="lines+markers",
                                 line=dict(color=SERIES_COLORS[idx], width=2), marker=dict(size=5)))
    for day, label in ((day_a, "A"), (day_b, "B")):
        fig.add_vline(x=pd.Timestamp(day), line=dict(color="#E2E8F0", dash="dot", width=1))
        fig.add_annotation(x=pd.Timestamp(day), y=1.02, yref="paper", text=label, showarrow=False,
                           font=dict(color="#E2E8F0"))
    fig.update_layout(height=300, margin=dict(l=10, r=10, t=30, b=10), paper_bgcolor="rgba(0,0,0,0)",
                      plot_bgcolor="rgba(0,0,0,0)", font=dict(color="#CBD5E1"), hovermode="x unified",
                      legend=dict(orientation="h", y=1.15))
    fig.update_xaxes(gridcolor="#1E2A40")
    fig.update_yaxes(gridcolor="#1E2A40")
    return fig


def _summary_table(df: pd.DataFrame, day_a: date, day_b: date) -> pd.DataFrame:
    row_a = df[df["date"] == pd.Timestamp(day_a)].iloc[0]
    row_b = df[df["date"] == pd.Timestamp(day_b)].iloc[0]
    rows = []
    for idx in SERIES_INDICES:
        t = trend(idx, row_a[idx], row_b[idx])
        rows.append({
            "Indice": LAYERS[idx]["label"],
            f"A · {day_a:%d/%m/%Y}": None if pd.isna(row_a[idx]) else round(float(row_a[idx]), 3),
            f"B · {day_b:%d/%m/%Y}": None if pd.isna(row_b[idx]) else round(float(row_b[idx]), 3),
            "Écart B − A": None if t["delta"] is None else round(t["delta"], 3),
            "Évolution": t["label"],
        })
    return pd.DataFrame(rows)


def render_imagery(coordinates: List[List[float]], demo: bool = False):
    """Section complète ; n'appelle Earth Engine qu'après le clic sur « Chercher les images »."""
    st.markdown("<div class='hs-section'>Suivi satellite de la parcelle · cartes Sentinel-2</div>",
                unsafe_allow_html=True)
    st.caption(
        "Cartes du stress hydrique, de l'état sanitaire et du développement de la végétation, pixel par pixel "
        "(10 à 20 m). Choisissez deux dates pour comparer la parcelle image contre image et voir où elle évolue. "
        "Une nouvelle image Sentinel-2 environ tous les 5 jours, gratuite."
    )

    coords_json = json.dumps(coordinates)
    start_default, end_default = default_period()
    c1, c2, c3 = st.columns([1, 1, 1.2])
    start = c1.date_input("Images depuis", value=start_default, min_value=date(2018, 1, 1),
                          max_value=end_default, key="img_start")
    end = c2.date_input("Jusqu'au", value=end_default, min_value=date(2018, 1, 2),
                        max_value=end_default, key="img_end")
    c3.write("")
    search = c3.button("🛰️ Chercher les images sans nuages", width="stretch", key="img_search")

    state_key = json.dumps([coords_json, str(start), str(end)])
    if st.session_state.get("img_key") != state_key:
        st.session_state.img_key = state_key
        st.session_state.img_series = None
        st.session_state.img_error = None

    if search:
        if demo:
            st.session_state.img_error = "Les cartes satellite demandent l'accès Earth Engine (pas de démonstration)."
        elif (end - start).days < 10:
            st.session_state.img_error = "Choisissez une période d'au moins 10 jours."
        else:
            with st.spinner("Recherche des images Sentinel-2 et calcul des indices sur la parcelle…"):
                try:
                    st.session_state.img_series = _series(coords_json, start, end)
                    st.session_state.img_error = None
                except Exception as e:  # Earth Engine : authentification, quota, réseau
                    logger.exception("Imagerie Sentinel-2")
                    st.session_state.img_error = f"Images indisponibles : {e}"

    if st.session_state.get("img_error"):
        st.error(st.session_state.img_error)
        return
    df = st.session_state.get("img_series")
    if df is None:
        st.info("Cliquez sur « Chercher les images sans nuages » pour charger les cartes de la parcelle.")
        return
    if len(df) < 1:
        st.warning("Aucune image où la parcelle est dégagée à plus de 80 % sur cette période : élargissez-la.")
        return

    dates = [to_date(d) for d in df["date"]]
    st.success(f"{len(dates)} image(s) sans nuages sur la parcelle entre le {dates[0]:%d/%m/%Y} "
               f"et le {dates[-1]:%d/%m/%Y}.")

    # --- Choix du volet, de la couche et des deux dates -------------------------------------------
    p1, p2 = st.columns([1, 1.3])
    theme = p1.radio("Volet", list(THEMES), format_func=THEMES.get, key="img_theme")
    options = layers_for_theme(theme)
    layer = p2.radio("Carte", options, format_func=lambda k: LAYERS[k]["label"], key=f"img_layer_{theme}")
    st.caption(LAYERS[layer]["description"])

    d1, d2 = st.columns(2)
    fmt = (lambda d: d.strftime("%d/%m/%Y"))
    day_a = d1.selectbox("Date A (avant)", dates, index=0, format_func=fmt, key="img_day_a")
    day_b = d2.selectbox("Date B (après)", dates, index=len(dates) - 1, format_func=fmt, key="img_day_b")

    try:
        with st.spinner("Préparation des cartes…"):
            maps = _maps(coords_json, layer, day_a, day_b)
    except ValueError as e:
        st.warning(str(e))
        return
    except Exception as e:
        logger.exception("Cartes Sentinel-2")
        st.error(f"Cartes indisponibles : {e}")
        return

    spec = LAYERS[layer]
    if spec["palette"]:
        st.markdown(legend_html(spec["min"], spec["max"], spec["palette"], spec["low"], spec["high"],
                                spec["label"]), unsafe_allow_html=True)
    m1, m2 = st.columns(2)
    with m1:
        st.markdown(f"**A · {fmt(day_a)}**")
        _map(coordinates, maps["a"], f"{layer} A", key=f"img_map_a_{layer}_{day_a}")
    with m2:
        st.markdown(f"**B · {fmt(day_b)}**")
        _map(coordinates, maps["b"], f"{layer} B", key=f"img_map_b_{layer}_{day_b}")

    c_diff, c_info = st.columns([1, 1])
    with c_diff:
        if maps["diff"]:
            d = diff_layer(layer)
            st.markdown("**Changement B − A** · où la parcelle a évolué")
            st.markdown(legend_html(d["min"], d["max"], d["palette"], d["low"], d["high"]),
                        unsafe_allow_html=True)
            _map(coordinates, maps["diff"], f"{layer} B-A", key=f"img_map_d_{layer}_{day_a}_{day_b}", height=340)
        else:
            st.caption("Pas de carte de différence pour cette couche.")
    with c_info:
        if day_a != day_b:
            st.markdown("**Moyennes de la parcelle**")
            table = _summary_table(df, day_a, day_b)
            st.dataframe(
                table.style.map(lambda v: f"color:{TREND_COLORS[LABEL_STATUS.get(v, 'unknown')]}",
                                subset=["Évolution"]),
                hide_index=True, width="stretch",
            )
        st.link_button("⬇️ Carte de la date B (GeoTIFF, pour QGIS)", maps["geotiff_b"])
        st.caption(
            "Les indices montrent un changement de vigueur, d'eau ou de chlorophylle, pas sa cause : "
            "une baisse localisée se vérifie au champ (irrigation, maladie, ravageur, carence)."
        )

    st.markdown("**Évolution de la parcelle sur la période** (moyenne à chaque image)")
    chosen = st.multiselect("Indices", SERIES_INDICES, default=["NDVI", "NDMI", "NDRE"], key="img_series_idx")
    if chosen:
        st.plotly_chart(_plot_series(df, chosen, day_a, day_b), width="stretch",
                        config={"displayModeBar": False})
