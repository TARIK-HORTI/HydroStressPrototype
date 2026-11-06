"""
app.py
======
HydroStress Errachidia — tableau de bord sur une seule page.

1. En-tête : présentation du service et des sources de données
2. Carte (choix de la zone + dessin de la parcelle) et panneau d'analyse côte à côte
3. Un seul bouton : extraction des données + prédiction + rapport
4. Rapport complet sur la même page, téléchargeable en HTML
5. En bas : informations sur le modèle et simulation manuelle
"""

import json
import logging
from datetime import datetime, timedelta

import folium
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from folium.plugins import Draw
from plotly.subplots import make_subplots
from shapely.geometry import Polygon
from streamlit_folium import st_folium

from demo import make_demo_extraction
from extract_data import (
    DataPipeline,
    DataUnavailableError,
    day_of_year_cyclic,
    polygon_area_km2,
    validate_geometry,
)
from predict import HydroStressPredictor
from region import (
    CROPS,
    MAP_CENTER,
    MAP_ZOOM,
    MONTHLY_PRECIP_MM,
    MONTHLY_RH_MEAN,
    MONTHLY_TEMP_MEAN_C,
    OASES,
    REGION_BBOX,
    REGION_NAME,
)
from report import CLASS_STYLES, STATUS_LABELS, build_report, report_to_html

st.set_page_config(
    page_title="HydroStress Errachidia",
    page_icon="💧",
    layout="wide",
    initial_sidebar_state="collapsed",
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ACCENT = "#2DD4BF"

# ---------------------------------------------------------------------------
# Style
# ---------------------------------------------------------------------------
st.markdown(
    f"""
<style>
#MainMenu, footer, [data-testid="stSidebarCollapsedControl"] {{visibility:hidden;}}
[data-testid="stHeader"] {{background:transparent;}}
.block-container {{padding-top:1.6rem; padding-bottom:3rem; max-width:1400px;}}

.hs-hero {{
  background:linear-gradient(120deg,#0F2A3D 0%,#0B1220 55%,#132A2A 100%);
  border:1px solid #1E2A40; border-radius:20px; padding:28px 32px; margin-bottom:22px;
}}
.hs-hero h1 {{font-size:2.1rem; margin:0; color:#F8FAFC; font-weight:750; letter-spacing:-.02em;}}
.hs-hero h1 span {{color:{ACCENT};}}
.hs-hero p {{color:#94A3B8; font-size:1.02rem; margin:.5rem 0 1rem; max-width:860px;}}
.hs-chip {{display:inline-block; padding:5px 12px; margin:4px 6px 0 0; border-radius:999px;
  background:rgba(45,212,191,.10); border:1px solid rgba(45,212,191,.35); color:#99F6E4; font-size:.82rem;}}
.hs-chip.warn {{background:rgba(245,158,11,.12); border-color:rgba(245,158,11,.45); color:#FCD34D;}}

.hs-steps {{display:grid; grid-template-columns:repeat(3,1fr); gap:14px; margin-bottom:22px;}}
.hs-step {{background:#131C2E; border:1px solid #1E2A40; border-radius:14px; padding:14px 18px;}}
.hs-step b {{color:{ACCENT}; font-size:.8rem; letter-spacing:.08em;}}
.hs-step div {{color:#CBD5E1; font-size:.95rem; margin-top:4px;}}

.hs-section {{font-size:.78rem; font-weight:700; letter-spacing:.12em; text-transform:uppercase;
  color:#64748B; margin:6px 0 10px;}}

.hs-status {{border-radius:16px; padding:20px 24px; border:1px solid #1E2A40; background:#131C2E;}}
.hs-status .lbl {{font-size:.8rem; color:#94A3B8; text-transform:uppercase; letter-spacing:.1em;}}
.hs-status .val {{font-size:2.2rem; font-weight:800; line-height:1.2;}}
.hs-status .sub {{color:#CBD5E1; margin-top:4px;}}

.hs-kpi {{background:#131C2E; border:1px solid #1E2A40; border-radius:14px; padding:14px 16px; height:100%;}}
.hs-kpi .k {{color:#94A3B8; font-size:.8rem;}}
.hs-kpi .v {{color:#F1F5F9; font-size:1.45rem; font-weight:700; margin-top:2px;}}
.hs-kpi .s {{font-size:.78rem; margin-top:2px;}}

.hs-parcel {{background:#0F1726; border:1px dashed #334155; border-radius:12px; padding:12px 14px;
  color:#CBD5E1; font-size:.9rem; margin:6px 0 12px;}}
.hs-banner {{border-radius:12px; padding:10px 14px; font-size:.9rem; margin-bottom:12px;
  background:rgba(245,158,11,.12); border:1px solid rgba(245,158,11,.4); color:#FCD34D;}}
.hs-foot {{color:#64748B; font-size:.8rem; text-align:center; margin-top:28px;}}

div.stButton > button, div.stDownloadButton > button {{border-radius:10px; font-weight:600;}}
@media (max-width: 900px) {{ .hs-steps {{grid-template-columns:1fr;}} }}
</style>
""",
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Ressources
# ---------------------------------------------------------------------------
@st.cache_resource(show_spinner=False)
def get_predictor():
    try:
        return HydroStressPredictor()
    except Exception as e:  # modèle absent ou illisible
        logger.exception("Chargement du modèle")
        return e


def get_pipeline() -> DataPipeline:
    """Non mis en cache : les jetons Earth Engine expirent."""
    return DataPipeline()


def init_state():
    for key, val in {"result": None, "parcel_key": None, "error": None}.items():
        st.session_state.setdefault(key, val)


init_state()


# ---------------------------------------------------------------------------
# Composants
# ---------------------------------------------------------------------------
def hero(predictor):
    meta = getattr(predictor, "metadata", None) or {}
    synthetic = meta.get("data_source") == "synthetic"
    chips = [
        "🛰️ Sentinel-2 · 10 m", "🌧️ CHIRPS · pluie quotidienne", "🌡️ ERA5-Land · T° & humidité",
        "🤖 Random Forest calibré", f"🌴 {len(OASES)} oasis",
    ]
    chips_html = "".join(f"<span class='hs-chip'>{c}</span>" for c in chips)
    if synthetic:
        chips_html += "<span class='hs-chip warn'>Modèle de démonstration (données synthétiques)</span>"
    st.markdown(
        f"""
<div class="hs-hero">
  <h1>💧 HydroStress <span>Errachidia</span></h1>
  <p>Suivi du stress hydrique des parcelles agricoles de la {REGION_NAME} (vallée du Ziz,
  Tafilalet, Ghéris, Boudnib), par télédétection et apprentissage automatique.
  Choisissez une zone, dessinez votre parcelle et obtenez un diagnostic avec des recommandations.</p>
  {chips_html}
</div>
<div class="hs-steps">
  <div class="hs-step"><b>ÉTAPE 1</b><div>Choisissez une oasis et dessinez la parcelle sur la carte satellite.</div></div>
  <div class="hs-step"><b>ÉTAPE 2</b><div>Indiquez la culture et la date, puis lancez l'analyse.</div></div>
  <div class="hs-step"><b>ÉTAPE 3</b><div>Lisez le rapport ci-dessous et téléchargez-le.</div></div>
</div>
""",
        unsafe_allow_html=True,
    )


def build_map(center, zoom):
    lon_min, lat_min, lon_max, lat_max = REGION_BBOX
    m = folium.Map(
        location=list(center), zoom_start=zoom, tiles=None, control_scale=True,
        min_lat=lat_min - 0.5, max_lat=lat_max + 0.5,
        min_lon=lon_min - 0.5, max_lon=lon_max + 0.5, max_bounds=True,
    )
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Esri World Imagery", name="Satellite",
    ).add_to(m)
    folium.TileLayer("OpenStreetMap", name="Plan").add_to(m)
    folium.Rectangle(
        bounds=[[lat_min, lon_min], [lat_max, lon_max]],
        color=ACCENT, weight=2, fill=False, dash_array="6",
        tooltip="Zone d'étude : province d'Errachidia",
    ).add_to(m)
    for name, (lat, lon) in OASES.items():
        folium.CircleMarker(location=[lat, lon], radius=5, color=ACCENT, fill=True,
                            fill_opacity=.9, tooltip=name).add_to(m)
    Draw(
        export=False,
        draw_options={
            "polyline": False, "circle": False, "circlemarker": False, "marker": False,
            "polygon": {"allowIntersection": False, "showArea": True,
                        "shapeOptions": {"color": "#F59E0B"}},
            "rectangle": {"showArea": True, "shapeOptions": {"color": "#F59E0B"}},
        },
        edit_options={"edit": False, "remove": True},
    ).add_to(m)
    folium.LayerControl(position="topright").add_to(m)
    return m


def kpi(label, value, sub="", color="#94A3B8"):
    st.markdown(
        f"<div class='hs-kpi'><div class='k'>{label}</div><div class='v'>{value}</div>"
        f"<div class='s' style='color:{color}'>{sub}</div></div>",
        unsafe_allow_html=True,
    )


STATUS_COLORS = {"healthy": "#22C55E", "low": "#EF4444", "high": "#F59E0B", "unknown": "#94A3B8"}


def plot_probabilities(probs):
    labels = ["Normal", "Modéré", "Sévère"]
    values = [probs["normal"], probs["moderate"], probs["severe"]]
    fig = go.Figure(go.Bar(
        x=values, y=labels, orientation="h",
        marker_color=["#22C55E", "#F59E0B", "#EF4444"],
        text=[f"{v:.1f} %" for v in values], textposition="outside", cliponaxis=False,
    ))
    fig.update_layout(
        template="plotly_dark", height=210, margin=dict(l=10, r=40, t=10, b=10),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(range=[0, 100], showgrid=False, visible=False), yaxis=dict(autorange="reversed"),
    )
    return fig


def plot_weather(chirps: pd.DataFrame, era5: pd.DataFrame):
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    if not chirps.empty:
        fig.add_trace(go.Bar(x=chirps["date"], y=chirps["precipitation_mm"], name="Pluie (mm)",
                             marker_color="#38BDF8", opacity=.8), secondary_y=False)
    if not era5.empty:
        fig.add_trace(go.Scatter(x=era5["date"], y=era5["temperature_max_c"], name="T° max",
                                 line=dict(color="#F97316", width=2)), secondary_y=True)
        fig.add_trace(go.Scatter(x=era5["date"], y=era5["temperature_c"], name="T° moyenne",
                                 line=dict(color="#FACC15", width=2, dash="dot")), secondary_y=True)
    fig.update_layout(
        template="plotly_dark", height=300, margin=dict(l=10, r=10, t=10, b=10),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", y=1.12, x=0), bargap=.25,
    )
    fig.update_yaxes(title_text="mm", secondary_y=False, showgrid=False)
    fig.update_yaxes(title_text="°C", secondary_y=True, gridcolor="#1E2A40")
    return fig


# ---------------------------------------------------------------------------
# Analyse
# ---------------------------------------------------------------------------
def run_analysis(predictor, coordinates, zone, crop, analysis_date, lookback, demo: bool):
    """Extraction + prédiction + rapport, résultat stocké dans la session."""
    st.session_state.error = None
    with st.status("Analyse de la parcelle en cours…", expanded=True) as status:
        try:
            st.write("Validation de la parcelle")
            poly = validate_geometry(coordinates)
            date_str = analysis_date.strftime("%Y-%m-%d")
            if demo:
                st.write("Génération des données de démonstration")
                data = make_demo_extraction(coordinates, date_str, lookback)
            else:
                st.write("Connexion à Google Earth Engine")
                pipeline = get_pipeline()
                st.write("Extraction Sentinel-2, CHIRPS et ERA5-Land (30 à 90 s)")
                data = pipeline.extract_all_data(coordinates, date_str, lookback)
            st.write("Prédiction du stress hydrique")
            prediction = predictor.predict(data["features"])
            if not demo:
                predictor.log_prediction(prediction)
            report = build_report(
                coordinates=coordinates, area_km2=polygon_area_km2(poly), zone=zone, crop=crop, data=data,
                prediction=prediction, recommendations=predictor.get_recommendations(prediction, crop),
                interpretation=predictor.interpret_indices(data["features"]), model_meta=predictor.metadata,
            )
            st.session_state.result = {"data": data, "report": report}
            status.update(label="Analyse terminée", state="complete", expanded=False)
        except (DataUnavailableError, ValueError) as e:
            st.session_state.error = str(e)
            status.update(label="Analyse impossible", state="error", expanded=False)
        except Exception as e:
            logger.exception("Erreur d'analyse")
            msg = str(e)
            if "earthengine" in msg.lower() or "credentials" in msg.lower() or "not found" in msg.lower():
                msg += (" — Vérifiez l'accès Earth Engine : secret GCP_SERVICE_ACCOUNT_JSON sur Streamlit Cloud "
                        "(voir README).")
            st.session_state.error = f"Erreur : {msg}"
            status.update(label="Analyse impossible", state="error", expanded=False)


def render_report(result):
    report, data = result["report"], result["data"]
    pred = report["prediction"]
    style = CLASS_STYLES[pred["class_index"]]
    interp = report["interpretation"]
    w = report["weather"]

    st.markdown("<div class='hs-section'>Rapport d'analyse</div>", unsafe_allow_html=True)
    if report["demo"]:
        st.markdown(
            "<div class='hs-banner'>⚠ Données de démonstration : ce rapport montre le fonctionnement du "
            "tableau de bord, les valeurs ne viennent pas des satellites pour cette parcelle.</div>",
            unsafe_allow_html=True,
        )

    c_status, c_prob = st.columns([1.1, 1], gap="large")
    with c_status:
        lat, lon = report["parcel"]["centroid"]
        st.markdown(
            f"""<div class="hs-status" style="border-left:8px solid {style['color']}">
<div class="lbl">Niveau de stress hydrique</div>
<div class="val" style="color:{style['color']}">{style['label']}</div>
<div class="sub">{style['summary']}</div>
<div class="sub" style="color:#94A3B8;margin-top:10px;font-size:.88rem">
Confiance {pred['confidence_percent']:.1f} % · {report['zone']} · {report['crop']} · {report['analysis_date']}<br>
Parcelle de {report['parcel']['area_ha']} ha · centre {lat}, {lon}</div></div>""",
            unsafe_allow_html=True,
        )
    with c_prob:
        st.markdown("<div class='hs-section'>Probabilités</div>", unsafe_allow_html=True)
        st.plotly_chart(plot_probabilities(pred["probabilities"]), width="stretch",
                        config={"displayModeBar": False})

    st.write("")
    cols = st.columns(6)
    tiles = [
        ("NDVI · vigueur", f"{interp['NDVI']['value']:.2f}", interp["NDVI"]["status"]),
        ("NDWI · eau foliaire", f"{interp['NDWI']['value']:.2f}", interp["NDWI"]["status"]),
        ("MSI · stress", f"{interp['MSI']['value']:.2f}", interp["MSI"]["status"]),
        ("Pluie 30 jours", f"{w['precipitation_30d_mm']} mm", None),
        ("T° max 30 jours", f"{w['temperature_max_c']} °C", None),
        ("Jours secs consécutifs", f"{w['dry_days_max']}", None),
    ]
    for col, (label, value, status) in zip(cols, tiles):
        with col:
            if status:
                kpi(label, value, f"● {STATUS_LABELS[status]}", STATUS_COLORS[status])
            else:
                kpi(label, value, "&nbsp;")

    meta = report["sentinel_meta"]
    if meta:
        st.caption(
            f"Composite Sentinel-2 de {meta['image_count']} image(s) sur {meta['window_days']} jours · "
            f"{meta['valid_pixel_fraction']:.0%} de pixels valides (hors nuages)."
        )

    c_weather, c_reco = st.columns([1.4, 1], gap="large")
    with c_weather:
        st.markdown("<div class='hs-section'>Météo de la période</div>", unsafe_allow_html=True)
        st.plotly_chart(plot_weather(data["chirps_series"], data["era5_series"]), width="stretch",
                        config={"displayModeBar": False})
    with c_reco:
        rec = report["recommendations"]
        st.markdown(f"<div class='hs-section'>Recommandations · priorité {rec['priority'].upper()}</div>",
                    unsafe_allow_html=True)
        with st.container(border=True):
            st.markdown(f"**{rec['title']}**")
            for action in rec["actions"]:
                st.markdown(f"- {action}")

    c_idx, c_dl = st.columns([1.4, 1], gap="large")
    with c_idx:
        st.markdown("<div class='hs-section'>Indices spectraux</div>", unsafe_allow_html=True)
        table = pd.DataFrame([
            {"Indice": k, "Valeur": v["value"], "Référence": f"{v['healthy_range'][0]} – {v['healthy_range'][1]}",
             "État": STATUS_LABELS[v["status"]], "Description": v["description"]}
            for k, v in interp.items()
        ])
        st.dataframe(table, hide_index=True, width="stretch")
    with c_dl:
        st.markdown("<div class='hs-section'>Exporter</div>", unsafe_allow_html=True)
        st.download_button(
            "⬇️ Télécharger le rapport (HTML)", data=report_to_html(report),
            file_name=f"rapport_hydrostress_{report['analysis_date']}.html", mime="text/html",
            type="primary", width="stretch",
        )
        st.download_button(
            "⬇️ Données de l'analyse (JSON)",
            data=json.dumps({"report": report, "features": data["features"]}, ensure_ascii=False,
                            indent=2, default=str),
            file_name=f"hydrostress_{report['analysis_date']}.json", mime="application/json",
            width="stretch",
        )
        st.caption("Le rapport HTML s'ouvre dans le navigateur et s'imprime en PDF (Ctrl+P).")


# ---------------------------------------------------------------------------
# Bas de page : modèle et simulation
# ---------------------------------------------------------------------------
def render_model_section(predictor):
    meta = predictor.metadata or {}
    metrics = meta.get("test_metrics") or {}
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        kpi("Source des données", {"synthetic": "Synthétiques"}.get(meta.get("data_source"), meta.get("data_source", "—")))
    with c2:
        kpi("Échantillons", meta.get("training_samples", "—"))
    with c3:
        kpi("Accuracy (test)", f"{metrics['accuracy']:.0%}" if metrics else "—")
    with c4:
        kpi("Entraîné le", (meta.get("created_at") or "—")[:10])
    if meta.get("data_source") == "synthetic":
        st.caption(
            "Le modèle actuel est entraîné sur des données synthétiques calées sur le climat d'Errachidia. "
            "Il sera remplacé par un modèle entraîné sur des données réelles (build_dataset.py)."
        )


def render_simulation(predictor):
    month = datetime.now().month - 1
    c1, c2, c3 = st.columns(3)
    with c1:
        ndvi = st.slider("NDVI", -0.1, 0.9, 0.45, 0.01, key="sim_ndvi")
        ndwi = st.slider("NDWI", -0.4, 0.6, 0.15, 0.01, key="sim_ndwi")
        msi = st.slider("MSI", 0.2, 2.5, 0.75, 0.01, key="sim_msi")
    with c2:
        precip_30j = st.slider("Pluie 30 jours (mm)", 0.0, 150.0, float(MONTHLY_PRECIP_MM[month]), 1.0, key="sim_p")
        dry_days = st.slider("Jours secs consécutifs", 0, 30, 20, 1, key="sim_dry")
        crop = st.selectbox("Culture", CROPS, key="sim_crop")
    with c3:
        temp_mean = st.slider("T° moyenne (°C)", -5.0, 45.0, float(MONTHLY_TEMP_MEAN_C[month]), 0.5, key="sim_t")
        temp_max = st.slider("T° max (°C)", 0.0, 52.0, float(MONTHLY_TEMP_MEAN_C[month] + 11), 0.5, key="sim_tmax")
        humidity = st.slider("Humidité moyenne (%)", 0.0, 100.0, float(MONTHLY_RH_MEAN[month]), 1.0, key="sim_rh")

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
    }
    pred = predictor.predict(data)
    style = CLASS_STYLES[pred["class_index"]]
    rec = predictor.get_recommendations(pred, crop)
    c_res, c_rec = st.columns([1, 1.4], gap="large")
    with c_res:
        st.markdown(
            f"<div class='hs-status' style='border-left:8px solid {style['color']}'>"
            f"<div class='lbl'>Résultat simulé</div><div class='val' style='color:{style['color']}'>"
            f"{style['label']}</div><div class='sub'>Confiance {pred['confidence_percent']:.1f} %</div></div>",
            unsafe_allow_html=True,
        )
    with c_rec:
        for action in rec["actions"][:3]:
            st.markdown(f"- {action}")


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------
def main():
    predictor = get_predictor()
    if isinstance(predictor, Exception):
        st.error(f"Le modèle de prédiction n'a pas pu être chargé : {predictor}")
        st.info("Entraînez un modèle : `python train_model.py training_data.csv --source synthetic`")
        return

    hero(predictor)

    col_map, col_panel = st.columns([1.65, 1], gap="large")

    with col_panel:
        st.markdown("<div class='hs-section'>Zone et paramètres</div>", unsafe_allow_html=True)
        zone = st.selectbox("Zone", ["Toute la province"] + list(OASES.keys()), index=0)
        crop = st.selectbox("Culture de la parcelle", CROPS)
        c_date, c_win = st.columns(2)
        with c_date:
            analysis_date = st.date_input(
                "Date d'analyse", value=datetime.now() - timedelta(days=10),
                min_value=datetime(2017, 4, 1), max_value=datetime.now() - timedelta(days=5),
                help="ERA5-Land et CHIRPS sont publiés avec environ une semaine de retard.",
            )
        with c_win:
            lookback = st.select_slider("Fenêtre satellite", options=[15, 20, 30, 45, 60], value=30,
                                        format_func=lambda d: f"{d} jours",
                                        help="Période du composite Sentinel-2 sans nuages.")

    center, zoom = (MAP_CENTER, MAP_ZOOM) if zone == "Toute la province" else (OASES[zone], 14)

    with col_map:
        st.markdown("<div class='hs-section'>Carte · dessinez votre parcelle</div>", unsafe_allow_html=True)
        map_data = st_folium(
            build_map(center, zoom), height=560, use_container_width=True,
            returned_objects=["last_active_drawing"], key=f"map_{zone}",
        )

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
                st.markdown(
                    f"<div class='hs-parcel'>✅ <b>Parcelle prête</b> · {area_ha:.2f} ha · "
                    f"{len(coordinates) - 1} sommets<br>Centre : {c.y:.4f}, {c.x:.4f}</div>",
                    unsafe_allow_html=True,
                )
            except ValueError as e:
                parcel_error = str(e)
                st.markdown(f"<div class='hs-banner'>❌ {parcel_error}</div>", unsafe_allow_html=True)
        else:
            st.markdown(
                "<div class='hs-parcel'>✏️ Utilisez l'outil <b>rectangle</b> ou <b>polygone</b> de la carte "
                "pour dessiner votre parcelle (≤ 10 km², dans la province).</div>",
                unsafe_allow_html=True,
            )

        ready = coordinates is not None and parcel_error is None
        analyse = st.button("🔍 Analyser la parcelle", type="primary", width="stretch", disabled=not ready)
        demo = st.button("Voir un exemple (données de démonstration)", width="stretch", disabled=not ready)

        parcel_key = json.dumps([coordinates, str(analysis_date), crop, lookback]) if coordinates else None
        if parcel_key != st.session_state.parcel_key:
            st.session_state.result = None
            st.session_state.error = None
            st.session_state.parcel_key = parcel_key

        if analyse or demo:
            run_analysis(predictor, coordinates, zone, crop, analysis_date, lookback, demo=demo)
        if st.session_state.error:
            st.error(st.session_state.error)

    if st.session_state.result:
        st.divider()
        render_report(st.session_state.result)

    st.divider()
    with st.expander("🤖 À propos du modèle"):
        render_model_section(predictor)
    with st.expander("🎛️ Simulation manuelle (sans satellite)"):
        render_simulation(predictor)

    st.markdown(
        "<div class='hs-foot'>HydroStress Errachidia · Données : Copernicus Sentinel-2, CHIRPS (UCSB-CHG), "
        "ERA5-Land (ECMWF) via Google Earth Engine · Prototype de recherche, résultats indicatifs</div>",
        unsafe_allow_html=True,
    )


main()
