"""
contrib_ui.py
=============
Section Streamlit « 🤝 Aidez-nous à améliorer le modèle » : envoi des données
d'une ferme (registres d'irrigation, description, contact) pour l'entraînement.
"""

import os
from datetime import date

import streamlit as st

from contrib import (CONSENT_TEXT, OTHER_TYPES, REGISTER_TYPES, Contribution, get_storage, submit,
                     summarize_registers)
from farm import CROPS, IRRIGATION, SOILS, Farm, parse_spacing
from i18n import get_lang, pick, t
from security import allow, log_incident
from report_text import IRRIGATION_NAMES, SOIL_NAMES, crop_name

# Messages de contrib.Contribution.errors() (en français) -> clé de traduction
_ERROR_KEYS = {
    "Cochez la case": "ct_err_consent", "Indiquez votre nom": "ct_err_you", "Indiquez un téléphone": "ct_err_contact",
    "L'adresse e-mail": "ct_err_email", "Ajoutez au moins": "ct_err_file",
}


def _translate_error(msg: str) -> str:
    for start, key in _ERROR_KEYS.items():
        if msg.startswith(start):
            return t(key)
    if msg.endswith("fichiers au maximum."):
        return t("ct_err_max_files", n=msg.split()[0])
    if msg.endswith("Mo au maximum au total."):
        return t("ct_err_max_mb", n=msg.split()[0])
    return msg


def render_contribution():
    lang = get_lang()
    st.markdown(t("ct_intro"))
    with st.container(border=True):
        st.markdown(t("ct_useful"))

    storage = get_storage()
    if not storage.durable and os.environ.get("CONTRIB_ALLOW_LOCAL") != "1":
        # Sans bucket, les fichiers seraient perdus au prochain redémarrage : on n'accepte pas d'envoi.
        st.info(t("ct_soon"))
        return
    with st.form("contribution", clear_on_submit=False):
        st.markdown(t("ct_you"))
        c1, c2, c3 = st.columns(3)
        name = c1.text_input(t("ct_name"))
        phone = c2.text_input(t("ct_phone"))
        email = c3.text_input(t("ct_email"))
        org = st.text_input(t("ct_org"))

        st.markdown(t("ct_plot"))
        c1, c2, c3 = st.columns(3)
        farm_name = c1.text_input(t("ct_plot_name"))
        lat = c2.number_input(t("ct_lat"), value=None, format="%.6f", placeholder="31.887705", help=t("ct_lat_help"))
        lon = c3.number_input(t("ct_lon"), value=None, format="%.6f", placeholder="-4.155879")
        c1, c2, c3 = st.columns(3)
        crops = list(CROPS)
        crop = c1.selectbox(t("ct_crop"), crops, index=crops.index("amandier"),
                            format_func=lambda k: crop_name(CROPS[k]["name"], lang))
        spacing = c2.text_input(t("ct_spacing"), placeholder="7x5")
        area = c3.number_input(t("ct_area"), min_value=0.0, value=None, placeholder="10")
        c1, c2, c3 = st.columns(3)
        year = c1.number_input(t("ct_year"), min_value=1950, max_value=date.today().year, value=None,
                               placeholder="2018")
        irr_keys, soil_keys = list(IRRIGATION), list(SOILS)
        irrigation = c2.selectbox(t("ct_irrigation"), irr_keys,
                                  format_func=lambda k: pick(IRRIGATION_NAMES.get(k, {"fr": IRRIGATION[k]["name"]})))
        soil = c3.selectbox(t("ct_soil"), soil_keys, format_func=lambda k: pick(SOIL_NAMES.get(k, {"fr": SOILS[k]["name"]})))

        st.markdown(t("ct_files"))
        registers = st.file_uploader(t("ct_registers"), type=list(REGISTER_TYPES),
                                     accept_multiple_files=True)
        others = st.file_uploader(t("ct_others"), type=list(OTHER_TYPES),
                                  accept_multiple_files=True)
        comment = st.text_area(t("ct_comment"), height=90)

        consent = st.checkbox(t("ct_consent") if lang != "fr" else CONSENT_TEXT)
        sent = st.form_submit_button(t("ct_send"), type="primary")

    if not sent:
        return

    problems = []
    if lat is None or lon is None:
        problems.append(t("ct_err_position"))
    if not farm_name.strip():
        problems.append(t("ct_err_name"))
    if not area:
        problems.append(t("ct_err_area"))
    farm = None
    if not problems:
        try:
            row, tree = parse_spacing(spacing) if spacing.strip() else (None, None)
            farm = Farm(name=farm_name.strip(), latitude=lat, longitude=lon, crop=crop, spacing_row_m=row,
                        spacing_tree_m=tree, area_ha=area, planting_year=int(year) if year else None,
                        irrigation=irrigation, soil=soil)
        except ValueError as e:
            problems.append(str(e))
    contribution = Contribution(
        contact={"name": name, "phone": phone, "email": email, "organisation": org},
        farm=farm.to_dict() if farm else {},
        consent=consent,
        registers=[(f.name, f.getvalue()) for f in (registers or [])],
        other_files=[(f.name, f.getvalue()) for f in (others or [])],
        comment=comment,
    )
    problems += [_translate_error(m) for m in contribution.errors()]
    if problems:
        for p in problems:
            st.error(p)
        return

    ok, wait = allow("contribution", st.session_state)
    if not ok:
        st.warning(t("sec_rate", m=max(1, wait // 60)))
        return
    with st.spinner(t("ct_sending")):
        contribution.register_summary = summarize_registers(contribution.registers, area)
        try:
            ref = submit(contribution, storage)
        except Exception as e:  # stockage indisponible : détail dans les journaux seulement
            st.error(t("sec_send_failed", ref=log_incident("contribution", e)))
            return
    st.success(t("ct_thanks", ref=ref))
    summary = contribution.register_summary
    if summary:
        st.caption(t("ct_read", a=summary["debut"], b=summary["fin"]))
        st.dataframe({c: v for c, v in summary["campagnes"].items()}, width="stretch")
    elif contribution.registers:
        st.caption(t("ct_unread"))
