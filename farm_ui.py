"""
farm_ui.py
==========
Section Streamlit « Entraîner sur ma ferme » : saisie de la ferme (position,
culture, écartement), téléchargement du climat, lecture des registres
d'irrigation et bilan hydrique. Les étapes Earth Engine (dataset complet et
entraînement) restent en ligne de commande (farm_dataset.py) car elles
prennent du temps.
"""

import tempfile
from datetime import date
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from farm import CROPS, IRRIGATION, SOILS, Farm, parse_spacing

FARMS_DIR = Path("farms")


def _farm_form() -> Farm | None:
    saved = sorted(FARMS_DIR.glob("*.json")) if FARMS_DIR.exists() else []
    choice = st.selectbox("Ferme", ["➕ Nouvelle ferme"] + [p.stem for p in saved])
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
            st.success(f"Ferme enregistrée : {farm.id}")
            return farm
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
    st.markdown(
        "Étape suivante (Earth Engine, quelques dizaines de minutes) :\n"
        f"```\npython farm_dataset.py build farms/{farm.id}.json\npython farm_dataset.py train farms/{farm.id}.json\n```"
    )


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
