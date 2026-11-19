"""
farm_ui.py
==========
Section Streamlit « Entraîner sur ma ferme » : saisie de la ferme (position,
culture, écartement), téléchargement du climat, lecture des registres
d'irrigation, bilan hydrique, puis dataset satellite (Earth Engine) et
entraînement du modèle, directement dans l'application. Le dataset satellite
reprend là où il s'est arrêté si la page est fermée ou si la session expire.
"""

import io
import tempfile
import zipfile
from datetime import date
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from farm import CROPS, IRRIGATION, SOILS, Farm, parse_spacing

FARMS_DIR = Path("farms")


def _farm_form() -> Farm | None:
    saved = sorted(FARMS_DIR.glob("*.json")) if FARMS_DIR.exists() else []
    options = ["➕ Nouvelle ferme"] + [p.stem for p in saved]
    # Après « Enregistrer », la ferme enregistrée devient la ferme choisie (sinon les étapes suivantes disparaissent)
    a_choisir = st.session_state.pop("_ferme_a_choisir", None)
    if a_choisir in options:
        st.session_state["ferme_choisie"] = a_choisir
        st.toast(f"Ferme enregistrée : {a_choisir}", icon="✅")
    choice = st.selectbox("Ferme", options, key="ferme_choisie")
    current = Farm.load(FARMS_DIR / f"{choice}.json") if choice != "➕ Nouvelle ferme" else None

    with st.form("farm_form"):
        c1, c2, c3 = st.columns(3)
        name = c1.text_input("Nom (bloc, parcelle)", value=current.name if current else "")
        lat = c2.number_input("Latitude", value=current.latitude if current else 31.887705, format="%.6f")
        lon = c3.number_input("Longitude", value=current.longitude if current else -4.155879, format="%.6f")
        c1, c2, c3 = st.columns(3)
        crops = list(CROPS)
        crop = c1.selectbox("Culture", crops, index=crops.index(current.crop) if current else crops.index("amandier"),
                            format_func=lambda k: f"{CROPS[k]['name']} · {CROPS[k]['name_ar']}")
        spacing_default = f"{current.spacing_row_m:g}x{current.spacing_tree_m:g}" if current and current.spacing_row_m else ""
        spacing = c2.text_input("Écartement (m) : entre rangs x sur le rang", value=spacing_default, placeholder="7x5")
        area = c3.number_input("Surface (ha)", min_value=0.0, value=float(current.area_ha or 0) if current else 0.0)
        c1, c2, c3 = st.columns(3)
        year = c1.number_input("Année de plantation", min_value=1950, max_value=date.today().year,
                               value=int(current.planting_year or 2018) if current else 2018)
        irr_keys = list(IRRIGATION)
        irrigation = c2.selectbox("Irrigation", irr_keys, index=irr_keys.index(current.irrigation) if current else 0,
                                  format_func=lambda k: IRRIGATION[k]["name"])
        soil_keys = list(SOILS)
        soil = c3.selectbox("Sol", soil_keys, index=soil_keys.index(current.soil) if current else 0,
                            format_func=lambda k: SOILS[k]["name"])
        submitted = st.form_submit_button("💾 Enregistrer la ferme")

    if submitted:
        try:
            row, tree = parse_spacing(spacing) if spacing.strip() else (None, None)
            farm = Farm(name=name or "Ma ferme", latitude=lat, longitude=lon, crop=crop,
                        spacing_row_m=row, spacing_tree_m=tree, area_ha=area or None,
                        planting_year=int(year), irrigation=irrigation, soil=soil)
            farm.save(FARMS_DIR)
            st.session_state["_ferme_a_choisir"] = farm.id
            st.rerun()
        except ValueError as e:
            st.error(str(e))
            return None
    return current


def _data_dir(farm: Farm) -> Path:
    path = Path("data") / farm.id
    path.mkdir(parents=True, exist_ok=True)
    return path


def _climate_step(farm: Farm):
    from climate_history import download_climate

    c1, c2, c3 = st.columns([2, 1, 1])
    years = c1.slider("Années", 2000, date.today().year, (2018, 2025))
    source = c2.selectbox("Source", ["open-meteo", "nasa-power"])
    path = _data_dir(farm) / "climat.csv"
    if c3.button("⬇️ Télécharger le climat", width="stretch"):
        with st.spinner("Téléchargement année par année..."):
            try:
                path.unlink(missing_ok=True)
                download_climate(farm.latitude, farm.longitude, f"{years[0]}-01-01", f"{years[1]}-12-31",
                                 source=source, cache_file=str(path))
            except Exception as e:  # réseau, quota...
                st.error(f"Téléchargement impossible : {e}")
    if path.exists():
        df = pd.read_csv(path, parse_dates=["date"])
        summary = df.groupby(df["date"].dt.year).agg(pluie_mm=("precipitation_mm", "sum"), et0_mm=("et0_mm", "sum"),
                                                     t_max_moy=("temperature_max_c", "mean"), jours=("date", "size"))
        st.dataframe(summary.round(1), width="stretch")
        return df
    return None


def _irrigation_step(farm: Farm):
    from irrigation_register import campaign_of, coverage_report, read_registers

    path = _data_dir(farm) / "irrigation.csv"
    files = st.file_uploader("Registres d'irrigation (Excel, un fichier par campagne)", type=["xlsx"],
                             accept_multiple_files=True)
    if files and st.button("📖 Lire les registres"):
        if not farm.area_ha:
            st.error("Indiquez la surface de la ferme pour convertir les m³ en mm.")
        else:
            with tempfile.TemporaryDirectory() as tmp:
                paths = []
                for f in files:
                    p = Path(tmp) / Path(f.name).name
                    p.write_bytes(f.getvalue())
                    paths.append(str(p))
                try:
                    read_registers(paths, farm.area_ha).to_csv(path, index=False)
                except ValueError as e:
                    st.error(str(e))
    if path.exists():
        daily = pd.read_csv(path, parse_dates=["date"])
        camp = daily.assign(campagne=daily["date"].map(campaign_of)).groupby("campagne").agg(
            m3=("irrigation_m3", "sum"), mm=("irrigation_mm", "sum"), jours_irrigues=("date", "size"))
        st.dataframe(camp.round(0), width="stretch")
        report = coverage_report(daily)
        empty = [str(m) for m, r in report.iterrows() if r["jours_irrigues"] == 0]
        if empty:
            st.warning("Mois sans aucun apport : " + ", ".join(empty) +
                       ". Arrêt réel ou registre manquant ? Les longues périodes vides ne sont pas étiquetées.")
        return daily
    return None


def _balance_step(farm: Farm, climate: pd.DataFrame, irrigation: pd.DataFrame):
    from farm_dataset import labelled_dates
    from irrigation_register import campaign_of
    from water_balance import label_at, run_water_balance

    balance = run_water_balance(climate, irrigation, farm)
    monthly = balance.groupby(balance["date"].dt.to_period("M")).agg(
        etc=("etc_mm", "sum"), irr=("irrigation_mm", "sum"), pluie=("effective_rain_mm", "sum"), ks=("ks", "mean"))
    x = monthly.index.to_timestamp()
    fig = go.Figure()
    fig.add_bar(x=x, y=monthly["irr"], name="Irrigation (mm)", marker_color="#2DD4BF")
    fig.add_bar(x=x, y=monthly["pluie"], name="Pluie efficace (mm)", marker_color="#60A5FA")
    fig.add_scatter(x=x, y=monthly["etc"], name="Besoin ETc (mm)", line=dict(color="#F59E0B"))
    fig.add_scatter(x=x, y=monthly["ks"], name="Ks moyen", yaxis="y2", line=dict(color="#EF4444", dash="dot"))
    fig.update_layout(barmode="stack", height=380, margin=dict(l=10, r=10, t=30, b=10),
                      yaxis=dict(title="mm / mois"), yaxis2=dict(title="Ks", overlaying="y", side="right", range=[0, 1.05]),
                      legend=dict(orientation="h", y=1.12))
    st.plotly_chart(fig, width="stretch")

    dates = labelled_dates(balance, irrigation, every_days=10)
    if not dates:
        st.warning("Aucune date étiquetable : climat et registres ne couvrent pas la même période.")
        return
    labels = pd.DataFrame([{"date": d, **dict(zip(("stress_class", "ks"), label_at(balance, d)))} for d in dates])
    labels["campagne"] = labels["date"].map(campaign_of)
    dist = labels.pivot_table(index="campagne", columns="stress_class", values="ks", aggfunc="size", fill_value=0)
    st.dataframe(dist.rename(columns={0: "🟢 normal", 1: "🟡 modéré", 2: "🔴 sévère"}), width="stretch")
    labels.to_csv(_data_dir(farm) / "etiquettes.csv", index=False)
    st.download_button("Télécharger les étiquettes (CSV)", labels.to_csv(index=False), f"{farm.id}_etiquettes.csv")


def _dataset_step(farm: Farm, climate: pd.DataFrame, irrigation: pd.DataFrame | None):
    from farm_dataset import build_dataset

    path = _data_dir(farm) / "dataset.csv"
    c1, c2, c3 = st.columns([1, 1, 2])
    every = c1.selectbox("Une date tous les", [10, 15, 20, 30], format_func=lambda n: f"{n} jours",
                         help="Moins de dates = extraction plus rapide, mais moins d'exemples pour l'entraînement.")
    restart = c2.checkbox("Recommencer", value=False, help="Ignorer le dataset déjà extrait et tout refaire.")
    if c3.button("🛰️ Extraire les données satellite (Earth Engine)", width="stretch"):
        bar = st.progress(0.0, text="Connexion à Earth Engine…")

        def progress(i, total, message):
            bar.progress(i / max(total, 1), text=f"{i}/{total} · {message}")

        try:
            df, skipped = build_dataset(farm, climate, irrigation, path, every_days=every,
                                        resume=not restart, progress=progress)
            bar.progress(1.0, text="Terminé")
            st.success(f"{len(df)} échantillons ({skipped} dates sans image Sentinel-2 exploitable).")
        except Exception as e:  # Earth Engine non configuré, quota, réseau…
            st.error(f"Extraction interrompue : {e}. Relancez : elle reprendra là où elle s'est arrêtée.")
    if path.exists():
        df = pd.read_csv(path)
        if not df.empty:
            dist = df.groupby("campagne")["stress_class"].value_counts().unstack(fill_value=0)
            st.dataframe(dist.rename(columns={0: "🟢 normal", 1: "🟡 modéré", 2: "🔴 sévère"}), width="stretch")
            st.download_button("Télécharger le dataset (CSV)", df.to_csv(index=False), f"{farm.id}_dataset.csv")
            return path
    return None


def _model_zip(prefix: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for suffix in ("_pipeline.joblib", "_metadata.json"):
            f = Path(prefix + suffix)
            if f.exists():
                z.write(f, "hydrostress" + suffix)
    return buf.getvalue()


def _train_step(farm: Farm, dataset_path: Path):
    from farm_dataset import MIN_CAMPAIGNS, train_farm_model

    n = pd.read_csv(dataset_path)["campagne"].nunique()
    if n < MIN_CAMPAIGNS:
        st.info(f"{n} campagne(s) dans le dataset : il en faut au moins {MIN_CAMPAIGNS} pour entraîner et tester.")
        return
    grid = st.checkbox("Recherche des meilleurs réglages (plus long, plus précis)", value=False)
    if st.button("🧠 Entraîner le modèle sur cette ferme"):
        with st.spinner("Entraînement en cours…"):
            try:
                model, _, prefix = train_farm_model(farm, dataset_path, grid_search=grid)
            except Exception as e:
                st.error(f"Entraînement impossible : {e}")
                return
        st.session_state[f"modele_{farm.id}"] = (prefix, model.metadata.get("test_metrics", {}))
    trained = st.session_state.get(f"modele_{farm.id}")
    if trained:
        prefix, m = trained
        c = st.columns(4)
        c[0].metric("Exactitude (test)", f"{m.get('accuracy', 0):.0%}")
        c[1].metric("F1 pondéré", f"{m.get('f1_weighted', 0):.2f}")
        auc = m.get("roc_auc_ovr_weighted")
        c[2].metric("ROC-AUC", f"{auc:.2f}" if auc is not None else "—")
        c[3].metric("Échantillons de test", m.get("samples", 0))
        st.caption("Le test porte sur des campagnes jamais vues pendant l'entraînement.")
        st.download_button("⬇️ Télécharger le modèle (zip)", _model_zip(prefix), f"hydrostress_{farm.id}.zip",
                           help="Envoyez ce fichier pour qu'il devienne le modèle de l'application.")


def render_farm_training():
    st.caption("Décrivez la ferme, téléchargez son climat et lisez ses registres d'irrigation : un bilan hydrique "
               "FAO-56 en déduit le stress réel subi chaque jour, qui sert d'étiquette pour entraîner le modèle.")
    farm = _farm_form()
    if farm is None:
        return
    st.text(farm.summary())
    st.markdown("**1. Climat quotidien**")
    climate = _climate_step(farm)
    st.markdown("**2. Registres d'irrigation**")
    irrigation = _irrigation_step(farm)
    if climate is not None and (irrigation is not None or farm.irrigation == "pluvial"):
        st.markdown("**3. Bilan hydrique et étiquettes**")
        _balance_step(farm, climate, irrigation)
        st.markdown("**4. Données satellite (Earth Engine)**")
        dataset_path = _dataset_step(farm, climate, irrigation)
        if dataset_path is not None:
            st.markdown("**5. Entraînement du modèle**")
            _train_step(farm, dataset_path)
