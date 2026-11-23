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
from i18n import get_lang, pick, t
from report_text import IRRIGATION_NAMES, SOIL_NAMES, crop_name

FARMS_DIR = Path("farms")


def _farm_form() -> Farm | None:
    saved = sorted(FARMS_DIR.glob("*.json")) if FARMS_DIR.exists() else []
    new = "__new__"
    options = [new] + [p.stem for p in saved]
    lang = get_lang()
    # Après « Enregistrer », la ferme enregistrée devient la ferme choisie (sinon les étapes suivantes disparaissent)
    a_choisir = st.session_state.pop("_ferme_a_choisir", None)
    if a_choisir in options:
        st.session_state["ferme_choisie"] = a_choisir
        st.toast(t("fm_saved", name=a_choisir), icon="✅")
    if st.session_state.get("ferme_choisie") not in options:
        st.session_state.pop("ferme_choisie", None)
    choice = st.selectbox(t("fm_farm"), options, key="ferme_choisie",
                          format_func=lambda o: t("fm_new") if o == new else o)
    current = Farm.load(FARMS_DIR / f"{choice}.json") if choice != new else None

    with st.form("farm_form"):
        c1, c2, c3 = st.columns(3)
        name = c1.text_input(t("fm_name"), value=current.name if current else "")
        lat = c2.number_input(t("fm_lat"), value=current.latitude if current else 31.887705, format="%.6f")
        lon = c3.number_input(t("fm_lon"), value=current.longitude if current else -4.155879, format="%.6f")
        c1, c2, c3 = st.columns(3)
        crops = list(CROPS)
        crop = c1.selectbox(t("sm_crop"), crops, index=crops.index(current.crop) if current else crops.index("amandier"),
                            format_func=lambda k: crop_name(CROPS[k]["name"], lang))
        spacing_default = f"{current.spacing_row_m:g}x{current.spacing_tree_m:g}" if current and current.spacing_row_m else ""
        spacing = c2.text_input(t("ct_spacing"), value=spacing_default, placeholder="7x5")
        area = c3.number_input(t("fm_area"), min_value=0.0, value=float(current.area_ha or 0) if current else 0.0)
        c1, c2, c3 = st.columns(3)
        year = c1.number_input(t("ct_year"), min_value=1950, max_value=date.today().year,
                               value=int(current.planting_year or 2018) if current else 2018)
        irr_keys = list(IRRIGATION)
        irrigation = c2.selectbox(t("ct_irrigation"), irr_keys,
                                  index=irr_keys.index(current.irrigation) if current else 0,
                                  format_func=lambda k: pick(IRRIGATION_NAMES.get(k, {"fr": IRRIGATION[k]["name"]})))
        soil_keys = list(SOILS)
        soil = c3.selectbox(t("ct_soil"), soil_keys, index=soil_keys.index(current.soil) if current else 0,
                            format_func=lambda k: pick(SOIL_NAMES.get(k, {"fr": SOILS[k]["name"]})))
        submitted = st.form_submit_button(t("fm_save"))

    if submitted:
        try:
            row, tree = parse_spacing(spacing) if spacing.strip() else (None, None)
            farm = Farm(name=name or t("fm_default_name"), latitude=lat, longitude=lon, crop=crop,
                        spacing_row_m=row, spacing_tree_m=tree, area_ha=area or None,
                        planting_year=int(year), irrigation=irrigation, soil=soil)
            farm.save(FARMS_DIR)
            st.session_state["_ferme_a_choisir"] = farm.id
            st.rerun()
        except ValueError as e:
            st.error(str(e))
            return None
    return current


def _class_columns():
    return {0: t("fm_normal"), 1: t("fm_moderate"), 2: t("fm_severe")}


def _data_dir(farm: Farm) -> Path:
    path = Path("data") / farm.id
    path.mkdir(parents=True, exist_ok=True)
    return path


def _climate_step(farm: Farm):
    from climate_history import download_climate

    c1, c2, c3 = st.columns([2, 1, 1])
    years = c1.slider(t("fm_years"), 2000, date.today().year, (2018, 2025))
    source = c2.selectbox(t("fm_source"), ["open-meteo", "nasa-power"])
    path = _data_dir(farm) / "climat.csv"
    if c3.button(t("fm_dl_climate"), width="stretch"):
        with st.spinner(t("fm_dl_climate_spin")):
            try:
                path.unlink(missing_ok=True)
                download_climate(farm.latitude, farm.longitude, f"{years[0]}-01-01", f"{years[1]}-12-31",
                                 source=source, cache_file=str(path))
            except Exception as e:  # réseau, quota...
                st.error(t("fm_dl_failed", e=e))
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
    files = st.file_uploader(t("fm_registers"), type=["xlsx"],
                             accept_multiple_files=True)
    if files and st.button(t("fm_read")):
        if not farm.area_ha:
            st.error(t("fm_need_area"))
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
            st.warning(t("fm_empty_months", months=", ".join(empty)))
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
    fig.add_bar(x=x, y=monthly["irr"], name=t("fm_irr"), marker_color="#2DD4BF")
    fig.add_bar(x=x, y=monthly["pluie"], name=t("fm_rain_eff"), marker_color="#60A5FA")
    fig.add_scatter(x=x, y=monthly["etc"], name=t("fm_etc"), line=dict(color="#F59E0B"))
    fig.add_scatter(x=x, y=monthly["ks"], name=t("fm_ks"), yaxis="y2", line=dict(color="#EF4444", dash="dot"))
    fig.update_layout(barmode="stack", height=380, margin=dict(l=10, r=10, t=30, b=10),
                      yaxis=dict(title=t("fm_mm_month")), yaxis2=dict(title="Ks", overlaying="y", side="right", range=[0, 1.05]),
                      legend=dict(orientation="h", y=1.12))
    st.plotly_chart(fig, width="stretch")

    dates = labelled_dates(balance, irrigation, every_days=10)
    if not dates:
        st.warning(t("fm_no_dates"))
        return
    labels = pd.DataFrame([{"date": d, **dict(zip(("stress_class", "ks"), label_at(balance, d)))} for d in dates])
    labels["campagne"] = labels["date"].map(campaign_of)
    dist = labels.pivot_table(index="campagne", columns="stress_class", values="ks", aggfunc="size", fill_value=0)
    st.dataframe(dist.rename(columns=_class_columns()), width="stretch")
    labels.to_csv(_data_dir(farm) / "etiquettes.csv", index=False)
    st.download_button(t("fm_dl_labels"), labels.to_csv(index=False), f"{farm.id}_etiquettes.csv")


def _dataset_step(farm: Farm, climate: pd.DataFrame, irrigation: pd.DataFrame | None):
    from farm_dataset import build_dataset

    path = _data_dir(farm) / "dataset.csv"
    c1, c2, c3 = st.columns([1, 1, 2])
    every = c1.selectbox(t("fm_every"), [10, 15, 20, 30], format_func=lambda n: t("days", d=n),
                         help=t("fm_every_help"))
    restart = c2.checkbox(t("fm_restart"), value=False, help=t("fm_restart_help"))
    if c3.button(t("fm_extract"), width="stretch"):
        bar = st.progress(0.0, text=t("fm_ee_connect"))

        def progress(i, total, message):
            bar.progress(i / max(total, 1), text=f"{i}/{total} · {message}")

        try:
            df, skipped = build_dataset(farm, climate, irrigation, path, every_days=every,
                                        resume=not restart, progress=progress)
            bar.progress(1.0, text=t("fm_done"))
            st.success(t("fm_samples", n=len(df), s=skipped))
        except Exception as e:  # Earth Engine non configuré, quota, réseau…
            st.error(t("fm_extract_failed", e=e))
    if path.exists():
        df = pd.read_csv(path)
        if not df.empty:
            dist = df.groupby("campagne")["stress_class"].value_counts().unstack(fill_value=0)
            st.dataframe(dist.rename(columns=_class_columns()), width="stretch")
            st.download_button(t("fm_dl_dataset"), df.to_csv(index=False), f"{farm.id}_dataset.csv")
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
        st.info(t("fm_few_campaigns", n=n, m=MIN_CAMPAIGNS))
        return
    grid = st.checkbox(t("fm_grid"), value=False)
    if st.button(t("fm_train")):
        with st.spinner(t("fm_training")):
            try:
                model, _, prefix = train_farm_model(farm, dataset_path, grid_search=grid)
            except Exception as e:
                st.error(t("fm_train_failed", e=e))
                return
        st.session_state[f"modele_{farm.id}"] = (prefix, model.metadata.get("test_metrics", {}))
    trained = st.session_state.get(f"modele_{farm.id}")
    if trained:
        prefix, m = trained
        c = st.columns(4)
        c[0].metric(t("md_accuracy"), f"{m.get('accuracy', 0):.0%}")
        c[1].metric(t("fm_f1"), f"{m.get('f1_weighted', 0):.2f}")
        auc = m.get("roc_auc_ovr_weighted")
        c[2].metric("ROC-AUC", f"{auc:.2f}" if auc is not None else "—")
        c[3].metric(t("fm_test_samples"), m.get("samples", 0))
        st.caption(t("fm_test_note"))
        st.download_button(t("fm_dl_model"), _model_zip(prefix), f"hydrostress_{farm.id}.zip",
                           help=t("fm_dl_model_help"))


def render_farm_training():
    st.caption(t("fm_intro"))
    farm = _farm_form()
    if farm is None:
        return
    st.text(farm.summary())
    st.markdown(t("fm_step1"))
    climate = _climate_step(farm)
    st.markdown(t("fm_step2"))
    irrigation = _irrigation_step(farm)
    if climate is not None and (irrigation is not None or farm.irrigation == "pluvial"):
        st.markdown(t("fm_step3"))
        _balance_step(farm, climate, irrigation)
        st.markdown(t("fm_step4"))
        dataset_path = _dataset_step(farm, climate, irrigation)
        if dataset_path is not None:
            st.markdown(t("fm_step5"))
            _train_step(farm, dataset_path)
