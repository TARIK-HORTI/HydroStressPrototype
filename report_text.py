"""
report_text.py
==============
Textes du diagnostic et du rapport en français, arabe et anglais : classes de
stress, recommandations, conseils par culture, organismes à contacter, noms des
zones, des cultures, des sols et des modes d'irrigation.

Le modèle (predict.py) produit toujours ses textes en français (journal, JSON) ;
l'interface et le rapport HTML les reprennent ici dans la langue choisie.
"""

from typing import Any, Dict, List, Optional

LANG_FALLBACK = "fr"


def _pick(entry: Dict[str, str], lang: str) -> str:
    return entry.get(lang) or entry.get(LANG_FALLBACK, "")


# ---------------------------------------------------------------------------
# Zones, organismes, cultures, sols, irrigation
# ---------------------------------------------------------------------------
ZONE_NAMES = {
    "gharb": {"ar": "الغرب – اللوكوس", "en": "Gharb – Loukkos"},
    "sais": {"ar": "سايس – مكناس – فاس", "en": "Saïs – Meknes – Fez"},
    "tadla": {"ar": "تادلة – بني ملال", "en": "Tadla – Beni Mellal"},
    "haouz": {"ar": "الحوز – مراكش", "en": "Haouz – Marrakech"},
    "chaouia": {"ar": "الشاوية – دكالة", "en": "Chaouia – Doukkala"},
    "souss": {"ar": "سوس – ماسة", "en": "Souss – Massa"},
    "oriental": {"ar": "الشرق – ملوية", "en": "Oriental – Moulouya"},
    "errachidia": {"ar": "الرشيدية – تافيلالت", "en": "Errachidia – Tafilalet"},
    "draa": {"ar": "درعة – ورزازات – زاكورة", "en": "Drâa – Ouarzazate – Zagora"},
}

CONTACTS = {
    "gharb": {"ar": "المكتب الجهوي للاستثمار الفلاحي للغرب أو للوكوس", "en": "the ORMVA of Gharb or Loukkos"},
    "sais": {"ar": "المديرية الإقليمية للفلاحة بمكناس أو بفاس", "en": "the DPA (provincial agriculture office) of Meknes or Fez"},
    "tadla": {"ar": "المكتب الجهوي للاستثمار الفلاحي لتادلة", "en": "the ORMVA of Tadla"},
    "haouz": {"ar": "المكتب الجهوي للاستثمار الفلاحي للحوز", "en": "the ORMVA of Haouz"},
    "chaouia": {"ar": "المكتب الجهوي للاستثمار الفلاحي لدكالة أو المديرية الإقليمية للفلاحة بسطات",
                "en": "the ORMVA of Doukkala or the DPA of Settat"},
    "souss": {"ar": "المكتب الجهوي للاستثمار الفلاحي لسوس ماسة", "en": "the ORMVA of Souss-Massa"},
    "oriental": {"ar": "المكتب الجهوي للاستثمار الفلاحي لملوية", "en": "the ORMVA of Moulouya"},
    "errachidia": {"ar": "المكتب الجهوي للاستثمار الفلاحي لتافيلالت", "en": "the ORMVA of Tafilalet"},
    "draa": {"ar": "المكتب الجهوي للاستثمار الفلاحي لورزازات", "en": "the ORMVA of Ouarzazate"},
}
DEFAULT_CONTACT = {"fr": "l'ORMVA ou la DPA de votre zone", "ar": "المكتب الجهوي للاستثمار الفلاحي أو المديرية الإقليمية "
                   "للفلاحة في منطقتك", "en": "the ORMVA or DPA of your area"}

# Clé : nom français (region.CROPS et farm.CROPS)
CROP_NAMES = {
    "Agrumes": {"ar": "الحوامض", "en": "Citrus"},
    "Canne à sucre": {"ar": "قصب السكر", "en": "Sugar cane"},
    "Betterave sucrière": {"ar": "الشمندر السكري", "en": "Sugar beet"},
    "Riz": {"ar": "الأرز", "en": "Rice"},
    "Céréales (blé / orge)": {"ar": "الحبوب (القمح / الشعير)", "en": "Cereals (wheat / barley)"},
    "Maraîchage": {"ar": "الخضروات", "en": "Vegetables"},
    "Olivier": {"ar": "الزيتون", "en": "Olive"},
    "Vigne": {"ar": "الكروم (الدالية)", "en": "Grapevine"},
    "Arboriculture (pommier, prunier)": {"ar": "الأشجار المثمرة (التفاح، البرقوق)", "en": "Fruit trees (apple, plum)"},
    "Luzerne": {"ar": "الفصّة", "en": "Alfalfa"},
    "Légumineuses": {"ar": "القطاني", "en": "Legumes"},
    "Maraîchage sous serre": {"ar": "الخضروات في البيوت المغطاة", "en": "Greenhouse vegetables"},
    "Arganier": {"ar": "الأركان", "en": "Argan"},
    "Bananier": {"ar": "الموز", "en": "Banana"},
    "Palmier dattier": {"ar": "النخيل", "en": "Date palm"},
    "Rosier à parfum": {"ar": "الورد العطري", "en": "Damask rose"},
    "Amandier": {"ar": "اللوز", "en": "Almond"},
    "Pommier": {"ar": "التفاح", "en": "Apple"},
    "Grenadier": {"ar": "الرمان", "en": "Pomegranate"},
    "Avocatier": {"ar": "الأفوكا", "en": "Avocado"},
}

IRRIGATION_NAMES = {
    "goutte": {"fr": "Goutte-à-goutte", "ar": "التنقيط", "en": "Drip"},
    "aspersion": {"fr": "Aspersion", "ar": "الرش", "en": "Sprinkler"},
    "gravitaire": {"fr": "Gravitaire (seguia, submersion)", "ar": "السقي بالجاذبية (الساقية، الغمر)",
                   "en": "Surface (seguia, flooding)"},
    "pluvial": {"fr": "Pluvial (sans irrigation)", "ar": "بوري (بدون سقي)", "en": "Rain-fed (no irrigation)"},
}
SOIL_NAMES = {
    "sableux": {"fr": "Sableux", "ar": "رملية", "en": "Sandy"},
    "limoneux": {"fr": "Limoneux", "ar": "طميية", "en": "Loamy"},
    "argileux": {"fr": "Argileux", "ar": "طينية", "en": "Clay"},
}


def zone_name(zone_id: Optional[str], fr_name: str, lang: str) -> str:
    return ZONE_NAMES.get(zone_id or "", {}).get(lang) or fr_name


def crop_name(fr_name: str, lang: str) -> str:
    return CROP_NAMES.get(fr_name, {}).get(lang) or fr_name


def contact(zone_id: Optional[str], lang: str) -> str:
    from region import ZONES
    if lang == "fr":
        return ZONES[zone_id]["contact"] if zone_id in ZONES else DEFAULT_CONTACT["fr"]
    return CONTACTS.get(zone_id or "", {}).get(lang) or _pick(DEFAULT_CONTACT, lang)


# ---------------------------------------------------------------------------
# Classes de stress et indices
# ---------------------------------------------------------------------------
CLASS_TEXT = {
    0: {"label": {"fr": "Normal", "ar": "عادي", "en": "Normal"},
        "summary": {"fr": "La parcelle ne montre pas de stress hydrique marqué.",
                    "ar": "القطعة لا تُظهر إجهادًا مائيًا واضحًا.",
                    "en": "The plot shows no marked water stress."}},
    1: {"label": {"fr": "Modéré", "ar": "متوسط", "en": "Moderate"},
        "summary": {"fr": "Stress hydrique modéré : ajuster l'irrigation et surveiller.",
                    "ar": "إجهاد مائي متوسط: عدّل السقي وتابع القطعة.",
                    "en": "Moderate water stress: adjust irrigation and monitor."}},
    2: {"label": {"fr": "Sévère", "ar": "حادّ", "en": "Severe"},
        "summary": {"fr": "Stress hydrique sévère : intervention rapide recommandée.",
                    "ar": "إجهاد مائي حادّ: يُنصح بالتدخل بسرعة.",
                    "en": "Severe water stress: quick action recommended."}},
}

STATUS_TEXT = {
    "healthy": {"fr": "Normal", "ar": "عادي", "en": "Normal"},
    "low": {"fr": "Bas", "ar": "منخفض", "en": "Low"},
    "high": {"fr": "Élevé", "ar": "مرتفع", "en": "High"},
    "unknown": {"fr": "—", "ar": "—", "en": "—"},
}

INDEX_DESC = {
    "NDVI": {"fr": "Vigueur de la végétation", "ar": "قوة الغطاء النباتي", "en": "Vegetation vigour"},
    "NDWI": {"fr": "Contenu en eau végétale", "ar": "محتوى النبات من الماء", "en": "Plant water content"},
    "MSI": {"fr": "Stress hydrique (bas = sain)", "ar": "الإجهاد المائي (منخفض = سليم)", "en": "Water stress (low = healthy)"},
    "SAVI": {"fr": "NDVI corrigé du sol", "ar": "NDVI مصحَّح بأثر التربة", "en": "Soil-adjusted NDVI"},
    "EVI": {"fr": "Indice amélioré de végétation", "ar": "مؤشر الغطاء النباتي المحسَّن", "en": "Enhanced vegetation index"},
}

PRIORITY_TEXT = {
    "low": {"fr": "BASSE", "ar": "منخفضة", "en": "LOW"},
    "medium": {"fr": "MOYENNE", "ar": "متوسطة", "en": "MEDIUM"},
    "high": {"fr": "HAUTE", "ar": "عالية", "en": "HIGH"},
}


def class_label(idx: int, lang: str) -> str:
    return _pick(CLASS_TEXT[idx]["label"], lang)


def class_summary(idx: int, lang: str) -> str:
    return _pick(CLASS_TEXT[idx]["summary"], lang)


def status_label(status: str, lang: str) -> str:
    return _pick(STATUS_TEXT.get(status, STATUS_TEXT["unknown"]), lang)


def index_description(name: str, fallback: str, lang: str) -> str:
    return INDEX_DESC.get(name, {}).get(lang) or fallback


def priority_label(priority: str, lang: str) -> str:
    return _pick(PRIORITY_TEXT.get(priority, {"fr": priority.upper()}), lang)


# ---------------------------------------------------------------------------
# Recommandations (mêmes contenus que predict.RECOMMENDATIONS_DB et CROP_TIPS)
# ---------------------------------------------------------------------------
REC_TEXT = {
    0: {
        "title": {"fr": "Stress hydrique normal", "ar": "لا يوجد إجهاد مائي", "en": "Normal water status"},
        "actions": [
            {"fr": "Maintenir le calendrier d'irrigation actuel.", "ar": "حافظ على برنامج السقي الحالي.",
             "en": "Keep the current irrigation schedule."},
            {"fr": "Continuer le suivi des indices toutes les 1 à 2 semaines (revisite Sentinel-2 : 5 jours).",
             "ar": "واصل تتبّع المؤشرات كل أسبوع إلى أسبوعين (صورة Sentinel-2 جديدة كل 5 أيام).",
             "en": "Keep monitoring the indices every 1 to 2 weeks (Sentinel-2 revisit: 5 days)."},
            {"fr": "Anticiper les périodes chaudes (juin-septembre) : les besoins en eau augmentent fortement.",
             "ar": "استعدّ للفترات الحارة (يونيو-شتنبر): حاجيات الماء ترتفع بقوة.",
             "en": "Plan ahead for hot periods (June-September): water needs rise sharply."},
        ],
    },
    1: {
        "title": {"fr": "Stress hydrique modéré détecté", "ar": "تم رصد إجهاد مائي متوسط",
                  "en": "Moderate water stress detected"},
        "actions": [
            {"fr": "Rapprocher les irrigations : +20 à 30 % d'apport, de préférence tôt le matin ou le soir.",
             "ar": "قرّب مواعيد السقي: زيادة 20 إلى 30 % في كمية الماء، ويُفضَّل في الصباح الباكر أو في المساء.",
             "en": "Irrigate more often: +20 to 30 % water, preferably early morning or evening."},
            {"fr": "Vérifier le réseau d'irrigation (colmatage des goutteurs, pression, fuites, état des canaux).",
             "ar": "افحص شبكة السقي (انسداد القطّارات، الضغط، التسربات، حالة السواقي).",
             "en": "Check the irrigation network (clogged drippers, pressure, leaks, state of the channels)."},
            {"fr": "Pailler le sol (résidus de culture, paille) pour limiter l'évaporation.",
             "ar": "غطِّ التربة (بقايا المحاصيل، التبن) للحدّ من التبخر.",
             "en": "Mulch the soil (crop residues, straw) to limit evaporation."},
            {"fr": "Surveiller la parcelle tous les 2 à 3 jours.", "ar": "راقب القطعة كل يومين إلى ثلاثة أيام.",
             "en": "Monitor the plot every 2 to 3 days."},
        ],
    },
    2: {
        "title": {"fr": "Stress hydrique SÉVÈRE", "ar": "إجهاد مائي حادّ", "en": "SEVERE water stress"},
        "actions": [
            {"fr": "IRRIGATION PRIORITAIRE : augmenter les apports de +50 % dès que possible.",
             "ar": "السقي أولوية: زِد كمية الماء بـ 50 % في أقرب وقت.",
             "en": "PRIORITY IRRIGATION: increase water by +50 % as soon as possible."},
            {"fr": "Prioriser les cultures pérennes (arbres fruitiers, olivier, palmier) si l'eau est limitée.",
             "ar": "أعطِ الأولوية للزراعات الدائمة (الأشجار المثمرة، الزيتون، النخيل) إذا كان الماء محدودًا.",
             "en": "Give priority to perennial crops (fruit trees, olive, palm) if water is limited."},
            {"fr": "Contrôler le niveau du puits / forage et la salinité de l'eau d'irrigation.",
             "ar": "راقب مستوى البئر / الثقب وملوحة ماء السقي.",
             "en": "Check the well / borehole level and the salinity of irrigation water."},
        ],
    },
}

CONTACT_ACTION = {
    "fr": "Contacter {contact} ou un technicien agricole pour une visite terrain.",
    "ar": "اتصل بـ{contact} أو بتقني فلاحي لزيارة ميدانية.",
    "en": "Contact {contact} or an agricultural technician for a field visit.",
}

CROP_TIPS_TEXT = {
    "Palmier dattier": {
        "fr": "Palmier dattier : irriguer en cuvette au pied, surtout pendant la nouaison et le grossissement des dattes (avril-septembre).",
        "ar": "النخيل: اسقِ في الحوض عند قاعدة النخلة، خاصة خلال العقد ونمو التمر (أبريل-شتنبر).",
        "en": "Date palm: basin-irrigate at the foot, especially during fruit set and date growth (April-September)."},
    "Luzerne": {
        "fr": "Luzerne : éviter la coupe pendant le pic de stress et irriguer juste après chaque coupe.",
        "ar": "الفصّة: تجنّب الحشّ خلال ذروة الإجهاد واسقِ مباشرة بعد كل حشّة.",
        "en": "Alfalfa: avoid cutting during peak stress and irrigate right after each cut."},
    "Céréales (blé / orge)": {
        "fr": "Céréales : le stress au tallage et à l'épiaison (février-avril) a l'impact le plus fort sur le rendement ; une irrigation d'appoint à ces stades est la plus rentable.",
        "ar": "الحبوب: الإجهاد في مرحلتي الإشطاء والإسبال (فبراير-أبريل) هو الأكثر تأثيرًا على المردود؛ السقي التكميلي في هاتين المرحلتين هو الأكثر مردودية.",
        "en": "Cereals: stress at tillering and heading (February-April) hits yield hardest; supplementary irrigation at these stages pays best."},
    "Olivier": {
        "fr": "Olivier : un apport à la floraison et au grossissement des fruits limite la chute de production.",
        "ar": "الزيتون: السقي عند الإزهار ونمو الثمار يحدّ من انخفاض الإنتاج.",
        "en": "Olive: watering at flowering and fruit growth limits yield loss."},
    "Maraîchage": {
        "fr": "Maraîchage : passer à des irrigations courtes et fréquentes, ombrage léger aux heures chaudes.",
        "ar": "الخضروات: اعتمد سقيًا قصيرًا ومتكررًا، وتظليلًا خفيفًا في ساعات الحرارة.",
        "en": "Vegetables: switch to short, frequent irrigations, light shading in the hot hours."},
    "Maraîchage sous serre": {
        "fr": "Serre : aérer aux heures chaudes, fractionner la fertigation et contrôler la conductivité de la solution.",
        "ar": "البيت المغطى: هوِّ في ساعات الحرارة، وجزّئ التسميد مع السقي، وراقب ملوحة المحلول.",
        "en": "Greenhouse: ventilate in hot hours, split fertigation and check the solution's conductivity."},
    "Agrumes": {
        "fr": "Agrumes : un stress à la floraison et à la nouaison (mars-juin) fait chuter les fruits ; maintenir une humidité du sol régulière.",
        "ar": "الحوامض: الإجهاد عند الإزهار والعقد (مارس-يونيو) يُسقط الثمار؛ حافظ على رطوبة منتظمة للتربة.",
        "en": "Citrus: stress at flowering and fruit set (March-June) makes fruit drop; keep soil moisture steady."},
    "Betterave sucrière": {
        "fr": "Betterave : les besoins sont maximaux en avril-mai ; ne pas espacer les tours d'eau pendant cette phase.",
        "ar": "الشمندر: الحاجة إلى الماء في أقصاها في أبريل-ماي؛ لا تباعد بين دورات السقي في هذه المرحلة.",
        "en": "Sugar beet: needs peak in April-May; do not space out irrigation turns in this phase."},
    "Canne à sucre": {
        "fr": "Canne à sucre : maintenir des apports réguliers en été, période de forte croissance.",
        "ar": "قصب السكر: حافظ على سقي منتظم في الصيف، فترة النمو القوي.",
        "en": "Sugar cane: keep regular irrigation in summer, the period of strong growth."},
    "Riz": {
        "fr": "Riz : maintenir la lame d'eau ; un assec pendant la floraison réduit fortement le rendement.",
        "ar": "الأرز: حافظ على طبقة الماء؛ الجفاف خلال الإزهار يخفض المردود بقوة.",
        "en": "Rice: keep the water layer; drying out at flowering cuts yield sharply."},
    "Vigne": {
        "fr": "Vigne : un stress modéré après la véraison est tolérable, mais pas pendant la floraison et la nouaison.",
        "ar": "الكروم: إجهاد متوسط بعد تلوّن العنب مقبول، لكن ليس خلال الإزهار والعقد.",
        "en": "Grapevine: moderate stress after veraison is tolerable, but not during flowering and fruit set."},
    "Arboriculture (pommier, prunier)": {
        "fr": "Arbres fruitiers : sécuriser l'irrigation pendant le grossissement des fruits (mai-août).",
        "ar": "الأشجار المثمرة: أمّن السقي خلال نمو الثمار (ماي-غشت).",
        "en": "Fruit trees: secure irrigation during fruit growth (May-August)."},
    "Arganier": {
        "fr": "Arganier : très résistant à la sécheresse ; un apport d'appoint ne se justifie que pour les jeunes plants.",
        "ar": "الأركان: مقاوم جدًا للجفاف؛ السقي التكميلي لا يُبرَّر إلا للشتلات الصغيرة.",
        "en": "Argan: very drought tolerant; supplementary watering is only justified for young plants."},
    "Bananier": {
        "fr": "Bananier (sous serre) : besoins très élevés, irrigation quotidienne et contrôle de l'humidité de l'air.",
        "ar": "الموز (في البيوت المغطاة): حاجيات مرتفعة جدًا، سقي يومي ومراقبة رطوبة الهواء.",
        "en": "Banana (greenhouse): very high needs, daily irrigation and control of air humidity."},
    "Légumineuses": {
        "fr": "Légumineuses : sensibles au stress à la floraison ; une irrigation d'appoint sécurise la gousse.",
        "ar": "القطاني: حساسة للإجهاد عند الإزهار؛ السقي التكميلي يؤمّن القرون.",
        "en": "Legumes: sensitive to stress at flowering; supplementary irrigation secures the pods."},
    "Rosier à parfum": {
        "fr": "Rosier à parfum : sécuriser l'irrigation en mars-avril, avant et pendant la floraison.",
        "ar": "الورد العطري: أمّن السقي في مارس-أبريل، قبل الإزهار وخلاله.",
        "en": "Damask rose: secure irrigation in March-April, before and during flowering."},
}


def localized_recommendations(class_idx: int, crop: Optional[str], zone_id: Optional[str], priority: str,
                              lang: str) -> Dict[str, Any]:
    """Recommandations du diagnostic dans la langue voulue (même logique que predict.get_recommendations)."""
    rec = REC_TEXT.get(class_idx, REC_TEXT[0])
    actions: List[str] = [_pick(a, lang) for a in rec["actions"]]
    if crop and class_idx > 0 and crop in CROP_TIPS_TEXT:
        actions.append(_pick(CROP_TIPS_TEXT[crop], lang))
    if class_idx == 2:
        actions.append(_pick(CONTACT_ACTION, lang).format(contact=contact(zone_id, lang)))
    return {"title": _pick(rec["title"], lang), "actions": actions, "priority": priority_label(priority, lang)}
