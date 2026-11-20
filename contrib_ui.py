"""
contrib_ui.py
=============
Section Streamlit « 🤝 Aidez-nous à améliorer le modèle » : envoi des données
d'une ferme (registres d'irrigation, description, contact) pour l'entraînement.
"""

import os
from datetime import date

import streamlit as st

from contrib import CONSENT_TEXT, OTHER_TYPES, REGISTER_TYPES, Contribution, get_storage, submit, summarize_registers
from farm import CROPS, IRRIGATION, SOILS, Farm, parse_spacing


def render_contribution():
    st.markdown(
        "Le modèle apprend à partir de **vraies fermes**. Chaque ferme qui partage ses registres d'irrigation "
        "le rend plus juste pour sa région et sa culture. Les données servent uniquement à entraîner HydroStress : "
        "le nom et la position de votre ferme ne sont jamais publiés."
    )
    with st.container(border=True):
        st.markdown(
            "**Données les plus utiles**\n"
            "- Registres d'irrigation **jour par jour** (m³, heures × débit ou relevés de compteur), sur plusieurs "
            "campagnes : un fichier Excel par campagne convient.\n"
            "- La culture, l'écartement de plantation, la surface et l'année de plantation de la parcelle.\n"
            "- En plus si vous les avez : observations de stress (dates, symptômes), rendements par campagne, "
            "analyses de sol, limites de la parcelle (KML / GeoJSON)."
        )

    storage = get_storage()
    if not storage.durable and os.environ.get("CONTRIB_ALLOW_LOCAL") != "1":
        # Sans bucket, les fichiers seraient perdus au prochain redémarrage : on n'accepte pas d'envoi.
        st.info("📬 L'envoi de données ouvre très bientôt. En attendant, contactez-nous pour partager vos registres.")
        return
    with st.form("contribution", clear_on_submit=False):
        st.markdown("**1. Vous**")
        c1, c2, c3 = st.columns(3)
        name = c1.text_input("Nom et prénom *")
        phone = c2.text_input("Téléphone / WhatsApp")
        email = c3.text_input("E-mail")
        org = st.text_input("Exploitation, coopérative ou organisme (facultatif)")

        st.markdown("**2. La parcelle**")
        c1, c2, c3 = st.columns(3)
        farm_name = c1.text_input("Nom de la parcelle (ex. Bloc 4) *")
        lat = c2.number_input("Latitude *", value=None, format="%.6f", placeholder="31.887705",
                              help="Sur la carte ci-dessus ou dans Google Maps : clic droit sur la parcelle.")
        lon = c3.number_input("Longitude *", value=None, format="%.6f", placeholder="-4.155879")
        c1, c2, c3 = st.columns(3)
        crops = list(CROPS)
        crop = c1.selectbox("Culture *", crops, index=crops.index("amandier"),
                            format_func=lambda k: f"{CROPS[k]['name']} · {CROPS[k]['name_ar']}")
        spacing = c2.text_input("Écartement (m) : entre rangs x sur le rang", placeholder="7x5")
        area = c3.number_input("Surface (ha) *", min_value=0.0, value=None, placeholder="10")
        c1, c2, c3 = st.columns(3)
        year = c1.number_input("Année de plantation", min_value=1950, max_value=date.today().year, value=None,
                               placeholder="2018")
        irr_keys, soil_keys = list(IRRIGATION), list(SOILS)
        irrigation = c2.selectbox("Irrigation", irr_keys, format_func=lambda k: IRRIGATION[k]["name"])
        soil = c3.selectbox("Sol", soil_keys, format_func=lambda k: SOILS[k]["name"])

        st.markdown("**3. Vos fichiers**")
        registers = st.file_uploader("Registres d'irrigation (un fichier par campagne)", type=list(REGISTER_TYPES),
                                     accept_multiple_files=True)
        others = st.file_uploader("Autres fichiers utiles (facultatif)", type=list(OTHER_TYPES),
                                  accept_multiple_files=True)
        comment = st.text_area("Remarques (période couverte, changements de culture, panne, etc.)", height=90)

        consent = st.checkbox(CONSENT_TEXT)
        sent = st.form_submit_button("📤 Envoyer mes données", type="primary")

    if not sent:
        return

    problems = []
    if lat is None or lon is None:
        problems.append("Indiquez la position de la parcelle (latitude et longitude).")
    if not farm_name.strip():
        problems.append("Indiquez le nom de la parcelle.")
    if not area:
        problems.append("Indiquez la surface de la parcelle.")
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
    problems += contribution.errors()
    if problems:
        for p in problems:
            st.error(p)
        return

    with st.spinner("Lecture des registres et envoi…"):
        contribution.register_summary = summarize_registers(contribution.registers, area)
        try:
            ref = submit(contribution, storage)
        except Exception as e:  # stockage indisponible
            st.error(f"L'envoi n'a pas abouti ({e}). Réessayez plus tard ou contactez-nous.")
            return
    st.success(f"Merci ! Vos données sont bien reçues. Référence : **{ref}**. "
               "Gardez-la si vous voulez nous écrire à leur sujet.")
    summary = contribution.register_summary
    if summary:
        st.caption(f"Registres lus du {summary['debut']} au {summary['fin']} :")
        st.dataframe({c: v for c, v in summary["campagnes"].items()}, width="stretch")
    elif contribution.registers:
        st.caption("Nous n'avons pas pu lire automatiquement vos registres : nous les traiterons à la main.")
