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

from i18n import get_lang, t
from imagery import (
    LAYERS,
    build_zones,
    zones_geojson,
    zones_kml,
    SERIES_INDICES,
    THEMES,
    default_period,
    diff_labels,
    diff_layer,
    glossary,
    interpret_change,
    layer_maps,
    layer_text,
    layers_for_theme,
    legend_html,
    theme_label,
    to_date,
    trend,
    trend_label,
)
from imagery_text import INTERP


def interpret_disclaimer(lang: str) -> str:
    return INTERP["disclaimer"].get(lang) or INTERP["disclaimer"]["fr"]

logger = logging.getLogger(__name__)

SERIES_COLORS = {"NDVI": "#4ADE80", "NDMI": "#38BDF8", "NDRE": "#FACC15", "PSRI": "#F97316", "MSI": "#F87171"}
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


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def _change(coords_json: str, day_a: date, day_b: date) -> dict:
    from extract_data import initialize_earth_engine
    from imagery import ee_change_fractions
    initialize_earth_engine()
    return ee_change_fractions(json.loads(coords_json), day_a, day_b)


LIKELIHOOD_COLORS = {"probable": "#F59E0B", "possible": "#94A3B8"}
STATUS_STYLE = {
    "better": ("#22C55E", "✅"), "stable": ("#38BDF8", "➖"), "worse": ("#EF4444", "⚠️"), "unknown": ("#94A3B8", "❔"),
}


def render_glossary(selected: str | None = None):
    """Guide des indices : ce que chacun mesure, comment le lire et à quoi il sert."""
    lang = get_lang()
    gl = glossary(lang)
    st.markdown(t("gl_title"))
    st.markdown(t("gl_intro"))
    keys = list(gl)
    if selected in gl:  # l'indice de la carte choisie en premier, ouvert
        keys.remove(selected)
        keys.insert(0, selected)
    for k in keys:
        g = gl[k]
        with st.expander(g["name"], expanded=(k == selected)):
            st.markdown(
                f"**{t('gl_meaning')}** {g['meaning']}\n\n"
                f"**{t('gl_reading')}** {g['reading']}\n\n"
                f"**{t('gl_use')}** {g['use']}\n\n"
                f"<span style='color:#94A3B8;font-size:.85rem'>{t('gl_formula')} : {g['formula']}</span>",
                unsafe_allow_html=True,
            )


def render_interpretation(result: dict):
    color, icon = STATUS_STYLE.get(result["status"], STATUS_STYLE["unknown"])
    st.markdown(t("in_title"))
    st.markdown(
        f"<div class='hs-status' style='border-left:8px solid {color};padding:14px 18px'>"
        f"<div style='font-size:1.05rem;color:#F1F5F9;font-weight:650'>{icon} {result['headline']}</div></div>",
        unsafe_allow_html=True,
    )
    c_obs, c_hyp = st.columns([1, 1.3], gap="large")
    with c_obs:
        st.markdown(t("in_obs"))
        for o in result["observations"]:
            st.markdown(f"- {o}")
        for n in result["notes"]:
            st.caption(f"ℹ️ {n}")
    with c_hyp:
        st.markdown(t("in_causes"))
        for h in result["hypotheses"]:
            hc = LIKELIHOOD_COLORS.get(h["likelihood"], LIKELIHOOD_COLORS["possible"])
            hl = t(f"lk_{h['likelihood']}")
            st.markdown(
                f"<div style='margin-bottom:8px'><span class='hs-chip' style='border-color:{hc};color:{hc};"
                f"background:transparent'>{hl}</span> <b>{h['title']}</b><br>"
                f"<span style='color:#CBD5E1;font-size:.92rem'>{h['detail']}</span></div>",
                unsafe_allow_html=True,
            )
    if result["checks"]:
        st.markdown(t("in_checks"))
        for c in result["checks"]:
            st.markdown(f"- {c}")
    st.markdown(f"<div class='hs-banner'>🧑‍🌾 <b>{t('in_field_last')}</b> {result['disclaimer']}</div>",
                unsafe_allow_html=True)


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def _zones(coords_json: str, day_a: date, day_b: date, relative: bool) -> list:
    from extract_data import initialize_earth_engine
    from imagery import ee_change_zones
    initialize_earth_engine()
    return ee_change_zones(json.loads(coords_json), day_a, day_b, relative=relative)


def _area(m2: float) -> str:
    return t("zn_area_ha", v=f"{m2 / 10000:.2f}") if m2 >= 5000 else t("zn_area_m2", v=f"{m2:.0f}")


def _zones_map(coordinates: List[List[float]], zones: list, key: str):
    poly = Polygon(coordinates)
    minx, miny, maxx, maxy = poly.bounds
    m = folium.Map(location=[poly.centroid.y, poly.centroid.x], zoom_start=16, tiles=None, control_scale=True)
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Esri World Imagery", name="Satellite", max_zoom=20, max_native_zoom=18,
    ).add_to(m)
    folium.GeoJson({"type": "Polygon", "coordinates": [coordinates]},
                   style_function=lambda _: {"color": "#F8FAFC", "weight": 2, "fillOpacity": 0}).add_to(m)
    for z in zones:
        label = t(f"zn_cat_{z['category']}")
        folium.GeoJson(
            z["geometry"],
            style_function=(lambda _, c=z["color"]: {"color": c, "weight": 2, "fillColor": c, "fillOpacity": .45}),
            tooltip=f"Zone {z['id']} · {label}",
        ).add_to(m)
        folium.Marker(
            [z["lat"], z["lon"]],
            icon=folium.DivIcon(
                icon_size=(26, 26), icon_anchor=(13, 13),
                html=(f"<div style='width:26px;height:26px;border-radius:13px;background:{z['color']};"
                      "color:#fff;font-weight:700;font-size:13px;display:flex;align-items:center;"
                      f"justify-content:center;border:2px solid #fff'>{z['id']}</div>"),
            ),
            popup=folium.Popup(f"<b>Zone {z['id']}</b><br>{label}<br>{_area(z['area_m2'])}<br>"
                               f"<a href='{z['nav_url']}' target='_blank'>{t('zn_go')}</a>", max_width=240),
        ).add_to(m)
    m.fit_bounds([[miny, minx], [maxy, maxx]], padding=(20, 20))
    st_folium(m, height=460, use_container_width=True, returned_objects=[], key=key)


def render_zones(coordinates: List[List[float]], coords_json: str, day_a: date, day_b: date,
                 crop: str | None, lang: str):
    """Orientation : zones qui ont changé, dessinées, classées, avec causes possibles et itinéraire."""
    st.markdown(t("zn_title"))
    st.caption(t("zn_intro"))
    c1, c2 = st.columns([1.4, 1])
    relative = c1.toggle(t("zn_relative"), value=True, help=t("zn_relative_help"), key="zn_relative")
    run = c2.button(t("zn_detect"), type="primary", width="stretch", key="zn_detect")
    key = json.dumps([coords_json, str(day_a), str(day_b), relative])
    if run:
        with st.spinner(t("zn_detecting")):
            try:
                st.session_state.zn_result = {"key": key, "features": _zones(coords_json, day_a, day_b, relative),
                                              "error": None}
            except Exception as e:
                logger.exception("Zones de changement")
                st.session_state.zn_result = {"key": key, "features": None, "error": str(e)}
    res = st.session_state.get("zn_result")
    if not res or res["key"] != key:
        return
    if res["error"]:
        st.error(t("zn_error", e=res["error"]))
        return
    zones = build_zones(res["features"], day_a, day_b, crop=crop, lang=lang)
    if not zones:
        st.success(t("zn_none"))
        return
    st.warning(t("zn_found", n=len(zones)))
    legend = " ".join(
        f"<span class='hs-chip' style='border-color:{c};color:{c};background:transparent'>"
        f"■ {t('zn_cat_' + k)}</span>"
        for k, c in (("decline", "#DC2626"), ("water", "#3B82F6"), ("health", "#F59E0B"), ("vigor", "#A855F7"))
    )
    st.markdown(legend, unsafe_allow_html=True)
    _zones_map(coordinates, zones, key=f"zn_map_{abs(hash(key))}")

    delta_label = t("zn_delta_rel") if relative else t("zn_delta")
    for z in zones:
        head = t("zn_card", id=z["id"], cat=t(f"zn_cat_{z['category']}"), area=_area(z["area_m2"]),
                 lat=f"{z['lat']:.5f}", lon=f"{z['lon']:.5f}")
        with st.expander(head, expanded=z["id"] <= 2):
            cz1, cz2 = st.columns([1, 1.4], gap="large")
            with cz1:
                st.markdown(t("zn_changed"))
                for b in ["NDVI", "NDMI", "NDRE", "PSRI"]:
                    va, vb, d = z["a"].get(b), z["b"].get(b), z["delta"][b]
                    mark = "🔻 " if b in z["changed"] else ""
                    vals = f"{va:.2f} → {vb:.2f}" if va is not None and vb is not None else "—"
                    st.markdown(f"- {mark}**{b}** : {vals} ({delta_label} {d:+.2f})")
                st.link_button(t("zn_go"), z["nav_url"])
            with cz2:
                st.markdown(t("in_causes"))
                for h in z["hypotheses"]:
                    hc = LIKELIHOOD_COLORS.get(h["likelihood"], LIKELIHOOD_COLORS["possible"])
                    st.markdown(
                        f"<div style='margin-bottom:6px'><span class='hs-chip' style='border-color:{hc};"
                        f"color:{hc};background:transparent'>{t('lk_' + h['likelihood'])}</span> "
                        f"<b>{h['title']}</b><br><span style='color:#CBD5E1;font-size:.9rem'>{h['detail']}</span></div>",
                        unsafe_allow_html=True,
                    )
                if z["checks"]:
                    st.markdown(t("in_checks"))
                    for c in z["checks"]:
                        st.markdown(f"- {c}")

    d1, d2 = st.columns(2)
    d1.download_button(t("zn_geojson"), json.dumps(zones_geojson(zones), ensure_ascii=False),
                       file_name=f"zones_{day_a}_{day_b}.geojson", mime="application/geo+json", width="stretch")
    d2.download_button(t("zn_kml"), zones_kml(zones, f"HydroStress {day_a} - {day_b}"),
                       file_name=f"zones_{day_a}_{day_b}.kml", mime="application/vnd.google-earth.kml+xml",
                       width="stretch")
    st.markdown(f"<div class='hs-banner'>🧑‍🌾 <b>{t('in_field_last')}</b> "
                f"{interpret_disclaimer(lang)}</div>", unsafe_allow_html=True)


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


def _summary_table(df: pd.DataFrame, day_a: date, day_b: date, lang: str) -> pd.DataFrame:
    row_a = df[df["date"] == pd.Timestamp(day_a)].iloc[0]
    row_b = df[df["date"] == pd.Timestamp(day_b)].iloc[0]
    rows = []
    for idx in SERIES_INDICES:
        tr = trend(idx, row_a[idx], row_b[idx])
        rows.append({
            t("img_col_index"): layer_text(idx, "label", lang),
            f"A · {day_a:%d/%m/%Y}": None if pd.isna(row_a[idx]) else round(float(row_a[idx]), 3),
            f"B · {day_b:%d/%m/%Y}": None if pd.isna(row_b[idx]) else round(float(row_b[idx]), 3),
            t("img_col_delta"): None if tr["delta"] is None else round(tr["delta"], 3),
            t("img_col_trend"): trend_label(tr["status"], lang),
            "_status": tr["status"],
        })
    return pd.DataFrame(rows)


def render_imagery(coordinates: List[List[float]], crop: str | None = None, demo: bool = False):
    """Section complète ; n'appelle Earth Engine qu'après le clic sur « Chercher les images »."""
    lang = get_lang()
    st.markdown(f"<div class='hs-section'>{t('img_title')}</div>", unsafe_allow_html=True)
    st.caption(t("img_intro"))
    glossary_slot = st.container()

    coords_json = json.dumps(coordinates)
    start_default, end_default = default_period()
    c1, c2, c3 = st.columns([1, 1, 1.2])
    start = c1.date_input(t("img_since"), value=start_default, min_value=date(2018, 1, 1),
                          max_value=end_default, key="img_start")
    end = c2.date_input(t("img_until"), value=end_default, min_value=date(2018, 1, 2),
                        max_value=end_default, key="img_end")
    c3.write("")
    search = c3.button(t("img_search"), width="stretch", key="img_search")

    state_key = json.dumps([coords_json, str(start), str(end)])
    if st.session_state.get("img_key") != state_key:
        st.session_state.img_key = state_key
        st.session_state.img_series = None
        st.session_state.img_error = None

    if search:
        if demo:
            st.session_state.img_error = t("img_demo")
        elif (end - start).days < 10:
            st.session_state.img_error = t("img_period_short")
        else:
            with st.spinner(t("img_searching")):
                try:
                    st.session_state.img_series = _series(coords_json, start, end)
                    st.session_state.img_error = None
                except Exception as e:  # Earth Engine : authentification, quota, réseau
                    logger.exception("Imagerie Sentinel-2")
                    st.session_state.img_error = t("img_unavailable", e=e)

    with glossary_slot:  # l'indice de la carte choisie s'ouvre en premier (choix fait plus bas)
        render_glossary(st.session_state.get("img_selected_index"))

    if st.session_state.get("img_error"):
        st.error(st.session_state.img_error)
        return
    df = st.session_state.get("img_series")
    if df is None:
        st.info(t("img_click"))
        return
    if len(df) < 1:
        st.warning(t("img_none"))
        return

    dates = [to_date(d) for d in df["date"]]
    st.success(t("img_found", n=len(dates), a=f"{dates[0]:%d/%m/%Y}", b=f"{dates[-1]:%d/%m/%Y}"))

    # --- Choix du volet, de la couche et des deux dates -------------------------------------------
    p1, p2 = st.columns([1, 1.3])
    theme = p1.radio(t("img_theme"), list(THEMES), format_func=lambda k: theme_label(k, lang), key="img_theme")
    options = layers_for_theme(theme)
    layer = p2.radio(t("img_layer"), options, format_func=lambda k: layer_text(k, "label", lang),
                     key=f"img_layer_{theme}")
    st.caption(layer_text(layer, "description", lang))
    selected_index = {"NDVI_ANOM": "NDVI", "NDVI_ZONES": "NDVI"}.get(layer, layer)
    if st.session_state.get("img_selected_index") != selected_index:
        st.session_state.img_selected_index = selected_index
        st.rerun()  # rouvre le guide sur l'indice de la carte choisie

    d1, d2 = st.columns(2)
    fmt = (lambda d: d.strftime("%d/%m/%Y"))
    day_a = d1.selectbox(t("img_date_a"), dates, index=0, format_func=fmt, key="img_day_a")
    day_b = d2.selectbox(t("img_date_b"), dates, index=len(dates) - 1, format_func=fmt, key="img_day_b")

    try:
        with st.spinner(t("img_preparing")):
            maps = _maps(coords_json, layer, day_a, day_b)
    except ValueError as e:
        st.warning(t("img_no_history") if layer == "NDVI_ANOM" else str(e))
        return
    except Exception as e:
        logger.exception("Cartes Sentinel-2")
        st.error(t("img_maps_error", e=e))
        return

    spec = LAYERS[layer]
    if spec["palette"]:
        st.markdown(legend_html(spec["min"], spec["max"], spec["palette"], layer_text(layer, "low", lang),
                                layer_text(layer, "high", lang), layer_text(layer, "label", lang)),
                    unsafe_allow_html=True)
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
            low, high = diff_labels(layer, lang)
            st.markdown(t("img_change"))
            st.markdown(legend_html(d["min"], d["max"], d["palette"], low, high),
                        unsafe_allow_html=True)
            _map(coordinates, maps["diff"], f"{layer} B-A", key=f"img_map_d_{layer}_{day_a}_{day_b}", height=340)
        else:
            st.caption(t("img_no_diff"))
    with c_info:
        if day_a != day_b:
            st.markdown(t("img_means"))
            table = _summary_table(df, day_a, day_b, lang)
            colors = [f"color:{TREND_COLORS[s]}" for s in table.pop("_status")]
            st.dataframe(
                table.style.apply(lambda _: colors, subset=[t("img_col_trend")], axis=0),
                hide_index=True, width="stretch",
            )
        st.link_button(t("img_geotiff"), maps["geotiff_b"])
        st.caption(t("img_cause_note"))

    if day_a != day_b:
        row_a = df[df["date"] == pd.Timestamp(day_a)].iloc[0]
        row_b = df[df["date"] == pd.Timestamp(day_b)].iloc[0]
        try:
            fractions = _change(coords_json, day_a, day_b)
        except Exception:
            logger.exception("Part de la parcelle en baisse")
            fractions = None
        render_interpretation(interpret_change(
            {k: row_a[k] for k in SERIES_INDICES}, {k: row_b[k] for k in SERIES_INDICES},
            day_a, day_b, crop=crop, fractions=fractions, lang=lang,
        ))
        st.divider()
        render_zones(coordinates, coords_json, day_a, day_b, crop, lang)
    else:
        st.info(t("img_pick_two"))

    st.markdown(t("img_series_title"))
    chosen = st.multiselect(t("img_series_pick"), SERIES_INDICES, default=["NDVI", "NDMI", "NDRE"], key="img_series_idx")
    if chosen:
        st.plotly_chart(_plot_series(df, chosen, day_a, day_b), width="stretch",
                        config={"displayModeBar": False})
