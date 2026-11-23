"""
app.py
======
HydroStress Maroc — tableau de bord sur une seule page.

1. En-tête : présentation du service et des sources de données
2. Carte (choix de la zone + dessin de la parcelle) et panneau d'analyse côte à côte
3. Un seul bouton : extraction des données + prédiction + rapport
4. Rapport complet sur la même page, téléchargeable en HTML
5. En bas : informations sur le modèle et simulation manuelle
"""

import json
import logging
import os
from datetime import datetime, timedelta

import folium
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from folium.plugins import Draw, Geocoder
from plotly.subplots import make_subplots
from shapely.geometry import Polygon
from streamlit_folium import st_folium

from demo import make_demo_extraction
from farm_ui import render_farm_training
from contrib_ui import render_contribution
from i18n import LANGS, RTL_LANGS, get_lang, set_lang, t
from i18n_pages import translate_error
from security import admin_password, allow, check_password, log_incident, MAX_ADMIN_ATTEMPTS
from report_text import (class_label, class_summary, crop_name, index_description, localized_recommendations,
                         status_label, zone_name)
from imagery_ui import render_imagery
from extract_data import (
    DataPipeline,
    DataUnavailableError,
    day_of_year_cyclic,
    polygon_area_km2,
    validate_geometry,
)
from predict import HydroStressPredictor
from region import CROPS, MAP_CENTER, MAP_ZOOM, ZONES, zone_for_point
from report import CLASS_STYLES, STATUS_LABELS, build_report, report_to_html
from stations import validate_analysis

st.set_page_config(
    page_title="HydroStress Maroc",
    page_icon="💧",
    layout="wide",
    initial_sidebar_state="collapsed",
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ACCENT = "#2DD4BF"


def app_setting(name: str, default: str = "") -> str:
    """Réglage lu dans l'environnement, puis dans st.secrets (Streamlit Cloud)."""
    value = os.environ.get(name)
    if value is None:
        try:
            value = st.secrets.get(name)
        except Exception:
            value = None
    return str(value).strip() if value not in (None, "") else default


# Service en production : plus de badge BÊTA ni de mention « démonstration »
# (un ancien réglage HYDROSTRESS_STAGE dans les Secrets est ignoré).
IS_BETA = False
BRAND = app_setting("HYDROSTRESS_BRAND", "")

# ---------------------------------------------------------------------------
# Style
# ---------------------------------------------------------------------------
st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Sans+Arabic:wght@400;500;600;700&display=swap');
:root {
  --paper:#F7F8F3; --surface:#FFFFFF; --ink:#142019; --muted:#5C6B61; --line:#DDE3DA;
  --palm:#1D6B45; --palm-soft:#E6F0E8; --water:#1C6CA8; --ochre:#9A6412; --ochre-soft:#FBF1DC;
  --alert:#B42318;
}
html, body, .stApp, .stApp p, .stApp li, .stApp label, .stApp input, .stApp button, .stApp textarea,
.stApp h1, .stApp h2, .stApp h3, .stApp h4, .hs-hero, .hs-step {
  font-family:'IBM Plex Sans','IBM Plex Sans Arabic',system-ui,sans-serif;
}
#MainMenu, footer, [data-testid="stSidebarCollapsedControl"] {visibility:hidden;}
[data-testid="stHeader"] {background:transparent;}
.block-container {padding-top:1.2rem; padding-bottom:3rem; max-width:1320px;}

.hs-top {display:flex; align-items:baseline; gap:.5rem; margin:0 0 2.2rem;}
.hs-mark {font-size:1.15rem; font-weight:700; color:var(--ink); letter-spacing:-.01em;}
.hs-mark i {font-style:normal; color:var(--palm);}
.hs-org {color:var(--muted); font-size:.9rem;}

.hs-hero {margin:0 0 2.4rem; max-width:860px;}
.hs-hero h1 {font-size:clamp(2.1rem,4.2vw,3.3rem); line-height:1.08; font-weight:600; letter-spacing:-.025em;
  color:var(--ink); margin:0 0 1rem; padding:0;}
.hs-hero .lead {font-size:1.08rem; line-height:1.6; color:var(--muted); max-width:68ch; margin:0 0 1.6rem;}
.hs-strip {max-width:560px; margin:0 0 .9rem;}
.hs-strip .band {height:14px; border-radius:7px;
  background:linear-gradient(90deg,#CDB98F 0%,#E6DCAE 22%,#B8CF8E 48%,#5FA266 74%,#1D6B45 100%);}
.hs-strip .ends {display:flex; justify-content:space-between; font-size:.8rem; color:var(--muted); margin-top:.35rem;}
.hs-sources {font-size:.85rem; color:var(--muted); margin:0;}
.hs-tag {display:inline-block; margin-inline-start:.4rem; padding:2px 10px; border-radius:999px; font-size:.78rem;
  background:var(--palm-soft); color:var(--palm);}
.hs-tag.warn {background:var(--ochre-soft); color:var(--ochre);}
.hs-chip {display:inline-block; padding:4px 11px; margin:4px 6px 0 0; border-radius:999px; font-size:.8rem;
  background:var(--surface); border:1px solid var(--line); color:var(--ink);}

.hs-steps {list-style:none; display:grid; grid-template-columns:repeat(3,1fr); gap:0; margin:0 0 2.4rem; padding:0;
  border-top:1px solid var(--line);}
.hs-step {padding:1rem 1.4rem 0 0; color:var(--ink); font-size:.95rem; line-height:1.5;}
.hs-step .n {display:inline-flex; width:1.6rem; height:1.6rem; border-radius:50%; align-items:center; justify-content:center;
  background:var(--palm); color:#fff; font-weight:600; font-size:.85rem; margin-bottom:.5rem;}

.hs-section {font-size:1.05rem; font-weight:600; color:var(--ink); margin:.4rem 0 .7rem;}

.hs-status {border-radius:14px; padding:20px 24px; border:1px solid var(--line); background:var(--surface);}
.hs-status .lbl {font-size:.85rem; color:var(--muted);}
.hs-status .val {font-size:2.3rem; font-weight:700; line-height:1.15; letter-spacing:-.02em;}
.hs-status .sub {color:var(--ink); margin-top:4px;}

.hs-kpi {background:var(--surface); border:1px solid var(--line); border-radius:10px; padding:12px 14px; height:100%;}
.hs-kpi .k {color:var(--muted); font-size:.8rem;}
.hs-kpi .v {color:var(--ink); font-size:1.4rem; font-weight:600; margin-top:2px; font-variant-numeric:tabular-nums;}
.hs-kpi .s {font-size:.78rem; margin-top:2px;}

.hs-parcel {background:var(--palm-soft); border-radius:10px; padding:12px 14px; color:var(--ink); font-size:.9rem;
  margin:6px 0 12px; line-height:1.55;}
.hs-banner {border-radius:10px; padding:10px 14px; font-size:.9rem; margin-bottom:12px;
  background:var(--ochre-soft); color:var(--ochre);}
.hs-hero h1 span.hs-beta {display:inline-block; margin-inline-start:10px; padding:3px 10px; border-radius:999px;
  font-size:.75rem; font-weight:600; vertical-align:middle; color:var(--ink) !important; background:#F2D16B;}
.hs-betabar {background:var(--ochre-soft); color:var(--ochre); border-radius:10px; padding:10px 16px;
  margin-bottom:14px; font-size:.9rem;}
.hs-foot {color:var(--muted); font-size:.8rem; text-align:center; margin-top:2.5rem; padding-top:1.2rem;
  border-top:1px solid var(--line);}

div.stButton > button, div.stDownloadButton > button, div.stLinkButton > a {border-radius:8px; font-weight:600;}
button:focus-visible, a:focus-visible, input:focus-visible {outline:2px solid var(--water) !important; outline-offset:2px;}
.st-key-lang_select {max-width:190px; margin-inline-start:auto;}
[data-testid="stExpander"] details {border-radius:10px; border-color:var(--line); background:var(--surface);}
@media (max-width: 900px) { .hs-steps {grid-template-columns:1fr;} .hs-step {padding-right:0;} }
@media (prefers-reduced-motion: reduce) { * {animation:none !important; transition:none !important;} }
</style>
""",
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Ressources
# ---------------------------------------------------------------------------
def model_version() -> str:
    """Date des fichiers du modèle : un nouveau modèle déployé invalide le cache."""
    try:
        return "|".join(str(os.path.getmtime(f"models/hydrostress{suffix}"))
                        for suffix in ("_pipeline.joblib", "_metadata.json"))
    except OSError:
        return "absent"


@st.cache_resource(show_spinner=False)
def get_predictor(version: str = ""):
    try:
        return HydroStressPredictor()
    except Exception as e:  # modèle absent ou illisible
        logger.exception("Chargement du modèle")
        return e


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def latest_weather_date():
    """
    Date d'analyse proposée par défaut : le dernier jour publié à la fois par CHIRPS et par ERA5-Land
    (CHIRPS est mis en ligne avec plusieurs semaines de retard). Sans Earth Engine : il y a 60 jours.
    """
    fallback = (datetime.now() - timedelta(days=60)).date()
    try:
        import ee
        from extract_data import CHIRPS_COLLECTION, ERA5_COLLECTION, initialize_earth_engine
        initialize_earth_engine()
        since = (datetime.now() - timedelta(days=150)).strftime("%Y-%m-%d")
        last = [ee.ImageCollection(c).filterDate(since, datetime.now().strftime("%Y-%m-%d"))
                .aggregate_max("system:time_start") for c in (CHIRPS_COLLECTION, ERA5_COLLECTION)]
        ms = ee.List(last).getInfo()
        if not all(ms):
            return fallback
        latest = pd.Timestamp(min(ms), unit="ms").date()
        return min(latest, (datetime.now() - timedelta(days=5)).date())
    except Exception:
        logger.exception("Dernière date météo disponible")
        return fallback


def get_pipeline() -> DataPipeline:
    """Non mis en cache : les jetons Earth Engine expirent."""
    return DataPipeline()


def init_state():
    for key, val in {"result": None, "parcel_key": None, "error": None, "detected_zone": None,
                     "station": None}.items():
        st.session_state.setdefault(key, val)


init_state()


# ---------------------------------------------------------------------------
# Composants
# ---------------------------------------------------------------------------
def model_origin(meta) -> str:
    """Libellé lisible de l'origine du modèle (ex. « Bloc 4 · Amandier · Errachidia »)."""
    src = str(meta.get("data_source", ""))
    if src == "synthetic":
        return "Synthétiques"
    if src.startswith("terrain:"):
        label = meta.get("origin_label") or f"ferme {src.split(':', 1)[1]}"
        return t("origin_almond_errachidia") if label == "ferme d'amandiers à Errachidia" else label
    return src or "—"


def hero(predictor):
    meta = getattr(predictor, "metadata", None) or {}
    tag = ""
    if meta.get("data_source") == "synthetic":
        tag = f"<span class='hs-tag warn'>{t('chip_synthetic')}</span>"
    elif str(meta.get("data_source", "")).startswith("terrain:"):
        tag = f"<span class='hs-tag'>{t('chip_real', origin=model_origin(meta))}</span>"
    beta_badge = "<span class='hs-beta'>BÊTA</span>" if IS_BETA else ""
    by = f"{BRAND} · " if BRAND else ""
    beta_bar = f"<div class='hs-betabar'>{t('beta_bar', by=by)}</div>" if IS_BETA else ""
    org = f"<span class='hs-org'>· {BRAND}</span>" if BRAND else ""
    steps = "".join(f"<li class='hs-step'><span class='n'>{n}</span><div>{t(f'step{n}')}</div></li>" for n in (1, 2, 3))
    st.markdown(
        f"""
{beta_bar}
<div class="hs-top"><span class="hs-mark">HydroStress <i>Maroc</i></span>{org}</div>
<section class="hs-hero">
  <h1>{t('hero_title')}{beta_badge}</h1>
  <p class="lead">{t('hero_intro')}</p>
  <div class="hs-strip" aria-hidden="true"><div class="band"></div>
    <div class="ends"><span>{t('strip_low')}</span><span>{t('strip_high')}</span></div></div>
  <p class="hs-sources">{t('hero_sources')}{tag}</p>
</section>
<ol class="hs-steps">{steps}</ol>
""",
        unsafe_allow_html=True,
    )


ZONE_COLORS = ["#2DD4BF", "#38BDF8", "#A78BFA", "#F472B6", "#FACC15", "#FB923C", "#4ADE80", "#F87171", "#E2E8F0"]


def build_map(center, zoom):
    m = folium.Map(location=list(center), zoom_start=zoom, tiles=None, control_scale=True,
                   min_zoom=5, max_bounds=True, min_lat=19, max_lat=37.5, min_lon=-19, max_lon=1)
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Esri World Imagery", name=t("map_satellite"),
    ).add_to(m)
    folium.TileLayer("OpenStreetMap", name=t("map_plan"), show=False).add_to(m)   # Satellite reste la vue par défaut
    # Noms des villes, villages et frontières par-dessus l'image satellite (affichés par défaut)
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}",
        attr="Esri Boundaries & Places", name=t("map_places"), overlay=True, control=True, show=True,
    ).add_to(m)
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Transportation/MapServer/tile/{z}/{y}/{x}",
        attr="Esri Transportation", name=t("map_roads"), overlay=True, control=True, show=False,
    ).add_to(m)
    for color, zone in zip(ZONE_COLORS, ZONES.values()):
        for place, (lat, lon) in zone["places"].items():
            folium.CircleMarker(location=[lat, lon], radius=5, color=color, fill=True, fill_opacity=.9,
                                tooltip=f"{place} — {zone['name']}").add_to(m)
    Draw(
        export=False,
        draw_options={
            "polyline": False, "circle": False, "circlemarker": False, "marker": False,
            "polygon": {"allowIntersection": False, "showArea": True,
                        "shapeOptions": {"color": "#F2D16B"}},
            "rectangle": {"showArea": True, "shapeOptions": {"color": "#F2D16B"}},
        },
        edit_options={"edit": False, "remove": True},
    ).add_to(m)
    # Recherche d'un lieu (ville, douar, commune) pour se déplacer vite jusqu'à sa ferme
    Geocoder(collapsed=False, position="topleft", add_marker=False,
             placeholder=t("map_search")).add_to(m)
    folium.LayerControl(position="topright", collapsed=False).add_to(m)
    return m


def map_legend():
    """Sous la carte : ce que sont les points colorés (localités de référence, une couleur par zone)."""
    lang = get_lang()
    chips = "".join(
        f"<span class='hs-chip'><span style='color:{color};-webkit-text-stroke:1px rgba(20,32,25,.35)'>●</span> "
        f"{zone_name(zid, zone['name'], lang)}</span>"
        for color, (zid, zone) in zip(ZONE_COLORS, ZONES.items())
    )
    st.markdown(f"<div style='color:var(--muted);font-size:.85rem;line-height:1.5;margin:8px 0 4px'>{t('map_legend')}</div>{chips}",
                unsafe_allow_html=True)


def kpi(label, value, sub="", color="var(--muted)"):
    st.markdown(
        f"<div class='hs-kpi'><div class='k'>{label}</div><div class='v'>{value}</div>"
        f"<div class='s' style='color:{color}'>{sub}</div></div>",
        unsafe_allow_html=True,
    )


STATUS_COLORS = {"healthy": "#1D6B45", "low": "#B42318", "high": "#9A6412", "unknown": "#5C6B61"}


def plot_probabilities(probs):
    labels = [class_label(i, get_lang()) for i in range(3)]
    values = [probs["normal"], probs["moderate"], probs["severe"]]
    fig = go.Figure(go.Bar(
        x=values, y=labels, orientation="h",
        marker_color=["#1D6B45", "#C98A1B", "#B42318"],
        text=[f"{v:.1f} %" for v in values], textposition="outside", cliponaxis=False,
    ))
    fig.update_layout(
        template="plotly_white", height=210, margin=dict(l=10, r=40, t=10, b=10),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(range=[0, 100], showgrid=False, visible=False), yaxis=dict(autorange="reversed"),
    )
    return fig


def plot_weather(chirps: pd.DataFrame, era5: pd.DataFrame):
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    if not chirps.empty:
        fig.add_trace(go.Bar(x=chirps["date"], y=chirps["precipitation_mm"], name=t("pl_rain"),
                             marker_color="#1C6CA8", opacity=.75), secondary_y=False)
    if not era5.empty:
        fig.add_trace(go.Scatter(x=era5["date"], y=era5["temperature_max_c"], name=t("pl_tmax"),
                                 line=dict(color="#B42318", width=2)), secondary_y=True)
        fig.add_trace(go.Scatter(x=era5["date"], y=era5["temperature_c"], name=t("pl_tmean"),
                                 line=dict(color="#C98A1B", width=2, dash="dot")), secondary_y=True)
    fig.update_layout(
        template="plotly_white", height=300, margin=dict(l=10, r=10, t=10, b=10),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", y=1.12, x=0), bargap=.25,
    )
    fig.update_yaxes(title_text="mm", secondary_y=False, showgrid=False)
    fig.update_yaxes(title_text="°C", secondary_y=True, gridcolor="#E3E8E0")
    return fig


# ---------------------------------------------------------------------------
# Analyse
# ---------------------------------------------------------------------------
def run_analysis(predictor, coordinates, crop, analysis_date, lookback, demo: bool):
    """Extraction + prédiction + rapport, résultat stocké dans la session."""
    st.session_state.error = None
    ok, wait = allow("analysis", st.session_state)
    if not ok:
        st.session_state.error = t("sec_rate", m=max(1, wait // 60))
        return
    with st.status(t("an_running"), expanded=True) as status:
        try:
            st.write(t("an_validate"))
            poly = validate_geometry(coordinates)
            date_str = analysis_date.strftime("%Y-%m-%d")
            if demo:
                st.write(t("an_demo"))
                data = make_demo_extraction(coordinates, date_str, lookback)
            else:
                st.write(t("an_connect"))
                pipeline = get_pipeline()
                st.write(t("an_extract"))
                data = pipeline.extract_all_data(coordinates, date_str, lookback)
            zone_info = data["zone"]
            zone_text = f"{zone_info['name']} (près de {zone_info['nearest_place']})"
            st.write(t("an_predict"))
            prediction = predictor.predict(data["features"])
            if not demo:
                predictor.log_prediction(prediction)
            report = build_report(
                coordinates=coordinates, area_km2=polygon_area_km2(poly), zone=zone_text, crop=crop, data=data,
                prediction=prediction,
                recommendations=predictor.get_recommendations(prediction, crop, zone_info["id"]),
                interpretation=predictor.interpret_indices(data["features"], zone_info["id"]),
                model_meta=predictor.metadata,
            )
            report["zone_id"] = zone_info["id"]
            st.session_state.result = {"data": data, "report": report}
            st.session_state.station = None
            status.update(label=t("an_done"), state="complete", expanded=False)
        except (DataUnavailableError, ValueError) as e:
            st.session_state.error = translate_error(str(e), get_lang())
            status.update(label=t("an_failed"), state="error", expanded=False)
        except Exception as e:  # détail dans les journaux du serveur, jamais à l'écran
            st.session_state.error = t("sec_service", ref=log_incident("analyse", e))
            status.update(label=t("an_failed"), state="error", expanded=False)


def render_report(result):
    report, data = result["report"], result["data"]
    lang = get_lang()
    pred = report["prediction"]
    idx = pred["class_index"]
    style = CLASS_STYLES[idx]
    interp = report["interpretation"]
    w = report["weather"]
    zone_info = data["zone"]
    zone_txt = t("zone_near", zone=zone_name(zone_info["id"], zone_info["name"], lang), place=zone_info["nearest_place"])
    crop_txt = crop_name(report["crop"], lang)

    st.markdown(f"<div class='hs-section'>{t('rp_title')}</div>", unsafe_allow_html=True)
    if report["demo"]:
        st.markdown(f"<div class='hs-banner'>{t('rp_demo')}</div>", unsafe_allow_html=True)

    c_status, c_prob = st.columns([1.1, 1], gap="large")
    with c_status:
        lat, lon = report["parcel"]["centroid"]
        conf_line = t("rp_conf_line", conf=pred["confidence_percent"], zone=zone_txt, crop=crop_txt,
                      date=report["analysis_date"], ha=report["parcel"]["area_ha"], lat=lat, lon=lon)
        st.markdown(
            f"""<div class="hs-status" style="border-left:8px solid {style['color']}">
<div class="lbl">{t('rp_level')}</div>
<div class="val" style="color:{style['color']}">{class_label(idx, lang)}</div>
<div class="sub">{class_summary(idx, lang)}</div>
<div class="sub" style="color:var(--muted);margin-top:10px;font-size:.88rem">
{conf_line}</div></div>""",
            unsafe_allow_html=True,
        )
    with c_prob:
        st.markdown(f"<div class='hs-section'>{t('rp_probs')}</div>", unsafe_allow_html=True)
        st.plotly_chart(plot_probabilities(pred["probabilities"]), width="stretch",
                        config={"displayModeBar": False})

    st.write("")
    cols = st.columns(6)
    tiles = [
        (t("kpi_ndvi"), f"{interp['NDVI']['value']:.2f}", interp["NDVI"]["status"]),
        (t("kpi_ndwi"), f"{interp['NDWI']['value']:.2f}", interp["NDWI"]["status"]),
        (t("kpi_msi"), f"{interp['MSI']['value']:.2f}", interp["MSI"]["status"]),
        (t("kpi_rain30"), f"{w['precipitation_30d_mm']} mm", None),
        (t("kpi_tmax30"), f"{w['temperature_max_c']} °C", None),
        (t("kpi_dry"), f"{w['dry_days_max']}", None),
    ]
    for col, (label, value, status) in zip(cols, tiles):
        with col:
            if status:
                kpi(label, value, f"● {status_label(status, lang)}", STATUS_COLORS[status])
            else:
                kpi(label, value, "&nbsp;")

    meta = report["sentinel_meta"]
    if meta:
        st.caption(t("rp_s2", n=meta["image_count"], d=meta["window_days"], v=f"{meta['valid_pixel_fraction']:.0%}"))

    c_weather, c_reco = st.columns([1.4, 1], gap="large")
    with c_weather:
        st.markdown(f"<div class='hs-section'>{t('rp_weather')}</div>", unsafe_allow_html=True)
        st.plotly_chart(plot_weather(data["chirps_series"], data["era5_series"]), width="stretch",
                        config={"displayModeBar": False})
    with c_reco:
        rec = localized_recommendations(idx, report["crop"], report.get("zone_id"),
                                        report["recommendations"]["priority"], lang)
        st.markdown(f"<div class='hs-section'>{t('rp_reco', p=rec['priority'])}</div>", unsafe_allow_html=True)
        with st.container(border=True):
            st.markdown(f"**{rec['title']}**")
            for action in rec["actions"]:
                st.markdown(f"- {action}")

    c_idx, c_dl = st.columns([1.4, 1], gap="large")
    with c_idx:
        st.markdown(f"<div class='hs-section'>{t('rp_indices')}</div>", unsafe_allow_html=True)
        table = pd.DataFrame([
            {t("col_index"): k, t("col_value"): v["value"],
             t("col_ref"): f"{v['healthy_range'][0]} – {v['healthy_range'][1]}",
             t("col_state"): status_label(v["status"], lang),
             t("col_desc"): index_description(k, v["description"], lang)}
            for k, v in interp.items()
        ])
        st.dataframe(table, hide_index=True, width="stretch")
    with c_dl:
        st.markdown(f"<div class='hs-section'>{t('rp_export')}</div>", unsafe_allow_html=True)
        st.download_button(
            t("rp_dl_html"), data=report_to_html(report, lang=lang, zone_label=zone_txt),
            file_name=f"rapport_hydrostress_{report['analysis_date']}.html", mime="text/html",
            type="primary", width="stretch",
        )
        st.download_button(
            t("rp_dl_json"),
            data=json.dumps({"report": report, "features": data["features"]}, ensure_ascii=False,
                            indent=2, default=str),
            file_name=f"hydrostress_{report['analysis_date']}.json", mime="application/json",
            width="stretch",
        )
        st.caption(t("rp_print"))

    render_station_validation(report, data)


def render_station_validation(report, data):
    st.markdown(f"<div class='hs-section'>{t('st_title')}</div>", unsafe_allow_html=True)
    with st.container(border=True):
        st.caption(t("st_intro"))
        if report["demo"]:
            st.info(t("st_demo"))
            return
        if st.button(t("st_btn"), key="station_btn"):
            ok, wait = allow("station", st.session_state)
            if not ok:
                st.warning(t("sec_rate", m=max(1, wait // 60)))
                return
            lat, lon = report["parcel"]["centroid"]
            with st.spinner(t("st_searching")):
                try:
                    st.session_state.station = validate_analysis(lat, lon, data["chirps_series"],
                                                                 data["era5_series"])
                except Exception as e:
                    st.session_state.station = {"station": None,
                                                "message": t("sec_service", ref=log_incident("station NOAA", e))}
        res = st.session_state.station
        if not res:
            return
        if not res.get("station"):
            msg = res.get("message") or ""
            if msg.startswith("Aucune station NOAA"):
                msg = t("st_none_near", km=150)
            elif msg.startswith("Les stations proches"):
                msg = t("st_no_data")
            st.warning(msg or t("st_none"))
            return
        stn, m = res["station"], res["metrics"]
        st.markdown(t("st_header", name=stn["name"], km=stn["distance_km"], alt=f"{stn['elevation_m']:.0f}"))
        rows = []
        labels = {"temperature_mean": t("st_tmean"), "temperature_max": t("st_tmax"), "precipitation": t("st_rain")}
        for key, label in labels.items():
            if key in m:
                rows.append({t("st_col_var"): label, t("st_col_days"): m[key]["days"], t("st_col_bias"): m[key]["bias"],
                             t("st_col_mae"): m[key]["mae"], t("st_col_corr"): m[key]["corr"]})
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
        if "precipitation" in m:
            p = m["precipitation"]
            st.caption(t("st_rain_total", s=p["total_station_mm"], g=p["total_grid_mm"]))
        series, era5 = res["series"], data["era5_series"]
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=series["date"], y=series["temperature_c"], name=t("st_series_station"),
                                 line=dict(color="#142019", width=2)))
        if not era5.empty:
            fig.add_trace(go.Scatter(x=era5["date"], y=era5["temperature_c"], name=t("st_series_era5"),
                                     line=dict(color="#C98A1B", width=2, dash="dot")))
        fig.update_layout(template="plotly_white", height=260, margin=dict(l=10, r=10, t=10, b=10),
                          paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                          legend=dict(orientation="h", y=1.15, x=0), yaxis_title="°C")
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


# ---------------------------------------------------------------------------
# Bas de page : modèle et simulation
# ---------------------------------------------------------------------------
def render_model_section(predictor):
    meta = predictor.metadata or {}
    metrics = meta.get("test_metrics") or {}
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        origin = model_origin(meta)
        kpi(t("md_source"), origin[:1].upper() + origin[1:])
    with c2:
        kpi(t("md_samples"), meta.get("training_samples", "—"))
    with c3:
        kpi(t("md_accuracy"), f"{metrics['accuracy']:.0%}" if metrics else "—")
    with c4:
        kpi(t("md_trained"), (meta.get("created_at") or "—")[:10])
    if meta.get("data_source") == "synthetic":
        st.caption(t("md_synth"))
    elif str(meta.get("data_source", "")).startswith("terrain:"):
        details = f" ({meta['origin_details']})" if meta.get("origin_details") else ""
        st.caption(t("md_real", origin=model_origin(meta), details=details))


def render_simulation(predictor):
    month = datetime.now().month - 1
    lang = get_lang()
    zone_id = st.selectbox(t("sm_zone"), list(ZONES), format_func=lambda z: zone_name(z, ZONES[z]["name"], lang),
                           key="sim_zone")
    zone = ZONES[zone_id]
    c1, c2, c3 = st.columns(3)
    with c1:
        ndvi = st.slider("NDVI", -0.1, 0.9, 0.45, 0.01, key="sim_ndvi")
        ndwi = st.slider("NDWI", -0.4, 0.6, 0.15, 0.01, key="sim_ndwi")
        msi = st.slider("MSI", 0.2, 2.5, 0.75, 0.01, key="sim_msi")
    with c2:
        precip_30j = st.slider(t("sm_rain"), 0.0, 150.0, float(zone["precip"][month]), 1.0, key=f"sim_p_{zone_id}")
        dry_days = st.slider(t("sm_dry"), 0, 30, 20, 1, key="sim_dry")
        crop = st.selectbox(t("sm_crop"), zone["crops"], format_func=lambda c: crop_name(c, lang),
                            key=f"sim_crop_{zone_id}")
    with c3:
        temp_mean = st.slider(t("sm_tmean"), -5.0, 45.0, float(zone["temp"][month]), 0.5, key=f"sim_t_{zone_id}")
        temp_max = st.slider(t("sm_tmax"), 0.0, 52.0, float(zone["temp"][month] + 11), 0.5, key=f"sim_tmax_{zone_id}")
        humidity = st.slider(t("sm_rh"), 0.0, 100.0, float(zone["rh"][month]), 1.0, key=f"sim_rh_{zone_id}")

    sin_doy, cos_doy = day_of_year_cyclic(datetime.now())
    data = {
        "NDVI_mean": ndvi, "NDVI_min": max(ndvi - 0.15, -0.1), "NDVI_max": min(ndvi + 0.15, 0.95), "NDVI_std": 0.08,
        "NDWI_mean": ndwi, "NDWI_std": 0.06,
        "MSI_mean": msi, "MSI_min": max(msi - 0.25, 0.1), "MSI_max": msi + 0.25, "MSI_std": 0.12,
        "SAVI_mean": 0.72 * ndvi, "EVI_mean": 0.62 * ndvi,
        "precipitation_total_30j": precip_30j, "precipitation_total_7j": precip_30j / 4,
        "precipitation_mean": precip_30j / 30.0, "max_consecutive_dry_days": float(dry_days),
        "rainy_days_count": float(min(30 - dry_days, round(precip_30j / 4))),
        "temperature_mean": temp_mean, "temperature_max": temp_max, "temperature_min": temp_mean - 10,
        "humidity_mean": humidity, "humidity_min": max(humidity - 18.0, 3.0),
        "day_of_year_sin": sin_doy, "day_of_year_cos": cos_doy,
        "elevation_m": float(sum(zone["elevation"]) / 2), "precip_annual_normal_mm": float(sum(zone["precip"])),
    }
    pred = predictor.predict(data)
    style = CLASS_STYLES[pred["class_index"]]
    base = predictor.get_recommendations(pred, crop, zone_id)
    rec = localized_recommendations(pred["class_index"], crop, zone_id, base["priority"], lang)
    c_res, c_rec = st.columns([1, 1.4], gap="large")
    with c_res:
        st.markdown(
            f"<div class='hs-status' style='border-left:8px solid {style['color']}'>"
            f"<div class='lbl'>{t('sm_result')}</div><div class='val' style='color:{style['color']}'>"
            f"{class_label(pred['class_index'], lang)}</div>"
            f"<div class='sub'>{t('sm_conf', c=pred['confidence_percent'])}</div></div>",
            unsafe_allow_html=True,
        )
    with c_rec:
        for action in rec["actions"][:3]:
            st.markdown(f"- {action}")


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------
def render_admin_area():
    """
    Entraînement sur une ferme : réservé à l'administrateur (registres et positions de fermes, quota Earth Engine).
    Visible seulement avec ?admin=1 dans l'adresse ET un mot de passe HYDROSTRESS_ADMIN_PASSWORD dans les Secrets.
    """
    expected = admin_password(app_setting)
    if not expected or st.query_params.get("admin") != "1":
        return
    with st.expander(t("adm_title"), expanded=not st.session_state.get("admin_ok")):
        if not st.session_state.get("admin_ok"):
            if st.session_state.get("admin_fails", 0) >= MAX_ADMIN_ATTEMPTS:
                st.error(t("adm_locked"))
                return
            with st.form("admin_login"):
                given = st.text_input(t("adm_password"), type="password")
                if st.form_submit_button(t("adm_open")):
                    if check_password(given, expected):
                        st.session_state.admin_ok = True
                        st.rerun()
                    st.session_state.admin_fails = st.session_state.get("admin_fails", 0) + 1
                    st.error(t("adm_wrong"))
            return
        if st.button(t("adm_logout"), key="admin_logout"):
            st.session_state.admin_ok = False
            st.rerun()
        st.markdown(f"**{t('exp_farm')}**")
        render_farm_training()


def language_switcher():
    """Choix de la langue (Français, العربية, English), mémorisé dans l'URL (?lang=ar) pour le partage."""
    if "lang" not in st.session_state:
        set_lang(st.query_params.get("lang", "fr"))
    _, c_lang = st.columns([5, 1])
    with c_lang:
        lang = st.selectbox(t("lang_label"), list(LANGS), index=list(LANGS).index(get_lang()),
                            format_func=LANGS.get, key="lang_select", label_visibility="collapsed")
    if lang != get_lang():
        set_lang(lang)
        st.query_params["lang"] = lang
        st.rerun()
    if lang in RTL_LANGS:  # arabe : lecture de droite à gauche (les cartes et graphiques restent tels quels)
        st.markdown(
            "<style>.block-container{direction:rtl;text-align:right;}"
            ".block-container iframe,.block-container .js-plotly-plot,[data-testid='stDataFrame']{direction:ltr;}"
            ".hs-hero h1 span.hs-beta{margin-left:0;margin-right:10px;}</style>",
            unsafe_allow_html=True,
        )


def main():
    predictor = get_predictor(model_version())
    if isinstance(predictor, Exception):
        st.error(f"Le modèle de prédiction n'a pas pu être chargé : {predictor}")
        st.info("Entraînez un modèle : `python train_model.py training_data.csv --source synthetic`")
        return

    language_switcher()
    hero(predictor)

    col_map, col_panel = st.columns([1.65, 1], gap="large")

    with col_panel:
        st.markdown(f"<div class='hs-section'>{t('sec_params')}</div>", unsafe_allow_html=True)
        c_zone, c_place = st.columns(2)
        with c_zone:
            zone_choice = st.selectbox(t("region"), ["Tout le Maroc"] + list(ZONES),
                                       format_func=lambda z: zone_name(z, ZONES[z]["name"], get_lang())
                                       if z in ZONES else t("all_morocco"))
        with c_place:
            places = ["Toute la région"] + (list(ZONES[zone_choice]["places"]) if zone_choice in ZONES else [])
            place = st.selectbox(t("place"), places, disabled=zone_choice not in ZONES,
                                 format_func=lambda p: t("all_region") if p == "Toute la région" else p)
        # Cultures : celles de la zone choisie ou détectée en premier, puis les autres
        crop_zone = zone_choice if zone_choice in ZONES else st.session_state.detected_zone
        zone_crops = ZONES[crop_zone]["crops"] if crop_zone in ZONES else []
        crop = st.selectbox(t("crop"), zone_crops + [c for c in CROPS if c not in zone_crops],
                            format_func=lambda c: crop_name(c, get_lang()))
        c_date, c_win = st.columns(2)
        with c_date:
            analysis_date = st.date_input(
                t("analysis_date"), value=latest_weather_date(),
                min_value=datetime(2017, 4, 1), max_value=datetime.now() - timedelta(days=5),
                help=t("analysis_date_help"),
            )
        with c_win:
            lookback = st.select_slider(t("window"), options=[15, 20, 30, 45, 60], value=30,
                                        format_func=lambda d: t("days", d=d), help=t("window_help"))

    if zone_choice not in ZONES:
        center, zoom = MAP_CENTER, MAP_ZOOM
    elif place in ZONES[zone_choice]["places"]:
        center, zoom = ZONES[zone_choice]["places"][place], 14
    else:
        pts = list(ZONES[zone_choice]["places"].values())
        center, zoom = (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)), 9

    with col_map:
        st.markdown(f"<div class='hs-section'>{t('sec_map')}</div>", unsafe_allow_html=True)
        map_data = st_folium(
            build_map(center, zoom), height=560, use_container_width=True,
            returned_objects=["last_active_drawing"], key=f"map_{zone_choice}_{place}",
        )
        map_legend()

    coordinates = None
    if map_data and map_data.get("last_active_drawing"):
        geom = map_data["last_active_drawing"].get("geometry", {})
        if geom.get("type") == "Polygon":
            coordinates = geom["coordinates"][0]

    with col_panel:
        parcel_error = None
        if coordinates:
            try:
                poly = validate_geometry(coordinates)
                area_ha = polygon_area_km2(poly) * 100
                c = Polygon(coordinates).centroid
                zone_id, near, dist = zone_for_point(c.y, c.x)
                if st.session_state.detected_zone != zone_id:
                    st.session_state.detected_zone = zone_id
                    st.rerun()  # met à jour la liste des cultures
                far = t("parcel_far", d=dist) if dist > 150 else ""
                ready_html = t("parcel_ready", ha=area_ha, n=len(coordinates) - 1, lat=c.y, lon=c.x,
                               zone=zone_name(zone_id, ZONES[zone_id]["name"], get_lang()), near=near, far=far)
                st.markdown(f"<div class='hs-parcel'>{ready_html}</div>", unsafe_allow_html=True)
            except ValueError as e:
                parcel_error = translate_error(str(e), get_lang())
                st.markdown(f"<div class='hs-banner'>❌ {parcel_error}</div>", unsafe_allow_html=True)
        else:
            st.markdown(f"<div class='hs-parcel'>{t('parcel_draw')}</div>", unsafe_allow_html=True)

        ready = coordinates is not None and parcel_error is None
        analyse = st.button(t("btn_analyse"), type="primary", width="stretch", disabled=not ready)
        demo = False  # le bouton d'exemple (données de démonstration) n'est plus proposé en production

        parcel_key = json.dumps([coordinates, str(analysis_date), crop, lookback]) if coordinates else None
        if parcel_key != st.session_state.parcel_key:
            st.session_state.result = None
            st.session_state.error = None
            st.session_state.parcel_key = parcel_key

        if analyse or demo:
            run_analysis(predictor, coordinates, crop, analysis_date, lookback, demo=demo)
        if st.session_state.error:
            st.error(st.session_state.error)

    if ready:
        st.divider()
        render_imagery(coordinates, crop=crop)

    if st.session_state.result:
        st.divider()
        render_report(st.session_state.result)

    st.divider()
    with st.expander(t("exp_contrib")):
        render_contribution()
    with st.expander(t("exp_model")):
        render_model_section(predictor)
    with st.expander(t("exp_sim")):
        render_simulation(predictor)
    render_admin_area()

    owner = f"{BRAND} · " if BRAND else ""
    stage = t("footer_beta") if IS_BETA else ""
    st.markdown(f"<div class='hs-foot'>{t('footer', owner=owner, stage=stage)}</div>", unsafe_allow_html=True)


main()
