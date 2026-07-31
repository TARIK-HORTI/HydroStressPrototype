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

# Import des modules du projet
from extract_data import DataPipeline, validate_geometry
from predict import HydroStressPredictor

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
    .main { padding: 0rem 1rem; }
    .metric-card {
        background-color: #f8f9fa;
        padding: 1.5rem;
        border-radius: 0.5rem;
        border-left: 4px solid #3b82f6;
    }
    .metric-value { font-size: 2.2rem; font-weight: bold; color: #1f2937; }
    .metric-label { font-size: 0.9rem; color: #6b7280; margin-top: 0.5rem; }
    .alert-box {
        padding: 1rem 1.25rem;
        border-radius: 0.5rem;
        margin: 1rem 0;
        border-left: 5px solid;
    }
    .alert-success { background-color: #dcfce7; border-left-color: #22c55e; }
    .alert-warning { background-color: #fef3c7; border-left-color: #f59e0b; }
    .alert-critical { background-color: #fee2e2; border-left-color: #ef4444; }
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
        return None


# ---------------------------------------------------------------------------
# Composants d'affichage
# ---------------------------------------------------------------------------
def create_map() -> tuple:
    """
    Crée la carte Folium interactive avec outil de dessin.

    Returns:
        tuple: (map_data, coordinates_list ou None)
    """
    st.subheader("🗺️ Délimitation de la parcelle")
    st.caption("Dessinez un polygone ou un rectangle sur la carte. Surface max : 10 km².")

    # Centré sur une zone agricole (exemple : région de Marrakech, Maroc)
    m = folium.Map(location=[31.63, -7.98], zoom_start=12, tiles="OpenStreetMap")

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
        st.plotly_chart(fig, use_container_width=True)

    if not era5_df.empty:
        fig2 = px.line(
            era5_df, x="date", y=["temperature_c", "humidity_percent"],
            title="Température et humidité relative",
            labels={"value": "Valeur", "date": "Date", "variable": "Mesure"},
        )
        fig2.update_layout(height=350)
        st.plotly_chart(fig2, use_container_width=True)

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
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.metric("Classe prédite", prediction["class_name"])
        st.metric("Confiance", f"{conf:.1f} %")
        st.metric("Probabilité dominante", f"{max(probs.values()):.1f} %")


def display_recommendations(prediction: dict, predictor: HydroStressPredictor):
    """Affiche les recommandations agronomiques structurées."""
    rec = predictor.get_recommendations(prediction)

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
    st.title("💧 HydroStress Prototype")
    st.markdown("**Prédiction du stress hydrique des cultures par Machine Learning et télédétection**")

    st.markdown("""
    ### 🚀 À propos

    Cette application analyse le stress hydrique des parcelles agricoles en combinant :

    - **🛰️ Sentinel-2** : indices spectraux (NDVI, NDWI, MSI, SAVI, EVI) à 10m de résolution
    - **🌧️ CHIRPS** : précipitations quotidiennes à 0.05°
    - **🌡️ ERA5-Land** : température, point de rosée, humidité relative calculée
    - **🤖 Random Forest** : classification en 3 classes (Normal, Modéré, Sévère)
    - **📊 Calibration** : probabilités calibrées par Platt scaling

    ### 📋 Workflow
    1. Naviguez vers **📊 Analyse**
    2. Délimitez votre parcelle sur la carte interactive
    3. Sélectionnez la date d'analyse
    4. Lancez l'extraction des données satellites et météo
    5. Obtenez la prédiction et les recommandations

    ### ⚠️ Prérequis
    - Compte Google Earth Engine activé (`earthengine authenticate`)
    - Modèle entraîné disponible (`python train_model.py`)
    """)

    c1, c2, c3 = st.columns(3)
    with c1:
        st.info("📡 3 sources de données satellites")
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

    # Carte interactive
    _, coordinates = create_map()

    if coordinates:
        st.success(f"✅ Parcelle définie : {len(coordinates)} points")
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
            value=datetime.now() - timedelta(days=5),  # Décalage pour éviter données non disponibles
            min_value=datetime(2017, 1, 1),
            max_value=datetime.now(),
        )
    with col2:
        lookback = st.slider("Fenêtre temporelle (jours)", 7, 60, 30)

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
                display_recommendations(pred, predictor)

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

    # Sliders organisés en colonnes
    col1, col2, col3 = st.columns(3)

    with col1:
        st.subheader("🌿 Végétation")
        ndvi = st.slider("NDVI (moyenne)", -0.2, 1.0, 0.65, 0.01)
        ndwi = st.slider("NDWI (moyenne)", -0.5, 1.0, 0.50, 0.01)
        savi = st.slider("SAVI (moyenne)", -0.2, 1.0, 0.58, 0.01)
        evi = st.slider("EVI (moyenne)", -0.2, 1.0, 0.48, 0.01)

    with col2:
        st.subheader("💧 Eau & Stress")
        msi = st.slider("MSI (moyenne)", 0.0, 3.0, 0.85, 0.01)
        precip_30j = st.slider("Précipitations 30j (mm)", 0.0, 300.0, 45.0, 1.0)
        precip_7j = st.slider("Précipitations 7j (mm)", 0.0, 150.0, 12.0, 1.0)
        dry_days = st.slider("Jours secs consécutifs max", 0, 30, 5, 1)

    with col3:
        st.subheader("🌡️ Climat")
        temp_mean = st.slider("Température moy. (°C)", 0.0, 50.0, 28.0, 0.5)
        temp_max = st.slider("Température max. (°C)", 0.0, 55.0, 35.0, 0.5)
        humidity = st.slider("Humidité moy. (%)", 0.0, 100.0, 60.0, 1.0)

        # Date pour le cyclique
        today = datetime.now()
        sin_doy, cos_doy = np.sin(2 * np.pi * today.timetuple().tm_yday / 366), np.cos(2 * np.pi * today.timetuple().tm_yday / 366)

    # Valeurs dérivées (coherent min/max/std)
    data = {
        "NDVI_mean": ndvi,
        "NDVI_min": max(ndvi - 0.1, -0.2),
        "NDVI_max": min(ndvi + 0.1, 1.0),
        "NDVI_std": 0.05,
        "NDWI_mean": ndwi,
        "NDWI_std": 0.04,
        "MSI_mean": msi,
        "MSI_min": max(msi - 0.1, 0.0),
        "MSI_max": min(msi + 0.1, 3.0),
        "MSI_std": 0.08,
        "SAVI_mean": savi,
        "EVI_mean": evi,
        "precipitation_total_30j": precip_30j,
        "precipitation_total_7j": precip_7j,
        "precipitation_mean": precip_30j / 30.0,
        "max_consecutive_dry_days": float(dry_days),
        "rainy_days_count": 10.0,
        "temperature_mean": temp_mean,
        "temperature_max": temp_max,
        "temperature_min": temp_mean - 5.0,
        "humidity_mean": humidity,
        "humidity_min": max(humidity - 10.0, 0.0),
        "day_of_year_sin": sin_doy,
        "day_of_year_cos": cos_doy,
    }

    if st.button("🎯 Prédire", type="primary"):
        prediction = predictor.predict(data)
        display_prediction(prediction)
        display_recommendations(prediction, predictor)


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
            st.dataframe(df_log, use_container_width=True)


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
        st.caption("HydroStress Prototype v1.0")
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
