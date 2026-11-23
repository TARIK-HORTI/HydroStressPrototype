"""
i18n.py
=======
Langues de l'interface : français (fr), arabe (ar) et anglais (en).

- `t(key, **kw)` : texte de l'interface dans la langue choisie (repli sur le français).
- `get_lang()` / `set_lang()` : langue courante (session Streamlit, ou `?lang=ar` dans l'URL).
- Les textes des cartes satellite (guide des indices, couches, interprétation) sont dans
  `IMAGERY_TEXT` et `GLOSSARY_TEXT`, utilisés par imagery.py.

Les noms de zones, de localités et de cultures restent ceux de region.py.
"""

from __future__ import annotations

from typing import Dict

from i18n_pages import PAGES

LANGS = {"fr": "Français", "ar": "العربية", "en": "English"}
DEFAULT_LANG = "fr"
RTL_LANGS = {"ar"}

_current = {"lang": DEFAULT_LANG}  # hors Streamlit (tests, CLI)


def _session():
    try:
        import streamlit as st
        return st.session_state
    except Exception:
        return None


def get_lang() -> str:
    ss = _session()
    try:
        if ss is not None and ss.get("lang") in LANGS:
            return ss["lang"]
    except Exception:  # pas de contexte Streamlit
        pass
    return _current["lang"]


def set_lang(lang: str) -> None:
    lang = lang if lang in LANGS else DEFAULT_LANG
    _current["lang"] = lang
    ss = _session()
    try:
        if ss is not None:
            ss["lang"] = lang
    except Exception:
        pass


def is_rtl(lang: str | None = None) -> bool:
    return (lang or get_lang()) in RTL_LANGS


def pick(entry: Dict[str, str], lang: str | None = None) -> str:
    """Texte d'un dictionnaire {fr, ar, en} dans la langue voulue (repli sur le français)."""
    lang = lang or get_lang()
    return entry.get(lang) or entry.get(DEFAULT_LANG, "")


def t(key: str, lang: str | None = None, **kw) -> str:
    entry = UI.get(key) or IMAGERY_TEXT.get(key) or PAGES.get(key)
    if entry is None:
        return key
    text = pick(entry, lang)
    return text.format(**kw) if kw else text


# ---------------------------------------------------------------------------
# Interface générale (app.py)
# ---------------------------------------------------------------------------
UI: Dict[str, Dict[str, str]] = {
    "lang_label": {"fr": "Langue", "ar": "اللغة", "en": "Language"},
    "beta_bar": {
        "fr": "🧪 <b>{by}Version bêta — démonstration.</b> Cette plateforme est une version de test en cours de "
              "développement : les résultats sont indicatifs et ne remplacent pas l'avis d'un conseiller agricole. "
              "Le service officiel sera ouvert prochainement.",
        "ar": "🧪 <b>{by}نسخة تجريبية.</b> هذه المنصة نسخة اختبارية قيد التطوير: النتائج إرشادية ولا تعوّض رأي "
              "المستشار الفلاحي. ستُفتح الخدمة الرسمية قريبًا.",
        "en": "🧪 <b>{by}Beta version — demo.</b> This platform is a test version under development: results are "
              "indicative and do not replace the advice of an agricultural advisor. The official service will "
              "open soon.",
    },
    "hero_intro": {
        "fr": "Suivi du stress hydrique des parcelles agricoles partout au Maroc (Gharb, Saïs, Tadla, Haouz, "
              "Chaouia-Doukkala, Souss-Massa, Oriental, oasis du Tafilalet et du Drâa), par télédétection et "
              "apprentissage automatique. Choisissez une zone, dessinez votre parcelle et obtenez un diagnostic "
              "avec des recommandations adaptées à la région et à la culture, ainsi que les cartes satellite du "
              "stress hydrique, de l'état sanitaire et du développement de la végétation pour suivre la ferme à "
              "distance.",
        "ar": "تتبّع الإجهاد المائي للضيعات الفلاحية في كل مناطق المغرب (الغرب، سايس، تادلة، الحوز، الشاوية-دكالة، "
              "سوس-ماسة، الشرق، واحات تافيلالت ودرعة) بالاستشعار عن بعد والتعلّم الآلي. اختر منطقة، ارسم قطعتك، "
              "واحصل على تشخيص مع توصيات تناسب المنطقة والزراعة، وعلى خرائط الأقمار الصناعية للإجهاد المائي "
              "والحالة الصحية ونموّ الغطاء النباتي لتتبّع ضيعتك عن بعد.",
        "en": "Monitoring of crop water stress for farm plots anywhere in Morocco (Gharb, Saïs, Tadla, Haouz, "
              "Chaouia-Doukkala, Souss-Massa, Oriental, Tafilalet and Drâa oases) using remote sensing and machine "
              "learning. Choose an area, draw your plot and get a diagnosis with recommendations suited to the "
              "region and crop, plus satellite maps of water stress, plant health and vegetation growth to "
              "monitor your farm remotely.",
    },
    "chip_maps": {"fr": "🗺️ Cartes satellite : eau, santé, croissance", "ar": "🗺️ خرائط الأقمار الصناعية: الماء، الصحة، النمو",
                  "en": "🗺️ Satellite maps: water, health, growth"},
    "chip_zones": {"fr": "📍 {n} zones agricoles", "ar": "📍 {n} مناطق فلاحية", "en": "📍 {n} farming areas"},
    "chip_synthetic": {"fr": "Modèle de démonstration (données synthétiques)", "ar": "نموذج للعرض (بيانات اصطناعية)",
                       "en": "Demo model (synthetic data)"},
    "chip_real": {"fr": "🌱 Modèle entraîné sur des données réelles de {origin}",
                  "ar": "🌱 نموذج مدرَّب على بيانات حقيقية من {origin}",
                  "en": "🌱 Model trained on real data from {origin}"},
    "step": {"fr": "ÉTAPE {n}", "ar": "الخطوة {n}", "en": "STEP {n}"},
    "step1": {"fr": "Choisissez une région et dessinez la parcelle sur la carte satellite.",
              "ar": "اختر منطقة وارسم القطعة على خريطة القمر الصناعي.",
              "en": "Choose a region and draw the plot on the satellite map."},
    "step2": {"fr": "Indiquez la culture et la date, puis lancez l'analyse.",
              "ar": "حدّد الزراعة والتاريخ ثم أطلق التحليل.",
              "en": "Set the crop and the date, then run the analysis."},
    "step3": {"fr": "Comparez les cartes satellite entre deux dates, lisez le rapport et téléchargez-le.",
              "ar": "قارن خرائط الأقمار الصناعية بين تاريخين، واقرأ التقرير وحمّله.",
              "en": "Compare satellite maps between two dates, read the report and download it."},
    "sec_params": {"fr": "Zone et paramètres", "ar": "المنطقة والإعدادات", "en": "Area and settings"},
    "region": {"fr": "Région agricole", "ar": "المنطقة الفلاحية", "en": "Farming region"},
    "all_morocco": {"fr": "Tout le Maroc", "ar": "كل المغرب", "en": "All of Morocco"},
    "place": {"fr": "Localité", "ar": "الجماعة / المكان", "en": "Locality"},
    "all_region": {"fr": "Toute la région", "ar": "كل المنطقة", "en": "Whole region"},
    "crop": {"fr": "Culture de la parcelle", "ar": "زراعة القطعة", "en": "Crop of the plot"},
    "analysis_date": {"fr": "Date d'analyse", "ar": "تاريخ التحليل", "en": "Analysis date"},
    "analysis_date_help": {"fr": "ERA5-Land et CHIRPS sont publiés avec environ une semaine de retard.",
                           "ar": "تُنشر بيانات ERA5-Land وCHIRPS بتأخير أسبوع تقريبًا.",
                           "en": "ERA5-Land and CHIRPS are published about one week late."},
    "window": {"fr": "Fenêtre satellite", "ar": "نافذة القمر الصناعي", "en": "Satellite window"},
    "window_help": {"fr": "Période du composite Sentinel-2 sans nuages.", "ar": "فترة تركيب صور Sentinel-2 بدون سحب.",
                    "en": "Period of the cloud-free Sentinel-2 composite."},
    "days": {"fr": "{d} jours", "ar": "{d} يومًا", "en": "{d} days"},
    "sec_map": {"fr": "Carte · dessinez votre parcelle", "ar": "الخريطة · ارسم قطعتك", "en": "Map · draw your plot"},
    "parcel_ready": {
        "fr": "✅ <b>Parcelle prête</b> · {ha:.2f} ha · {n} sommets<br>Centre : {lat:.4f}, {lon:.4f}<br>"
              "Zone détectée : <b>{zone}</b> (près de {near}){far}",
        "ar": "✅ <b>القطعة جاهزة</b> · {ha:.2f} هكتار · {n} رؤوس<br>المركز: {lat:.4f}، {lon:.4f}<br>"
              "المنطقة المكتشفة: <b>{zone}</b> (قرب {near}){far}",
        "en": "✅ <b>Plot ready</b> · {ha:.2f} ha · {n} vertices<br>Centre: {lat:.4f}, {lon:.4f}<br>"
              "Detected area: <b>{zone}</b> (near {near}){far}",
    },
    "parcel_far": {
        "fr": "<br><span style='color:#FCD34D'>⚠ À {d:.0f} km de la localité de référence la plus proche : "
              "seuils et recommandations approximatifs.</span>",
        "ar": "<br><span style='color:#FCD34D'>⚠ على بعد {d:.0f} كلم من أقرب مكان مرجعي: العتبات والتوصيات "
              "تقريبية.</span>",
        "en": "<br><span style='color:#FCD34D'>⚠ {d:.0f} km from the nearest reference locality: thresholds and "
              "recommendations are approximate.</span>",
    },
    "parcel_draw": {
        "fr": "✏️ Utilisez l'outil <b>rectangle</b> ou <b>polygone</b> de la carte pour dessiner votre parcelle "
              "(≤ 10 km², au Maroc).",
        "ar": "✏️ استعمل أداة <b>المستطيل</b> أو <b>المضلّع</b> في الخريطة لرسم قطعتك (≤ 10 كلم²، داخل المغرب).",
        "en": "✏️ Use the map's <b>rectangle</b> or <b>polygon</b> tool to draw your plot (≤ 10 km², in Morocco).",
    },
    "btn_analyse": {"fr": "🔍 Analyser la parcelle", "ar": "🔍 تحليل القطعة", "en": "🔍 Analyse the plot"},
    "btn_demo": {"fr": "Voir un exemple (données de démonstration)", "ar": "عرض مثال (بيانات للعرض)",
                 "en": "See an example (demo data)"},
    "exp_contrib": {"fr": "🤝 Aidez-nous à améliorer le modèle : partagez vos données",
                    "ar": "🤝 ساعدنا على تحسين النموذج: شارك بياناتك",
                    "en": "🤝 Help us improve the model: share your data"},
    "exp_model": {"fr": "🤖 À propos du modèle", "ar": "🤖 حول النموذج", "en": "🤖 About the model"},
    "exp_sim": {"fr": "🎛️ Simulation manuelle (sans satellite)", "ar": "🎛️ محاكاة يدوية (بدون قمر صناعي)",
                "en": "🎛️ Manual simulation (no satellite)"},
    "exp_farm": {"fr": "🌴 Entraîner sur ma ferme (données réelles)", "ar": "🌴 التدريب على ضيعتي (بيانات حقيقية)",
                 "en": "🌴 Train on my farm (real data)"},
    "footer": {
        "fr": "HydroStress Maroc · {owner}{stage}Données : Copernicus Sentinel-2, CHIRPS (UCSB-CHG), ERA5-Land (ECMWF) "
              "via Google Earth Engine · Résultats indicatifs",
        "ar": "HydroStress Maroc · {owner}{stage}المعطيات: Copernicus Sentinel-2، CHIRPS (UCSB-CHG)، ERA5-Land (ECMWF) "
              "عبر Google Earth Engine · النتائج إرشادية",
        "en": "HydroStress Maroc · {owner}{stage}Data: Copernicus Sentinel-2, CHIRPS (UCSB-CHG), ERA5-Land (ECMWF) "
              "via Google Earth Engine · Indicative results",
    },
    "footer_beta": {"fr": "Version bêta (démonstration) · ", "ar": "نسخة تجريبية · ", "en": "Beta version (demo) · "},
}


# ---------------------------------------------------------------------------
# Cartes satellite (imagery_ui.py)
# ---------------------------------------------------------------------------
IMAGERY_TEXT: Dict[str, Dict[str, str]] = {
    "img_title": {"fr": "Suivi satellite de la parcelle · cartes Sentinel-2",
                  "ar": "تتبّع القطعة بالأقمار الصناعية · خرائط Sentinel-2",
                  "en": "Satellite monitoring of the plot · Sentinel-2 maps"},
    "img_intro": {
        "fr": "Cartes du stress hydrique, de l'état sanitaire et du développement de la végétation, pixel par pixel "
              "(10 à 20 m). Choisissez deux dates pour comparer la parcelle image contre image et voir où elle "
              "évolue. Une nouvelle image Sentinel-2 environ tous les 5 jours, gratuite.",
        "ar": "خرائط الإجهاد المائي والحالة الصحية ونموّ الغطاء النباتي، نقطة بنقطة (10 إلى 20 م). اختر تاريخين "
              "لمقارنة القطعة صورة بصورة ومعرفة أين تغيّرت. صورة جديدة من Sentinel-2 كل 5 أيام تقريبًا، مجانًا.",
        "en": "Maps of water stress, plant health and vegetation growth, pixel by pixel (10 to 20 m). Pick two dates "
              "to compare the plot image against image and see where it changes. A new free Sentinel-2 image "
              "about every 5 days.",
    },
    "img_since": {"fr": "Images depuis", "ar": "الصور منذ", "en": "Images from"},
    "img_until": {"fr": "Jusqu'au", "ar": "إلى غاية", "en": "Until"},
    "img_search": {"fr": "🛰️ Chercher les images sans nuages", "ar": "🛰️ البحث عن الصور بدون سحب",
                   "en": "🛰️ Find cloud-free images"},
    "img_demo": {"fr": "Les cartes satellite demandent l'accès Earth Engine (pas de démonstration).",
                 "ar": "خرائط الأقمار الصناعية تتطلب الولوج إلى Earth Engine.",
                 "en": "Satellite maps require Earth Engine access (no demo)."},
    "img_period_short": {"fr": "Choisissez une période d'au moins 10 jours.", "ar": "اختر فترة لا تقل عن 10 أيام.",
                         "en": "Choose a period of at least 10 days."},
    "img_searching": {"fr": "Recherche des images Sentinel-2 et calcul des indices sur la parcelle…",
                      "ar": "جارٍ البحث عن صور Sentinel-2 وحساب المؤشرات على القطعة…",
                      "en": "Searching Sentinel-2 images and computing indices over the plot…"},
    "img_unavailable": {"fr": "Images indisponibles : {e}", "ar": "الصور غير متوفرة: {e}", "en": "Images unavailable: {e}"},
    "img_click": {"fr": "Cliquez sur « Chercher les images sans nuages » pour charger les cartes de la parcelle.",
                  "ar": "اضغط على «البحث عن الصور بدون سحب» لتحميل خرائط القطعة.",
                  "en": "Click “Find cloud-free images” to load the maps of the plot."},
    "img_none": {"fr": "Aucune image où la parcelle est dégagée à plus de 80 % sur cette période : élargissez-la.",
                 "ar": "لا توجد صورة تظهر فيها القطعة بأكثر من 80 % بدون سحب في هذه الفترة: وسّع الفترة.",
                 "en": "No image with the plot more than 80 % cloud-free in this period: widen it."},
    "img_found": {"fr": "{n} image(s) sans nuages sur la parcelle entre le {a} et le {b}.",
                  "ar": "{n} صورة بدون سحب على القطعة بين {a} و{b}.",
                  "en": "{n} cloud-free image(s) over the plot between {a} and {b}."},
    "img_theme": {"fr": "Volet", "ar": "المحور", "en": "Topic"},
    "img_layer": {"fr": "Carte", "ar": "الخريطة", "en": "Map"},
    "img_date_a": {"fr": "Date A (avant)", "ar": "التاريخ A (قبل)", "en": "Date A (before)"},
    "img_date_b": {"fr": "Date B (après)", "ar": "التاريخ B (بعد)", "en": "Date B (after)"},
    "img_preparing": {"fr": "Préparation des cartes…", "ar": "جارٍ إعداد الخرائط…", "en": "Preparing maps…"},
    "img_no_history": {"fr": "Pas d'images des années précédentes à cette période pour calculer l'anomalie.",
                       "ar": "لا توجد صور من السنوات السابقة في هذه الفترة لحساب الشذوذ.",
                       "en": "No images from previous years at this time of year to compute the anomaly."},
    "img_maps_error": {"fr": "Cartes indisponibles : {e}", "ar": "الخرائط غير متوفرة: {e}", "en": "Maps unavailable: {e}"},
    "img_change": {"fr": "**Changement B − A** · où la parcelle a évolué", "ar": "**التغيّر B − A** · أين تغيّرت القطعة",
                   "en": "**Change B − A** · where the plot changed"},
    "img_no_diff": {"fr": "Pas de carte de différence pour cette couche.", "ar": "لا توجد خريطة فرق لهذه الطبقة.",
                    "en": "No difference map for this layer."},
    "img_means": {"fr": "**Moyennes de la parcelle**", "ar": "**متوسطات القطعة**", "en": "**Plot averages**"},
    "img_col_index": {"fr": "Indice", "ar": "المؤشر", "en": "Index"},
    "img_col_delta": {"fr": "Écart B − A", "ar": "الفرق B − A", "en": "Difference B − A"},
    "img_col_trend": {"fr": "Évolution", "ar": "التطور", "en": "Trend"},
    "trend_better": {"fr": "Amélioration", "ar": "تحسّن", "en": "Improvement"},
    "trend_worse": {"fr": "Dégradation", "ar": "تدهور", "en": "Decline"},
    "trend_stable": {"fr": "Stable", "ar": "مستقر", "en": "Stable"},
    "trend_unknown": {"fr": "—", "ar": "—", "en": "—"},
    "img_geotiff": {"fr": "⬇️ Carte de la date B (GeoTIFF, pour QGIS)", "ar": "⬇️ خريطة التاريخ B (GeoTIFF لـ QGIS)",
                    "en": "⬇️ Date B map (GeoTIFF, for QGIS)"},
    "img_cause_note": {
        "fr": "Les indices montrent un changement de vigueur, d'eau ou de chlorophylle, pas sa cause : une baisse "
              "localisée se vérifie au champ (irrigation, maladie, ravageur, carence).",
        "ar": "المؤشرات تُظهر تغيّرًا في القوة أو الماء أو الكلوروفيل، ولا تُظهر سببه: أي تراجع في مكان معيّن "
              "يُتحقّق منه في الحقل (السقي، مرض، حشرة، نقص في التسميد).",
        "en": "Indices show a change in vigour, water or chlorophyll, not its cause: a local decline must be checked "
              "in the field (irrigation, disease, pest, deficiency).",
    },
    "img_pick_two": {"fr": "Choisissez deux dates différentes pour obtenir l'interprétation du changement.",
                     "ar": "اختر تاريخين مختلفين للحصول على تفسير التغيّر.",
                     "en": "Choose two different dates to get the interpretation of the change."},
    "img_series_title": {"fr": "**Évolution de la parcelle sur la période** (moyenne à chaque image)",
                         "ar": "**تطوّر القطعة خلال الفترة** (المتوسط في كل صورة)",
                         "en": "**Plot trend over the period** (average for each image)"},
    "img_series_pick": {"fr": "Indices", "ar": "المؤشرات", "en": "Indices"},
    # Orientation : zones à visiter
    "zn_title": {"fr": "#### 🧭 Orientation : zones de la parcelle à visiter",
                 "ar": "#### 🧭 التوجيه: مناطق القطعة التي يجب زيارتها",
                 "en": "#### 🧭 Guidance: zones of the plot to visit"},
    "zn_intro": {
        "fr": "Le système compare les deux images pixel par pixel (NDVI, NDMI, NDRE, PSRI), repère les zones qui ont "
              "changé, les dessine sur la carte et les classe de la plus urgente à la moins urgente. Pour chaque "
              "zone : les indices qui ont bougé, les causes possibles, ce qu'il faut regarder sur place et "
              "l'itinéraire pour s'y rendre.",
        "ar": "يقارن النظام الصورتين نقطة بنقطة (NDVI، NDMI، NDRE، PSRI)، ويحدّد المناطق التي تغيّرت، ويرسمها على "
              "الخريطة ويرتّبها من الأكثر استعجالًا إلى الأقل. لكل منطقة: المؤشرات التي تغيّرت، والأسباب المحتملة، "
              "وما يجب فحصه في عين المكان، والطريق للوصول إليها.",
        "en": "The system compares the two images pixel by pixel (NDVI, NDMI, NDRE, PSRI), finds the zones that "
              "changed, draws them on the map and ranks them from most to least urgent. For each zone: the indices "
              "that moved, possible causes, what to look at on site and directions to get there.",
    },
    "zn_relative": {"fr": "Comparer au reste de la parcelle (recommandé)", "ar": "المقارنة مع باقي القطعة (موصى به)",
                    "en": "Compare with the rest of the plot (recommended)"},
    "zn_relative_help": {
        "fr": "Activé : seules les zones qui ont évolué plus mal que l'ensemble de la parcelle sont signalées "
              "(l'effet de la saison ou d'une irrigation générale est retiré). Désactivé : toute baisse est signalée.",
        "ar": "مفعّل: لا تُعرض إلا المناطق التي تطوّرت أسوأ من مجموع القطعة (يُحذف أثر الموسم أو السقي العام). غير "
              "مفعّل: يُعرض كل انخفاض.",
        "en": "On: only zones that changed for the worse compared with the whole plot are flagged (the effect of the "
              "season or of plot-wide irrigation is removed). Off: every decline is flagged.",
    },
    "zn_detect": {"fr": "🧭 Détecter les zones qui ont changé", "ar": "🧭 كشف المناطق التي تغيّرت",
                  "en": "🧭 Detect the zones that changed"},
    "zn_detecting": {"fr": "Comparaison des deux images pixel par pixel…", "ar": "جارٍ مقارنة الصورتين نقطة بنقطة…",
                     "en": "Comparing the two images pixel by pixel…"},
    "zn_error": {"fr": "Détection impossible : {e}", "ar": "تعذّر الكشف: {e}", "en": "Detection failed: {e}"},
    "zn_none": {
        "fr": "Aucune zone de végétation d'au moins 500 m² n'a changé de façon notable entre les deux dates "
              "(le sol nu n'est pas analysé).",
        "ar": "لم تتغيّر أي منطقة نباتية تفوق 500 م² بشكل ملحوظ بين التاريخين (التربة العارية لا تُحلَّل).",
        "en": "No vegetated zone of at least 500 m² changed notably between the two dates (bare soil is not "
              "analysed).",
    },
    "zn_found": {"fr": "{n} zone(s) à visiter, de la plus prioritaire à la moins prioritaire.",
                 "ar": "{n} منطقة للزيارة، من الأكثر أولوية إلى الأقل.",
                 "en": "{n} zone(s) to visit, from highest to lowest priority."},
    "zn_card": {"fr": "Zone {id} · {cat} · {area} · {lat}, {lon}", "ar": "المنطقة {id} · {cat} · {area} · {lat}، {lon}",
                "en": "Zone {id} · {cat} · {area} · {lat}, {lon}"},
    "zn_changed": {"fr": "**Indices qui ont changé**", "ar": "**المؤشرات التي تغيّرت**", "en": "**Indices that changed**"},
    "zn_go": {"fr": "📍 Y aller (Google Maps)", "ar": "📍 الذهاب إليها (Google Maps)", "en": "📍 Go there (Google Maps)"},
    "zn_geojson": {"fr": "⬇️ Zones (GeoJSON)", "ar": "⬇️ المناطق (GeoJSON)", "en": "⬇️ Zones (GeoJSON)"},
    "zn_kml": {"fr": "⬇️ Zones pour téléphone (KML : Google Earth, OsmAnd)", "ar": "⬇️ المناطق للهاتف (KML: Google Earth، OsmAnd)",
               "en": "⬇️ Zones for phone (KML: Google Earth, OsmAnd)"},
    "zn_area_m2": {"fr": "{v} m²", "ar": "{v} م²", "en": "{v} m²"},
    "zn_area_ha": {"fr": "{v} ha", "ar": "{v} هكتار", "en": "{v} ha"},
    "zn_delta": {"fr": "écart", "ar": "الفرق", "en": "change"},
    "zn_delta_rel": {"fr": "écart par rapport au reste de la parcelle", "ar": "الفرق مقارنة بباقي القطعة",
                     "en": "change compared with the rest of the plot"},
    "zn_cat_water": {"fr": "Perte d'eau", "ar": "فقدان الماء", "en": "Water loss"},
    "zn_cat_health": {"fr": "Chlorophylle / jaunissement", "ar": "الكلوروفيل / الاصفرار", "en": "Chlorophyll / yellowing"},
    "zn_cat_decline": {"fr": "Eau + chlorophylle", "ar": "الماء + الكلوروفيل", "en": "Water + chlorophyll"},
    "zn_cat_vigor": {"fr": "Baisse de vigueur", "ar": "انخفاض القوة", "en": "Loss of vigour"},
    # Guide
    "gl_title": {"fr": "#### 📖 Comprendre les indices satellite", "ar": "#### 📖 فهم مؤشرات الأقمار الصناعية",
                 "en": "#### 📖 Understanding satellite indices"},
    "gl_intro": {
        "fr": "Le satellite Sentinel-2 mesure la lumière renvoyée par la parcelle dans plusieurs couleurs, dont "
              "certaines invisibles à l'œil (proche infrarouge, red-edge, infrarouge à ondes courtes). Une feuille "
              "saine, bien alimentée en eau et riche en chlorophylle ne renvoie pas la même lumière qu'une feuille "
              "sèche, malade ou jaunie. Les indices combinent ces couleurs pour suivre trois choses : "
              "**le développement de la végétation (NDVI)**, **l'eau dans les feuilles (NDMI, MSI)** et "
              "**l'état sanitaire (NDRE, PSRI)**.",
        "ar": "يقيس القمر الصناعي Sentinel-2 الضوء الذي تعكسه القطعة في عدة ألوان، بعضها لا تراه العين (الأشعة تحت "
              "الحمراء القريبة، الحافة الحمراء، الأشعة تحت الحمراء القصيرة). الورقة السليمة والمرتوية والغنية "
              "بالكلوروفيل لا تعكس نفس الضوء الذي تعكسه ورقة جافة أو مريضة أو مصفرّة. تجمع المؤشرات هذه الألوان "
              "لتتبّع ثلاثة أشياء: **نموّ الغطاء النباتي (NDVI)**، **الماء في الأوراق (NDMI، MSI)** و"
              "**الحالة الصحية (NDRE، PSRI)**.",
        "en": "The Sentinel-2 satellite measures the light reflected by the plot in several colours, some invisible "
              "to the eye (near infrared, red-edge, short-wave infrared). A healthy, well-watered leaf rich in "
              "chlorophyll does not reflect the same light as a dry, diseased or yellowing one. Indices combine "
              "these colours to track three things: **vegetation growth (NDVI)**, **water in the leaves (NDMI, "
              "MSI)** and **plant health (NDRE, PSRI)**.",
    },
    "gl_meaning": {"fr": "Ce qu'il mesure.", "ar": "ماذا يقيس.", "en": "What it measures."},
    "gl_reading": {"fr": "Comment le lire.", "ar": "كيف تقرؤه.", "en": "How to read it."},
    "gl_use": {"fr": "À quoi il sert.", "ar": "فيمَ يفيد.", "en": "What it is for."},
    "gl_formula": {"fr": "Calcul", "ar": "طريقة الحساب", "en": "Formula"},
    # Interprétation
    "in_title": {"fr": "#### 🔎 Interprétation automatique du changement", "ar": "#### 🔎 التفسير الآلي للتغيّر",
                 "en": "#### 🔎 Automatic interpretation of the change"},
    "in_obs": {"fr": "**Ce que montrent les images**", "ar": "**ما تُظهره الصور**", "en": "**What the images show**"},
    "in_causes": {"fr": "**Causes possibles**", "ar": "**الأسباب المحتملة**", "en": "**Possible causes**"},
    "in_checks": {"fr": "**À vérifier sur le terrain**", "ar": "**ما يجب التحقق منه في الحقل**",
                  "en": "**What to check in the field**"},
    "in_field_last": {"fr": "Le terrain a le dernier mot.", "ar": "الكلمة الأخيرة للحقل.",
                      "en": "The field has the final say."},
    "lk_probable": {"fr": "Probable", "ar": "مرجَّح", "en": "Likely"},
    "lk_possible": {"fr": "Possible", "ar": "ممكن", "en": "Possible"},
}


# ---------------------------------------------------------------------------
# Guide des indices
# ---------------------------------------------------------------------------
GLOSSARY_TEXT: Dict[str, Dict[str, Dict[str, str]]] = {
    "NDVI": {
        "name": {"fr": "NDVI — Indice de végétation par différence normalisée",
                 "ar": "NDVI — مؤشر الغطاء النباتي",
                 "en": "NDVI — Normalized Difference Vegetation Index"},
        "formula": {"fr": "(PIR − Rouge) / (PIR + Rouge) · bandes B8 et B4 · 10 m",
                    "ar": "(تحت الأحمر القريب − الأحمر) / (تحت الأحمر القريب + الأحمر) · النطاقان B8 وB4 · 10 م",
                    "en": "(NIR − Red) / (NIR + Red) · bands B8 and B4 · 10 m"},
        "meaning": {
            "fr": "Une feuille verte absorbe le rouge pour la photosynthèse et renvoie fortement le proche "
                  "infrarouge. Plus il y a de feuillage vert et vigoureux, plus le NDVI est élevé.",
            "ar": "الورقة الخضراء تمتص اللون الأحمر للقيام بالتمثيل الضوئي وتعكس بقوة الأشعة تحت الحمراء القريبة. "
                  "كلما كان الغطاء الأخضر أكثف وأقوى، ارتفع NDVI.",
            "en": "A green leaf absorbs red light for photosynthesis and strongly reflects near infrared. The more "
                  "green, vigorous foliage there is, the higher the NDVI.",
        },
        "reading": {
            "fr": "< 0,2 : sol nu ou très peu de végétation · 0,2–0,4 : couvert faible ou jeune · 0,4–0,6 : couvert "
                  "moyen · > 0,6 : végétation dense et vigoureuse.",
            "ar": "أقل من 0,2: تربة عارية أو نبات قليل جدًا · 0,2–0,4: غطاء ضعيف أو فتيّ · 0,4–0,6: غطاء متوسط · "
                  "أكثر من 0,6: نبات كثيف وقوي.",
            "en": "< 0.2: bare soil or very little vegetation · 0.2–0.4: sparse or young cover · 0.4–0.6: medium "
                  "cover · > 0.6: dense, vigorous vegetation.",
        },
        "use": {
            "fr": "Suivre la croissance et le développement du couvert, comparer les blocs, repérer les arbres ou les "
                  "rangs en retard. C'est l'indice de référence, mais il réagit tard : quand il baisse, le problème "
                  "est souvent déjà installé.",
            "ar": "تتبّع نموّ الغطاء النباتي وتطوّره، ومقارنة البلوكات، وتحديد الأشجار أو الخطوط المتأخرة. هو المؤشر "
                  "المرجعي، لكنه يتفاعل متأخرًا: عندما ينخفض يكون المشكل غالبًا قد استقر.",
            "en": "Track crop growth and canopy development, compare blocks, spot lagging trees or rows. It is the "
                  "reference index, but it reacts late: when it drops, the problem is often already established.",
        },
    },
    "NDMI": {
        "name": {"fr": "NDMI — Indice d'humidité par différence normalisée", "ar": "NDMI — مؤشر الرطوبة",
                 "en": "NDMI — Normalized Difference Moisture Index"},
        "formula": {"fr": "(PIR − SWIR) / (PIR + SWIR) · bandes B8 et B11 · 20 m",
                    "ar": "(تحت الأحمر القريب − تحت الأحمر القصير) / (المجموع) · النطاقان B8 وB11 · 20 م",
                    "en": "(NIR − SWIR) / (NIR + SWIR) · bands B8 and B11 · 20 m"},
        "meaning": {
            "fr": "L'eau contenue dans les feuilles absorbe l'infrarouge à ondes courtes (SWIR). Une feuille bien "
                  "hydratée renvoie peu de SWIR, donc un NDMI élevé.",
            "ar": "الماء الموجود في الأوراق يمتص الأشعة تحت الحمراء القصيرة (SWIR). الورقة المرتوية تعكس القليل منها، "
                  "فيكون NDMI مرتفعًا.",
            "en": "Water in the leaves absorbs short-wave infrared (SWIR). A well-hydrated leaf reflects little SWIR, "
                  "hence a high NDMI.",
        },
        "reading": {
            "fr": "< 0 : feuillage sec ou sol nu · 0–0,2 : teneur en eau faible à moyenne · > 0,2 : feuillage bien "
                  "alimenté en eau.",
            "ar": "أقل من 0: أوراق جافة أو تربة عارية · 0–0,2: محتوى مائي ضعيف إلى متوسط · أكثر من 0,2: أوراق مرتوية جيدًا.",
            "en": "< 0: dry foliage or bare soil · 0–0.2: low to medium water content · > 0.2: well-watered foliage.",
        },
        "use": {
            "fr": "Détecter le stress hydrique tôt, avant que les feuilles ne jaunissent ou ne tombent, et vérifier "
                  "que l'irrigation arrive partout dans la parcelle (secteurs, bouts de lignes).",
            "ar": "كشف الإجهاد المائي مبكرًا، قبل اصفرار الأوراق أو سقوطها، والتأكد من أن السقي يصل إلى كل القطعة "
                  "(القطاعات، نهايات الخطوط).",
            "en": "Detect water stress early, before leaves yellow or drop, and check that irrigation reaches the whole "
                  "plot (sectors, ends of lines).",
        },
    },
    "MSI": {
        "name": {"fr": "MSI — Indice de stress hydrique", "ar": "MSI — مؤشر الإجهاد المائي",
                 "en": "MSI — Moisture Stress Index"},
        "formula": {"fr": "SWIR / PIR · bandes B11 et B8 · 20 m",
                    "ar": "تحت الأحمر القصير / تحت الأحمر القريب · النطاقان B11 وB8 · 20 م",
                    "en": "SWIR / NIR · bands B11 and B8 · 20 m"},
        "meaning": {
            "fr": "Même information que le NDMI, lue à l'envers : il augmente quand la végétation perd de l'eau.",
            "ar": "نفس معلومة NDMI لكن معكوسة: يرتفع عندما يفقد النبات الماء.",
            "en": "Same information as NDMI, read the other way round: it rises when vegetation loses water.",
        },
        "reading": {
            "fr": "< 0,8 : pas de stress · 0,8–1,2 : stress modéré · > 1,2 : stress fort ou sol nu.",
            "ar": "أقل من 0,8: لا إجهاد · 0,8–1,2: إجهاد متوسط · أكثر من 1,2: إجهاد قوي أو تربة عارية.",
            "en": "< 0.8: no stress · 0.8–1.2: moderate stress · > 1.2: severe stress or bare soil.",
        },
        "use": {"fr": "Confirmer un stress hydrique signalé par le NDMI.", "ar": "تأكيد إجهاد مائي أشار إليه NDMI.",
                "en": "Confirm water stress flagged by NDMI."},
    },
    "NDRE": {
        "name": {"fr": "NDRE — Indice red-edge par différence normalisée", "ar": "NDRE — مؤشر الحافة الحمراء (الكلوروفيل)",
                 "en": "NDRE — Normalized Difference Red Edge index"},
        "formula": {"fr": "(PIR − Red-edge) / (PIR + Red-edge) · bandes B8 et B5 · 20 m",
                    "ar": "(تحت الأحمر القريب − الحافة الحمراء) / (المجموع) · النطاقان B8 وB5 · 20 م",
                    "en": "(NIR − Red-edge) / (NIR + Red-edge) · bands B8 and B5 · 20 m"},
        "meaning": {
            "fr": "Le « red-edge » est la zone où la réflectance de la feuille passe du rouge au proche infrarouge. "
                  "Sa position dépend directement de la chlorophylle (et donc de l'azote).",
            "ar": "«الحافة الحمراء» هي المنطقة التي ينتقل فيها انعكاس الورقة من الأحمر إلى تحت الأحمر القريب. موقعها "
                  "مرتبط مباشرة بالكلوروفيل (وبالتالي بالأزوت).",
            "en": "The red edge is where leaf reflectance jumps from red to near infrared. Its position depends "
                  "directly on chlorophyll (and therefore nitrogen).",
        },
        "reading": {
            "fr": "< 0,15 : peu de chlorophylle · 0,15–0,3 : moyen · > 0,3 : feuillage riche en chlorophylle.",
            "ar": "أقل من 0,15: كلوروفيل قليل · 0,15–0,3: متوسط · أكثر من 0,3: أوراق غنية بالكلوروفيل.",
            "en": "< 0.15: little chlorophyll · 0.15–0.3: medium · > 0.3: chlorophyll-rich foliage.",
        },
        "use": {
            "fr": "Indicateur de l'état sanitaire et nutritionnel : il baisse avant le NDVI en cas de carence (azote, "
                  "fer), de maladie, d'attaque de ravageurs ou de dépérissement, et il sature moins que le NDVI sur "
                  "les vergers denses.",
            "ar": "مؤشر للحالة الصحية والغذائية: ينخفض قبل NDVI عند نقص التسميد (الأزوت، الحديد) أو المرض أو هجوم "
                  "الحشرات أو ضعف الأشجار، ويتشبّع أقل من NDVI في البساتين الكثيفة.",
            "en": "Indicator of health and nutrition: it drops before NDVI with a deficiency (nitrogen, iron), "
                  "disease, pest attack or decline, and saturates less than NDVI in dense orchards.",
        },
    },
    "PSRI": {
        "name": {"fr": "PSRI — Indice de réflectance de la sénescence des plantes", "ar": "PSRI — مؤشر الاصفرار والشيخوخة",
                 "en": "PSRI — Plant Senescence Reflectance Index"},
        "formula": {"fr": "(Rouge − Bleu) / Red-edge 2 · bandes B4, B2 et B6 · 20 m",
                    "ar": "(الأحمر − الأزرق) / الحافة الحمراء 2 · النطاقات B4 وB2 وB6 · 20 م",
                    "en": "(Red − Blue) / Red-edge 2 · bands B4, B2 and B6 · 20 m"},
        "meaning": {
            "fr": "Mesure le rapport entre pigments jaunes (caroténoïdes) et chlorophylle. Quand la chlorophylle "
                  "disparaît, les feuilles jaunissent et le PSRI augmente.",
            "ar": "يقيس النسبة بين الصبغات الصفراء (الكاروتينات) والكلوروفيل. عندما يختفي الكلوروفيل تصفرّ الأوراق "
                  "ويرتفع PSRI.",
            "en": "Measures the ratio of yellow pigments (carotenoids) to chlorophyll. When chlorophyll disappears, "
                  "leaves turn yellow and PSRI rises.",
        },
        "reading": {
            "fr": "< 0 : feuillage vert et actif · 0–0,1 : début de jaunissement · > 0,1 : jaunissement net, "
                  "sénescence ou dessèchement.",
            "ar": "أقل من 0: أوراق خضراء ونشيطة · 0–0,1: بداية الاصفرار · أكثر من 0,1: اصفرار واضح أو شيخوخة أو جفاف.",
            "en": "< 0: green, active foliage · 0–0.1: yellowing begins · > 0.1: clear yellowing, senescence or "
                  "drying.",
        },
        "use": {
            "fr": "Repérer le jaunissement : maladie, carence, attaque de ravageurs, stress prolongé, mais aussi "
                  "maturité des cultures annuelles et chute des feuilles en automne.",
            "ar": "رصد الاصفرار: مرض، نقص في التسميد، هجوم حشرات، إجهاد طويل، وأيضًا نضج الزراعات السنوية وسقوط "
                  "الأوراق في الخريف.",
            "en": "Spot yellowing: disease, deficiency, pest attack, prolonged stress, but also ripening of annual "
                  "crops and autumn leaf fall.",
        },
    },
}
