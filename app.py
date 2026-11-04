"""
app.py
======
Interface Streamlit pour HydroStressPrototype.

Fonctionnalités :
- Carte interactive Folium avec dessin de parcelles et validation de taille
- Extraction de données satellites et météorologiques réelles
- Prédiction du stress hydrique avec probabilités calibrées
- Visualisations professionnelles (Plotly)
- Gestion d'état Streamlit robuste
- CSS personnalisé intégré
"""

import streamlit as st
import folium
from folium.plugins import Draw
from streamlit_folium import st_folium
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import logging
from pathlib import Path
import json

# Import des modules du projet
from extract_data import DataPipeline, DataUnavailableError, day_of_year_cyclic, validate_geometry
from predict import HydroStressPredictor
from region import (
    CROPS, MAP_CENTER, MAP_ZOOM, MONTHLY_PRECIP_MM, MONTHLY_RH_MEAN, MONTHLY_TEMP_MEAN_C,
    OASES, REGION_BBOX, REGION_NAME,
)

# ---------------------------------------------------------------------------
# Configuration Streamlit (DOIT être la première commande st)
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="HydroStress Prototype",
    page_icon="💧",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# CSS personnalisé
# ---------------------------------------------------------------------------
_CUSTOM_CSS = """
<style>

/* ===========================
   Fond général
=========================== */
.main {
    background-color: #F8FAFC;
}

/* ===========================
   Titres
=========================== */
h1 {
    color: #1E3A8A;
    font-weight:700;
}

h2, h3 {
    color:#0F172A;
    font-weight:600;
}

/* ===========================
   Cartes
=========================== */
.metric-card{
    background:#FFFFFF;
    border-radius:18px;
    padding:22px;
    border-left:6px solid #2563EB;
    box-shadow:0 4px 18px rgba(0,0,0,.08);
    transition:all .25s ease;
    margin-bottom:15px;
}

.metric-card:hover{
    transform:translateY(-4px);
    box-shadow:0 10px 28px rgba(0,0,0,.15);
}

/* ===========================
   Valeur
=========================== */
.metric-value{
    font-size:34px;
    font-weight:bold;
    color:#2563EB;
    margin-top:8px;
}

/* ===========================
   Nom
=========================== */
.metric-label{
    color:#64748B;
    font-size:15px;
}

/* ===========================
   Alertes
=========================== */

.alert-box{
    border-radius:15px;
    padding:18px;
    margin:15px 0;
    font-size:17px;
    font-weight:500;
}

.alert-success{
    background:#DCFCE7;
    color:#166534;
    border-left:8px solid #22C55E;
}

.alert-warning{
    background:#FEF3C7;
    color:#92400E;
    border-left:8px solid #F59E0B;
}

.alert-critical{
    background:#FEE2E2;
    color:#991B1B;
    border-left:8px solid #EF4444;
}

/* ===========================
   Boutons
=========================== */

.stButton>button{
    background:#2563EB;
    color:white;
    border:none;
    border-radius:12px;
    padding:0.6rem 1.5rem;
    font-weight:600;
}

.stButton>button:hover{
    background:#1D4ED8;
}

/* ===========================
   Sidebar
=========================== */

section[data-testid="stSidebar"]{
    background:#1E293B;
}

section[data-testid="stSidebar"] *{
    color:white;
}

/* Listes déroulantes de la sidebar : texte sombre sur fond clair */
section[data-testid="stSidebar"] [data-baseweb="select"] *,
section[data-testid="stSidebar"] [data-testid="stSelectbox"] input,
section[data-testid="stSidebar"] [data-testid="stSelectbox"] svg{
    color:#0F172A;
    -webkit-text-fill-color:#0F172A;
}

/* ===========================
   Métriques Streamlit
=========================== */

[data-testid="metric-container"]{
    border-radius:15px;
    background:white;
    padding:15px;
    box-shadow:0 4px 15px rgba(0,0,0,.08);
}

</style>
"""
st.markdown(_CUSTOM_CSS, unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Initialisation de l'état de session
# ---------------------------------------------------------------------------
def init_session_state():
    """Initialise les clés de session_state si absentes."""
    defaults = {
        "extracted_data": None,
        "prediction_result": None,
        "last_error": None,
        "pipeline_initialized": False,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val

init_session_state()

# ---------------------------------------------------------------------------
# Initialisation paresseuse du pipeline (SANS cache)
# ---------------------------------------------------------------------------
@st.cache_resource(show_spinner=False)
def get_predictor() -> HydroStressPredictor:
    """Charge le prédicteur (cachable car stateless après chargement)."""
    try:
        return HydroStressPredictor()
    except Exception as e:
        st.error(f"Erreur chargement du modèle : {e}")
        return None


def get_pipeline() -> DataPipeline:
    """
    Initialise le pipeline de données Earth Engine.

    Note : NON mis en cache car Earth Engine utilise des tokens qui expirent
    et des connexions réseau actives.
    """
    try:
        return DataPipeline()
    except Exception as e:
        st.error(f"Erreur connexion Earth Engine : {e}")
        st.info(
            "Configurez l'accès Earth Engine : sur Streamlit Cloud, ajoutez le secret "
            "`GCP_SERVICE_ACCOUNT_JSON` (contenu du fichier JSON du compte de service). "
            "Voir la section « Authentification Earth Engine » du README."
        )
        return None


# ---------------------------------------------------------------------------
# Composants d'affichage
# ---------------------------------------------------------------------------
def create_map(center: tuple, zoom: int) -> tuple:
    """
    Crée la carte Folium interactive avec outil de dessin, limitée à la
    province d'Errachidia.

    Returns:
        tuple: (map_data, coordinates_list ou None)
    """
    st.subheader("🗺️ Délimitation de la parcelle")
    st.caption(
        f"Dessinez un polygone ou un rectangle dans la zone d'étude ({REGION_NAME}). "
        "Surface max : 10 km²."
    )

    lon_min, lat_min, lon_max, lat_max = REGION_BBOX
    m = folium.Map(
        location=list(center), zoom_start=zoom, tiles=None,
        min_lat=lat_min - 0.5, max_lat=lat_max + 0.5,
        min_lon=lon_min - 0.5, max_lon=lon_max + 0.5, max_bounds=True,
    )
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Esri World Imagery", name="Satellite",
    ).add_to(m)
    folium.TileLayer("OpenStreetMap", name="OpenStreetMap").add_to(m)
    folium.Rectangle(
        bounds=[[lat_min, lon_min], [lat_max, lon_max]],
        color="#2563EB", weight=2, fill=False, tooltip="Zone d'étude : province d'Errachidia",
    ).add_to(m)
    for name, (lat, lon) in OASES.items():
        folium.CircleMarker(
            location=[lat, lon], radius=4, color="#16a34a", fill=True, tooltip=name,
        ).add_to(m)
    folium.LayerControl().add_to(m)

    Draw(
        export=False,
        draw_options={
            "polyline": False,
            "polygon": {"allowIntersection": False, "showArea": True},
            "rectangle": {"showArea": True},
            "circle": False,
            "circlemarker": False,
            "marker": False,
        },
        edit_options={"edit": False, "remove": True},
    ).add_to(m)

    map_data = st_folium(m, width=700, height=500, returned_objects=["last_active_drawing"])

    coordinates = None
    if map_data and map_data.get("last_active_drawing"):
        geom = map_data["last_active_drawing"]["geometry"]
        if geom["type"] == "Polygon":
            coordinates = geom["coordinates"][0]  # Premier anneau (extérieur)

    return map_data, coordinates


def display_spectral_cards(sentinel_stats: dict):
    """Affiche les indices spectraux sous forme de cartes métriques."""
    st.subheader("📈 Indices Spectraux")

    def card(label: str, value: float, unit: str = "", color_thresholds: tuple = None):
        if color_thresholds:
            low, high = color_thresholds
            if value < low:
                emoji = "🔴"
            elif value > high:
                emoji = "🟡"
            else:
                emoji = "🟢"
        else:
            emoji = ""
        st.markdown(f"""
        <div class="metric-card">
            <div style="font-size:1.1rem;font-weight:600;">{label}</div>
            <div class="metric-value">{value:.3f} {unit}</div>
            <div class="metric-label">{emoji}</div>
        </div>
        """, unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)
    with c1:
        v = sentinel_stats.get("NDVI", {}).get("mean", 0)
        card("NDVI", v, color_thresholds=(0.3, 0.8))
    with c2:
        v = sentinel_stats.get("NDWI", {}).get("mean", 0)
        card("NDWI", v, color_thresholds=(0.2, 0.7))
    with c3:
        v = sentinel_stats.get("MSI", {}).get("mean", 0)
        card("MSI", v, color_thresholds=(0.0, 1.2))

    c1, c2 = st.columns(2)
    with c1:
        v = sentinel_stats.get("SAVI", {}).get("mean", 0)
        card("SAVI", v, color_thresholds=(0.2, 0.7))
    with c2:
        v = sentinel_stats.get("EVI", {}).get("mean", 0)
        card("EVI", v, color_thresholds=(0.2, 0.6))


def display_weather_charts(chirps_df: pd.DataFrame, era5_df: pd.DataFrame):
    """Affiche les graphiques météorologiques interactifs."""
    st.subheader("🌦️ Données Météorologiques")

    if not chirps_df.empty:
        fig = px.bar(
            chirps_df, x="date", y="precipitation_mm",
            title="Précipitations quotidiennes (mm)",
            labels={"precipitation_mm": "Précipitation (mm)", "date": "Date"},
            color_discrete_sequence=["#3b82f6"],
        )
        fig.update_layout(height=350)
        st.plotly_chart(fig, width="stretch")

    if not era5_df.empty:
        fig2 = px.line(
            era5_df, x="date", y=["temperature_c", "humidity_percent"],
            title="Température et humidité relative",
            labels={"value": "Valeur", "date": "Date", "variable": "Mesure"},
        )
        fig2.update_layout(height=350)
        st.plotly_chart(fig2, width="stretch")

    # Résumé métriques
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        total = chirps_df["precipitation_mm"].sum() if not chirps_df.empty else 0
        st.metric("Précipitations totales", f"{total:.1f} mm")
    with c2:
        avg_t = era5_df["temperature_c"].mean() if not era5_df.empty else 0
        st.metric("Température moy.", f"{avg_t:.1f} °C")
    with c3:
        max_t = era5_df["temperature_c"].max() if not era5_df.empty else 0
        st.metric("Température max.", f"{max_t:.1f} °C")
    with c4:
        avg_h = era5_df["humidity_percent"].mean() if not era5_df.empty else 0
        st.metric("Humidité moy.", f"{avg_h:.1f} %")


def display_prediction(prediction: dict):
    """Affiche le résultat de prédiction avec alerte colorée et graphique."""
    st.subheader("🎯 Résultat de Prédiction")

    class_idx = prediction["class_index"]
    conf = prediction["confidence_percent"]
    probs = prediction["probabilities"]

    # Alerte
    if class_idx == 0:
        css_class = "alert-success"
        icon = "✅"
        title = "Stress hydrique NORMAL"
    elif class_idx == 1:
        css_class = "alert-warning"
        icon = "⚠️"
        title = "Stress hydrique MODÉRÉ"
    else:
        css_class = "alert-critical"
        icon = "🔴"
        title = "Stress hydrique SÉVÈRE"

    st.markdown(f"""
    <div class="alert-box {css_class}">
        <strong>{icon} {title}</strong><br>
        Confiance : <b>{conf:.1f} %</b><br>
        ID : {prediction.get("prediction_id", "N/A")}
    </div>
    """, unsafe_allow_html=True)

    # Graphique des probabilités
    col1, col2 = st.columns([2, 1])
    with col1:
        fig = go.Figure(data=[
            go.Bar(
                x=["Normal", "Modéré", "Sévère"],
                y=[probs["normal"], probs["moderate"], probs["severe"]],
                marker_color=["#22c55e", "#f59e0b", "#ef4444"],
                text=[f"{probs['normal']:.1f}%", f"{probs['moderate']:.1f}%", f"{probs['severe']:.1f}%"],
                textposition="auto",
            )
        ])
        fig.update_layout(
            title="Distribution des probabilités calibrées",
            yaxis_title="Probabilité (%)",
            height=320,
            showlegend=False,
        )
        st.plotly_chart(fig, width="stretch")

    with col2:
        st.metric("Classe prédite", prediction["class_name"])
        st.metric("Confiance", f"{conf:.1f} %")
        st.metric("Probabilité dominante", f"{max(probs.values()):.1f} %")


def display_recommendations(prediction: dict, predictor: HydroStressPredictor, crop: str = None):
    """Affiche les recommandations agronomiques structurées."""
    rec = predictor.get_recommendations(prediction, crop)

    st.subheader("💡 Recommandations Agronomiques")

    priority_colors = {"low": "green", "medium": "orange", "high": "red"}
    color = priority_colors.get(rec["priority"], "gray")

    st.markdown(f"**Priorité :** :{color}[{rec['priority'].upper()}]")
    st.markdown(f"**{rec['title']}**")

    for action in rec["actions"]:
        st.markdown(f"- {action}")


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------
def page_home():
    """Page d'accueil et documentation."""
    st.title("💧 HydroStress — Errachidia")
    st.markdown(f"**Suivi du stress hydrique des cultures dans la {REGION_NAME}**")

    st.markdown("""
    ### 🚀 À propos

    L'application est dédiée aux oasis de la province d'Errachidia : vallée du Ziz,
    Tafilalet (Erfoud, Rissani), Ghéris (Goulmima, Tinejdad) et Boudnib.
    Elle combine :

    - **🛰️ Sentinel-2** : composite sans nuages des indices NDVI, NDWI, MSI, SAVI, EVI (10 m)
    - **🌧️ CHIRPS** : précipitations quotidiennes (~5 km)
    - **🌡️ ERA5-Land** : températures min / moy / max et humidité relative (~9 km)
    - **🤖 Random Forest calibré** : classification Normal / Modéré / Sévère
    - **🌴 Recommandations** adaptées aux cultures locales (palmier dattier, luzerne, céréales, olivier)

    ### 📋 Workflow
    1. Ouvrez **📊 Analyse** et choisissez une oasis dans la barre latérale
    2. Dessinez votre parcelle sur la carte (vue satellite)
    3. Choisissez la date d'analyse et la culture
    4. Lancez l'extraction puis la prédiction

    ### ⚠️ Prérequis
    - Accès Google Earth Engine (compte de service ou `earthengine authenticate`, voir README)
    - Modèle entraîné dans `models/` (`python train_model.py <dataset.csv>`)
    """)

    predictor = get_predictor()
    if predictor is not None and (predictor.metadata or {}).get("data_source") == "synthetic":
        st.warning(
            "Le modèle fourni est entraîné sur des données **synthétiques** calées sur le climat "
            "d'Errachidia. Ses prédictions sont illustratives tant qu'il n'est pas réentraîné "
            "sur des données réelles (`build_dataset.py` ou relevés terrain)."
        )

    c1, c2, c3 = st.columns(3)
    with c1:
        st.info(f"🌴 {len(OASES)} oasis pré-configurées")
    with c2:
        st.warning("🤖 Random Forest + Calibration")
    with c3:
        st.success("📍 Résolution 10 m (Sentinel-2)")


def page_analysis():
    """Page d'analyse de parcelle avec extraction de données et prédiction."""
    st.header("📊 Analyse de Parcelle")

    predictor = get_predictor()
    if predictor is None:
        st.error("❌ Le modèle de prédiction n'est pas disponible. Entraînez d'abord un modèle.")
        st.info("Exécutez : `python train_model.py` avec votre dataset d'entraînement.")
        return

    # Choix de la zone dans la barre latérale
    with st.sidebar:
        st.divider()
        zone = st.selectbox("🌴 Centrer la carte sur", ["Vue d'ensemble"] + list(OASES.keys()))
        crop = st.selectbox("🌱 Culture de la parcelle", CROPS)
    center, zoom = (MAP_CENTER, MAP_ZOOM) if zone == "Vue d'ensemble" else (OASES[zone], 14)

    # Carte interactive
    _, coordinates = create_map(center, zoom)

    if coordinates:
        try:
            validate_geometry(coordinates)
        except ValueError as e:
            st.error(f"❌ {e}")
            return
        st.success(f"✅ Parcelle définie : {len(coordinates) - 1} sommets")
        # Affiche un aperçu des coordonnées
        with st.expander("Voir les coordonnées"):
            st.json(coordinates[:5] + [["..."]])  # Aperçu tronqué
    else:
        st.info("🖱️ Dessinez une parcelle sur la carte pour commencer.")
        return

    # Configuration de l'analyse
    col1, col2 = st.columns(2)
    with col1:
        analysis_date = st.date_input(
            "Date d'analyse",
            value=datetime.now() - timedelta(days=10),  # ERA5-Land et CHIRPS sont publiés avec ~1 semaine de délai
            min_value=datetime(2017, 1, 1),
            max_value=datetime.now(),
        )
    with col2:
        lookback = st.slider(
            "Fenêtre du composite Sentinel-2 (jours)", 10, 60, 30,
            help="Les features météo du modèle portent toujours sur les 30 derniers jours.",
        )

    # Bouton d'extraction
    if st.button("🔍 Extraire les données satellites et météo", type="primary"):
        progress = st.progress(0, text="Initialisation...")

        try:
            # Validation de la géométrie
            progress.progress(10, text="Validation de la géométrie...")
            validate_geometry(coordinates)

            # Initialisation du pipeline (sans cache)
            progress.progress(25, text="Connexion à Earth Engine...")
            pipeline = get_pipeline()
            if pipeline is None:
                st.error("Impossible de se connecter à Earth Engine.")
                return

            # Extraction
            progress.progress(40, text="Extraction Sentinel-2...")
            data = pipeline.extract_all_data(
                coordinates=coordinates,
                analysis_date=analysis_date.strftime("%Y-%m-%d"),
                lookback_days=lookback,
            )

            progress.progress(80, text="Agrégation des features...")
            st.session_state.extracted_data = data
            st.session_state.last_error = None
            progress.progress(100, text="Extraction terminée !")
            st.success("✅ Données extraites avec succès")

        except (DataUnavailableError, ValueError) as e:
            st.session_state.last_error = str(e)
            st.warning(f"⚠️ {e}")
            return
        except Exception as e:
            st.session_state.last_error = str(e)
            st.error(f"Erreur lors de l'extraction : {e}")
            logger.exception("Erreur extraction")
            return

    # Affichage des données extraites
    if st.session_state.extracted_data is not None:
        data = st.session_state.extracted_data

        # Onglets pour organiser l'affichage
        tab1, tab2, tab3 = st.tabs(["🛰️ Satellites", "🌦️ Météo", "🎯 Prédiction"])

        with tab1:
            if "sentinel_stats" in data:
                meta = data.get("sentinel_meta", {})
                if meta:
                    st.caption(
                        f"Composite médian de {meta['image_count']} image(s) sur {meta['window_days']} jours — "
                        f"{meta['valid_pixel_fraction']:.0%} de pixels valides (hors nuages)."
                    )
                display_spectral_cards(data["sentinel_stats"])

        with tab2:
            chirps = data.get("chirps_series", pd.DataFrame())
            era5 = data.get("era5_series", pd.DataFrame())
            if not chirps.empty or not era5.empty:
                display_weather_charts(chirps, era5)
            else:
                st.warning("Données météorologiques non disponibles.")

        with tab3:
            if st.button("🎯 Lancer la prédiction", type="primary"):
                with st.spinner("Analyse en cours..."):
                    try:
                        features = data["features"]
                        prediction = predictor.predict(features)
                        st.session_state.prediction_result = prediction

                        # Traçabilité
                        predictor.log_prediction(prediction)

                    except Exception as e:
                        st.error(f"Erreur de prédiction : {e}")
                        logger.exception("Erreur prédiction")

            if st.session_state.prediction_result is not None:
                pred = st.session_state.prediction_result
                display_prediction(pred)
                display_recommendations(pred, predictor, crop)

                # Interprétation des indices
                with st.expander("🔬 Interprétation détaillée des indices"):
                    interp = predictor.interpret_indices(data["features"])
                    for idx_name, info in interp.items():
                        status_emoji = {"healthy": "🟢", "low": "🔴", "high": "🟡", "unknown": "⚪"}
                        st.write(f"**{idx_name}** : {info['value']} {status_emoji.get(info['status'], '')} — {info['description']}")


def page_quick_predict():
    """Page de prédiction rapide avec sliders manuels."""
    st.header("🔮 Prédiction Rapide")
    st.markdown("Entrez manuellement les valeurs des indices pour une prédiction instantanée.")

    predictor = get_predictor()
    if predictor is None:
        st.error("Modèle non disponible.")
        return

    c_date, c_crop = st.columns(2)
    with c_date:
        ref_date = st.date_input("Date de référence", value=datetime.now())
    with c_crop:
        crop = st.selectbox("Culture", CROPS)
    month = ref_date.month - 1
    st.caption(
        f"Valeurs par défaut : normales approximatives d'Errachidia pour ce mois "
        f"({MONTHLY_TEMP_MEAN_C[month]:.0f} °C, {MONTHLY_PRECIP_MM[month]:.0f} mm, {MONTHLY_RH_MEAN[month]} % HR)."
    )

    col1, col2, col3 = st.columns(3)

    with col1:
        st.subheader("🌿 Végétation")
        ndvi = st.slider("NDVI (moyenne)", -0.1, 0.9, 0.45, 0.01)
        ndwi = st.slider("NDWI (moyenne)", -0.4, 0.6, 0.15, 0.01)
        savi = st.slider("SAVI (moyenne)", -0.1, 0.9, 0.32, 0.01)
        evi = st.slider("EVI (moyenne)", -0.1, 0.9, 0.28, 0.01)

    with col2:
        st.subheader("💧 Eau & Stress")
        msi = st.slider("MSI (moyenne)", 0.2, 2.5, 0.75, 0.01)
        precip_30j = st.slider("Précipitations 30j (mm)", 0.0, 150.0, float(MONTHLY_PRECIP_MM[month]), 1.0)
        precip_7j = st.slider("Précipitations 7j (mm)", 0.0, 80.0, float(round(MONTHLY_PRECIP_MM[month] / 4)), 1.0)
        dry_days = st.slider("Jours secs consécutifs max", 0, 30, 20, 1)
        rainy_days = st.slider("Jours de pluie (30j)", 0, 15, 2, 1)

    with col3:
        st.subheader("🌡️ Climat")
        temp_mean = st.slider("Température moy. (°C)", -5.0, 45.0, float(MONTHLY_TEMP_MEAN_C[month]), 0.5)
        temp_max = st.slider("Température max. (°C)", 0.0, 52.0, float(MONTHLY_TEMP_MEAN_C[month] + 11), 0.5)
        temp_min = st.slider("Température min. (°C)", -10.0, 35.0, float(MONTHLY_TEMP_MEAN_C[month] - 10), 0.5)
        humidity = st.slider("Humidité moy. (%)", 0.0, 100.0, float(MONTHLY_RH_MEAN[month]), 1.0)

    sin_doy, cos_doy = day_of_year_cyclic(datetime.combine(ref_date, datetime.min.time()))

    # Valeurs dérivées (min/max/std cohérents)
    data = {
        "NDVI_mean": ndvi,
        "NDVI_min": max(ndvi - 0.15, -0.1),
        "NDVI_max": min(ndvi + 0.15, 0.95),
        "NDVI_std": 0.08,
        "NDWI_mean": ndwi,
        "NDWI_std": 0.06,
        "MSI_mean": msi,
        "MSI_min": max(msi - 0.25, 0.1),
        "MSI_max": msi + 0.25,
        "MSI_std": 0.12,
        "SAVI_mean": savi,
        "EVI_mean": evi,
        "precipitation_total_30j": precip_30j,
        "precipitation_total_7j": min(precip_7j, precip_30j),
        "precipitation_mean": precip_30j / 30.0,
        "max_consecutive_dry_days": float(dry_days),
        "rainy_days_count": float(rainy_days),
        "temperature_mean": temp_mean,
        "temperature_max": temp_max,
        "temperature_min": temp_min,
        "humidity_mean": humidity,
        "humidity_min": max(humidity - 18.0, 3.0),
        "day_of_year_sin": sin_doy,
        "day_of_year_cos": cos_doy,
    }

    if st.button("🎯 Prédire", type="primary"):
        prediction = predictor.predict(data)
        display_prediction(prediction)
        display_recommendations(prediction, predictor, crop)


def page_dashboard():
    """Page de tableau de bord avec métriques du modèle."""
    st.header("📈 Dashboard du Modèle")

    predictor = get_predictor()
    if predictor is None or predictor.metadata is None:
        st.warning("Aucun modèle chargé. Les métriques ne sont pas disponibles.")
        return

    meta = predictor.metadata

    st.subheader("🔧 Métadonnées du modèle")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Features", meta.get("feature_count", "N/A"))
    with c2:
        st.metric("Échantillons d'entraînement", meta.get("training_samples", "N/A"))
    with c3:
        st.metric("Date d'entraînement", meta.get("created_at", "N/A")[:10] if meta.get("created_at") else "N/A")
    with c4:
        best = meta.get("best_params", {})
        n_est = best.get("rf__n_estimators", "N/A") if isinstance(best, dict) else "N/A"
        st.metric("Arbres RF", n_est)

    source = meta.get("data_source", "inconnue")
    if source == "synthetic":
        st.warning(
            "Données d'entraînement **synthétiques** (calées sur le climat d'Errachidia). "
            "Les métriques ci-dessous mesurent la cohérence du pipeline, pas la justesse sur le terrain."
        )
    else:
        st.caption(f"Source des données d'entraînement : {source}")

    metrics = meta.get("test_metrics")
    if metrics:
        st.subheader(f"🧪 Performance sur le jeu de test ({metrics['samples']} échantillons)")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Accuracy", f"{metrics['accuracy']:.1%}")
        m2.metric("F1 pondéré", f"{metrics['f1_weighted']:.1%}")
        m3.metric("Rappel pondéré", f"{metrics['recall_weighted']:.1%}")
        auc = metrics.get("roc_auc_ovr_weighted")
        m4.metric("ROC-AUC", f"{auc:.3f}" if auc is not None else "N/A")

        labels = ["Normal", "Modéré", "Sévère"]
        fig = px.imshow(
            metrics["confusion_matrix"], x=labels, y=labels, text_auto=True,
            color_continuous_scale="Blues",
            labels={"x": "Classe prédite", "y": "Classe réelle", "color": "Nombre"},
            title="Matrice de confusion",
        )
        fig.update_layout(height=380)
        st.plotly_chart(fig, width="stretch")

        per_class = pd.DataFrame(metrics["per_class"]).T.map(lambda v: f"{v:.1%}")
        st.dataframe(per_class, width="stretch")

    # Paramètres optimaux
    if meta.get("best_params"):
        st.subheader("⚙️ Hyperparamètres optimaux")
        st.json(meta["best_params"])

    # Liste des features
    with st.expander("📋 Liste des features utilisées"):
        for i, feat in enumerate(meta.get("feature_columns", []), 1):
            st.write(f"{i}. `{feat}`")

    # Logs de prédictions
    log_path = Path("predictions_log.jsonl")
    if log_path.exists():
        st.subheader("📜 Historique des prédictions")
        lines = log_path.read_text(encoding="utf-8").strip().split("\n")
        if lines and lines[0]:
            preds = [json.loads(line) for line in lines[-20:]]  # 20 dernières
            df_log = pd.DataFrame([
                {
                    "Date": p["timestamp"][:19],
                    "Classe": p["class_name"],
                    "Confiance": f"{p['confidence_percent']:.1f}%",
                    "Normal": f"{p['probabilities']['normal']:.1f}%",
                    "Modéré": f"{p['probabilities']['moderate']:.1f}%",
                    "Sévère": f"{p['probabilities']['severe']:.1f}%",
                }
                for p in preds
            ])
            st.dataframe(df_log, width="stretch")


# ---------------------------------------------------------------------------
# Navigation principale
# ---------------------------------------------------------------------------
def main():
    """Point d'entrée principal de l'application Streamlit."""

    with st.sidebar:
        st.title("⚙️ Navigation")
        page = st.radio(
            "Choisir une page",
            ["🏠 Accueil", "📊 Analyse", "🔮 Prédiction rapide", "📈 Dashboard"],
            index=0,
        )

        st.divider()
        st.caption("HydroStress Prototype v1.1 — Errachidia")
        st.caption("Données : Sentinel-2 | CHIRPS | ERA5-Land")
        st.caption("Modèle : Random Forest + Calibration")

    if page == "🏠 Accueil":
        page_home()
    elif page == "📊 Analyse":
        page_analysis()
    elif page == "🔮 Prédiction rapide":
        page_quick_predict()
    elif page == "📈 Dashboard":
        page_dashboard()


if __name__ == "__main__":
    main()
