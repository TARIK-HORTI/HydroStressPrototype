"""
imagery_text.py
===============
Textes des cartes satellite en français, arabe et anglais : volets, couches et
interprétation automatique du changement entre deux dates (utilisés par imagery.py).
"""

from typing import Dict

THEME_TEXT: Dict[str, Dict[str, str]] = {
    "water": {"fr": "💧 Stress hydrique", "ar": "💧 الإجهاد المائي", "en": "💧 Water stress"},
    "health": {"fr": "🩺 État sanitaire", "ar": "🩺 الحالة الصحية", "en": "🩺 Plant health"},
    "growth": {"fr": "🌱 Développement de la végétation", "ar": "🌱 نموّ الغطاء النباتي", "en": "🌱 Vegetation growth"},
    "rgb": {"fr": "🛰️ Image réelle", "ar": "🛰️ الصورة الحقيقية", "en": "🛰️ True colour"},
}

# label, description, low, high (le français est aussi dans imagery.LAYERS)
LAYER_TEXT: Dict[str, Dict[str, Dict[str, str]]] = {
    "NDMI": {
        "label": {"ar": "NDMI · الماء في الأوراق", "en": "NDMI · water in the leaves"},
        "description": {
            "ar": "محتوى الأوراق من الماء. انخفاضه بين تاريخين دون انخفاض NDVI يشير إلى نقص الماء قبل أن تصفرّ الأشجار.",
            "en": "Water content of the foliage (NIR / SWIR). A drop between two dates without an NDVI drop signals "
                  "a water shortage before trees turn yellow.",
        },
        "low": {"ar": "أوراق جافة", "en": "dry foliage"},
        "high": {"ar": "مرتوية جيدًا", "en": "well watered"},
    },
    "MSI": {
        "label": {"ar": "MSI · مؤشر الإجهاد المائي", "en": "MSI · moisture stress index"},
        "description": {"ar": "كلما ارتفع، زاد نقص الماء عند النبات.",
                        "en": "SWIR / NIR: the higher it is, the more the vegetation lacks water."},
        "low": {"ar": "بدون إجهاد", "en": "no stress"},
        "high": {"ar": "إجهاد قوي", "en": "severe stress"},
    },
    "NDRE": {
        "label": {"ar": "NDRE · الكلوروفيل", "en": "NDRE · chlorophyll"},
        "description": {
            "ar": "نطاق الحافة الحمراء، حسّاس للكلوروفيل والأزوت: ينخفض قبل NDVI عند نقص التسميد أو المرض أو ضعف الأشجار.",
            "en": "Red-edge band, sensitive to chlorophyll and nitrogen: drops before NDVI with a deficiency, "
                  "disease or decline.",
        },
        "low": {"ar": "كلوروفيل قليل", "en": "low chlorophyll"},
        "high": {"ar": "أوراق سليمة", "en": "healthy foliage"},
    },
    "PSRI": {
        "label": {"ar": "PSRI · الاصفرار / الشيخوخة", "en": "PSRI · yellowing / senescence"},
        "description": {
            "ar": "نسبة الصبغات الصفراء إلى الكلوروفيل: يرتفع عندما تصفرّ الأوراق (مرض، نقص تسميد، شيخوخة، سقوط الأوراق).",
            "en": "Carotenoid / chlorophyll ratio: rises when leaves turn yellow (disease, deficiency, senescence, "
                  "leaf fall).",
        },
        "low": {"ar": "أوراق خضراء", "en": "green foliage"},
        "high": {"ar": "اصفرار", "en": "yellowing"},
    },
    "NDVI": {
        "label": {"ar": "NDVI · القوة والغطاء", "en": "NDVI · vigour and cover"},
        "description": {"ar": "كثافة الغطاء النباتي وقوته: يتتبّع نموّ الأشجار والزراعات.",
                        "en": "Density and vigour of the plant cover: tracks the growth of trees and crops."},
        "low": {"ar": "تربة عارية", "en": "bare soil"},
        "high": {"ar": "نبات كثيف", "en": "dense vegetation"},
    },
    "NDVI_ANOM": {
        "label": {"ar": "شذوذ NDVI مقارنة بالسنوات الماضية", "en": "NDVI anomaly vs previous years"},
        "description": {
            "ar": "NDVI في التاريخ ناقص وسيط نفس الأسابيع في السنوات السابقة (حتى 5 سنوات): الأحمر = نبات أضعف من "
                  "المعتاد في هذه الفترة.",
            "en": "NDVI on the date minus the median of the same weeks in previous years (up to 5 years): red = "
                  "vegetation less developed than usual for this time of year.",
        },
        "low": {"ar": "متأخر", "en": "behind"},
        "high": {"ar": "متقدّم", "en": "ahead"},
    },
    "NDVI_ZONES": {
        "label": {"ar": "المناطق الضعيفة في القطعة", "en": "Weak zones of the plot"},
        "description": {
            "ar": "فرق NDVI كل نقطة (10 م) عن وسيط القطعة، بالنسبة المئوية: يحدّد الخطوط أو الأشجار المتأخرة، "
                  "أو تسرّبًا أو انسدادًا في التنقيط.",
            "en": "Gap between each pixel's NDVI (10 m) and the plot median, in %: finds lagging rows or trees, a "
                  "leak or a clogged drip line.",
        },
        "low": {"ar": "‎-30 % عن القطعة", "en": "-30 % vs plot"},
        "high": {"ar": "‎+30 % عن القطعة", "en": "+30 % vs plot"},
    },
    "RGB": {
        "label": {"ar": "الألوان الطبيعية", "en": "Natural colours"},
        "description": {"ar": "صورة Sentinel-2 كما تُرى من الفضاء (10 م).",
                        "en": "Sentinel-2 image as seen from space (10 m)."},
        "low": {"ar": "", "en": ""},
        "high": {"ar": "", "en": ""},
    },
}

DIFF_TEXT = {
    "down": {"fr": "baisse", "ar": "انخفاض", "en": "decrease"},
    "up": {"fr": "hausse", "ar": "ارتفاع", "en": "increase"},
    "down_good": {"fr": "baisse (mieux)", "ar": "انخفاض (أفضل)", "en": "decrease (better)"},
    "up_bad": {"fr": "hausse (pire)", "ar": "ارتفاع (أسوأ)", "en": "increase (worse)"},
}

# ---------------------------------------------------------------------------
# Interprétation : une entrée par phrase, {fr, ar, en}
# ---------------------------------------------------------------------------
INTERP: Dict[str, Dict[str, str]] = {
    "sep": {"fr": ", ", "ar": "، ", "en": ", "},
    "headline_order": {"fr": "La date A est postérieure à la date B : inversez les dates.",
                       "ar": "التاريخ A بعد التاريخ B: اعكس التاريخين.",
                       "en": "Date A is after date B: swap the dates."},
    "headline_better": {"fr": "La parcelle s'est améliorée entre les deux dates.",
                        "ar": "تحسّنت القطعة بين التاريخين.",
                        "en": "The plot improved between the two dates."},
    "headline_stable": {"fr": "Pas de changement notable de la parcelle entre les deux dates.",
                        "ar": "لا يوجد تغيّر ملحوظ في القطعة بين التاريخين.",
                        "en": "No notable change in the plot between the two dates."},
    "headline_patchy": {
        "fr": "La moyenne de la parcelle tient, mais certaines zones reculent : repérez-les sur la carte du "
              "changement B − A.",
        "ar": "متوسط القطعة ثابت، لكن بعض المناطق تراجعت: حدّدها على خريطة التغيّر B − A.",
        "en": "The plot average holds, but some zones are declining: find them on the B − A change map.",
    },
    "headline_worse": {"fr": "La parcelle a reculé{where} : {signs}.", "ar": "تراجعت القطعة{where}: {signs}.",
                       "en": "The plot declined{where}: {signs}."},
    "where_general": {"fr": " sur la plus grande partie de la parcelle", "ar": " في معظم أجزائها",
                      "en": " over most of its area"},
    "where_patchy": {"fr": " par taches", "ar": " في بقع متفرّقة", "en": " in patches"},
    "sign_vigor": {"fr": "baisse de vigueur", "ar": "انخفاض في القوة", "en": "loss of vigour"},
    "sign_water": {"fr": "perte d'eau du feuillage", "ar": "فقدان الماء في الأوراق", "en": "loss of leaf water"},
    "sign_chloro": {"fr": "baisse de chlorophylle", "ar": "انخفاض الكلوروفيل", "en": "loss of chlorophyll"},
    "sign_yellow": {"fr": "jaunissement", "ar": "اصفرار", "en": "yellowing"},
    "obs_line": {"fr": "{k} : {a} → {b} ({d}, {label})", "ar": "{k}: {a} ← {b} ({d}، {label})",
                 "en": "{k}: {a} → {b} ({d}, {label})"},
    "obs_frac": {
        "fr": "Part de la parcelle en baisse : NDVI {ndvi}, NDMI {ndmi}, NDRE {ndre} ; jaunissement (PSRI en "
              "hausse) sur {psri}.",
        "ar": "نسبة القطعة المتراجعة: NDVI {ndvi}، NDMI {ndmi}، NDRE {ndre}؛ الاصفرار (ارتفاع PSRI) على {psri}.",
        "en": "Share of the plot declining: NDVI {ndvi}, NDMI {ndmi}, NDRE {ndre}; yellowing (PSRI rising) on {psri}.",
    },
    # Hypothèses : titre (t_), détail (d_), vérifications (c_)
    "t_growth": {"fr": "Croissance ou reprise de la végétation", "ar": "نموّ أو انتعاش الغطاء النباتي",
                 "en": "Vegetation growth or recovery"},
    "d_growth": {
        "fr": "Hausse de vigueur, d'eau ou de chlorophylle : développement normal de la culture, feuillaison, "
              "reprise après une irrigation, une pluie ou une fertilisation.",
        "ar": "ارتفاع في القوة أو الماء أو الكلوروفيل: نموّ عادي للزراعة، تورّق، أو انتعاش بعد سقي أو مطر أو تسميد.",
        "en": "Higher vigour, water or chlorophyll: normal crop development, leaf-out, recovery after irrigation, "
              "rain or fertilisation.",
    },
    "t_weeds": {"fr": "Développement d'adventices (mauvaises herbes)", "ar": "نموّ الأعشاب الضارة",
                "en": "Weed growth"},
    "d_weeds": {"fr": "Entre les rangs, l'herbe fait aussi monter le NDVI sans que les arbres aillent mieux.",
                "ar": "العشب بين الخطوط يرفع NDVI أيضًا دون أن تتحسّن الأشجار.",
                "en": "Grass between rows also raises NDVI without the trees doing any better."},
    "c_weeds": {"fr": "Regarder si l'inter-rang est enherbé.", "ar": "تحقّق من وجود العشب بين الخطوط.",
                "en": "Check whether the inter-row is grassy."},
    "t_stable": {"fr": "Situation stable", "ar": "وضع مستقر", "en": "Stable situation"},
    "d_stable": {"fr": "Les indices restent dans la marge normale de variation.",
                 "ar": "المؤشرات تبقى داخل هامش التغيّر العادي.",
                 "en": "Indices stay within their normal range of variation."},
    "c_stable": {"fr": "Continuer la surveillance : comparer de nouveau dans 2 à 3 semaines.",
                 "ar": "واصل المراقبة: قارن من جديد بعد 2 إلى 3 أسابيع.",
                 "en": "Keep monitoring: compare again in 2 to 3 weeks."},
    "t_leaf_fall": {"fr": "Chute naturelle des feuilles (repos hivernal)", "ar": "سقوط طبيعي للأوراق (الراحة الشتوية)",
                    "en": "Natural leaf fall (winter dormancy)"},
    "d_leaf_fall": {
        "fr": "La culture ({crop}) perd ses feuilles en automne-hiver : NDVI et NDRE baissent et le PSRI monte chaque "
              "année à cette période, sans problème.",
        "ar": "هذه الزراعة ({crop}) تفقد أوراقها في الخريف والشتاء: ينخفض NDVI وNDRE ويرتفع PSRI كل سنة في هذه الفترة "
              "دون أي مشكل.",
        "en": "This crop ({crop}) sheds its leaves in autumn-winter: NDVI and NDRE drop and PSRI rises every year at "
              "this time, with no problem.",
    },
    "c_leaf_fall": {
        "fr": "Comparer avec la carte « Anomalie NDVI » : si la baisse est la même que les autres années, c'est le "
              "cycle normal.",
        "ar": "قارن مع خريطة «شذوذ NDVI»: إذا كان الانخفاض مثل السنوات الأخرى فهي الدورة العادية.",
        "en": "Compare with the “NDVI anomaly” map: if the drop matches other years, it is the normal cycle.",
    },
    "t_harvest": {"fr": "Maturité, récolte ou fauche", "ar": "النضج أو الحصاد أو الحشّ", "en": "Ripening, harvest or cut"},
    "d_harvest": {
        "fr": "Une culture qui mûrit, est récoltée ou fauchée (luzerne) fait chuter les indices sur toute la parcelle.",
        "ar": "الزراعة التي تنضج أو تُحصد أو تُحشّ (الفصّة) تُسقط المؤشرات على كل القطعة.",
        "en": "A crop that ripens, is harvested or cut (alfalfa) makes indices fall over the whole plot.",
    },
    "c_harvest": {"fr": "Vérifier le calendrier de récolte ou de coupe entre les deux dates.",
                  "ar": "تحقّق من مواعيد الحصاد أو الحشّ بين التاريخين.",
                  "en": "Check the harvest or cutting schedule between the two dates."},
    "t_pruning": {"fr": "Taille, désherbage ou travail du sol", "ar": "التقليم أو إزالة الأعشاب أو حرث التربة",
                  "en": "Pruning, weeding or tillage"},
    "d_pruning": {
        "fr": "Une taille sévère ou la suppression de l'herbe entre les rangs fait baisser le NDVI sans que les arbres "
              "souffrent.",
        "ar": "التقليم القوي أو إزالة العشب بين الخطوط يُخفض NDVI دون أن تعاني الأشجار.",
        "en": "Heavy pruning or removing grass between rows lowers NDVI without the trees suffering.",
    },
    "c_pruning": {"fr": "Vérifier les travaux réalisés entre les deux dates.",
                  "ar": "تحقّق من الأشغال التي أُنجزت بين التاريخين.",
                  "en": "Check the work done between the two dates."},
    "t_water": {"fr": "Stress hydrique", "ar": "إجهاد مائي", "en": "Water stress"},
    "d_water": {
        "fr": "Le feuillage contient moins d'eau. Causes fréquentes : apports d'irrigation insuffisants pour la "
              "demande (chaleur, chergui, vent), panne de pompe ou coupure d'eau, goutteurs bouchés, fuites, pression "
              "trop faible en bout de ligne, salinité de l'eau ou du sol.",
        "ar": "الأوراق تحتوي على ماء أقل. أسباب شائعة: كمية السقي غير كافية مقارنة بالحاجة (الحرارة، الشرقي، الريح)، "
              "عطل في المضخة أو انقطاع الماء، قطّارات مسدودة، تسرّبات، ضغط ضعيف في نهاية الخطوط، ملوحة الماء أو التربة.",
        "en": "The foliage holds less water. Common causes: irrigation below crop demand (heat, chergui wind, wind), "
              "pump failure or water cut, clogged drippers, leaks, low pressure at the end of lines, saline water "
              "or soil.",
    },
    "c_water_1": {"fr": "Contrôler la pompe, la pression et le débit des goutteurs, surtout en bout de ligne.",
                  "ar": "راقب المضخة والضغط وصبيب القطّارات، خاصة في نهاية الخطوط.",
                  "en": "Check the pump, pressure and dripper flow, especially at the end of lines."},
    "c_water_2": {"fr": "Sonder l'humidité du sol à 30–60 cm (tarière) dans les zones en recul et dans une zone saine.",
                  "ar": "قِس رطوبة التربة على عمق 30–60 سم (بالمثقب) في المناطق المتراجعة وفي منطقة سليمة.",
                  "en": "Probe soil moisture at 30–60 cm (auger) in declining zones and in a healthy zone."},
    "c_water_3": {"fr": "Comparer avec le registre d'irrigation et la météo (pic de chaleur, vent).",
                  "ar": "قارن مع سجل السقي والطقس (موجة حرّ، ريح).",
                  "en": "Compare with the irrigation log and the weather (heat wave, wind)."},
    "t_health": {"fr": "Problème sanitaire : maladie ou ravageur", "ar": "مشكل صحي: مرض أو حشرة",
                 "en": "Health problem: disease or pest"},
    "d_health": {
        "fr": "Chlorophylle en baisse ou jaunissement sans perte d'eau marquée : peut venir d'une maladie (champignon, "
              "bactérie, virus), d'une attaque de ravageurs (acariens, pucerons, cochenilles, chenilles, scolytes) "
              "ou de nématodes au niveau des racines.",
        "ar": "انخفاض الكلوروفيل أو اصفرار دون فقدان واضح للماء: قد يكون بسبب مرض (فطر، بكتيريا، فيروس)، أو هجوم "
              "حشرات (العنكبوت الأحمر، المنّ، القرمزيات، اليرقات، حفّارات الخشب) أو ديدان خيطية في الجذور.",
        "en": "Falling chlorophyll or yellowing without marked water loss: may come from a disease (fungus, "
              "bacteria, virus), a pest attack (mites, aphids, scale insects, caterpillars, bark beetles) or root "
              "nematodes.",
    },
    "c_health_1": {
        "fr": "Observer les feuilles (dessus et dessous), les rameaux et le tronc dans les zones en recul : taches, "
              "déformations, insectes, toiles, gomme, galeries.",
        "ar": "افحص الأوراق (الوجه والظهر) والأغصان والجذع في المناطق المتراجعة: بقع، تشوّهات، حشرات، خيوط، صمغ، أنفاق.",
        "en": "Inspect leaves (top and underside), shoots and trunk in declining zones: spots, deformation, insects, "
              "webbing, gum, galleries.",
    },
    "c_health_2": {"fr": "Prendre des photos et des échantillons pour un conseiller agricole ou un laboratoire.",
                   "ar": "التقط صورًا وخذ عيّنات لمستشار فلاحي أو مختبر.",
                   "en": "Take photos and samples for an agricultural advisor or a laboratory."},
    "t_deficiency": {"fr": "Carence nutritionnelle", "ar": "نقص في التغذية", "en": "Nutrient deficiency"},
    "d_deficiency": {
        "fr": "Une carence en azote ou une chlorose ferrique (fréquente sur sols calcaires) fait baisser le NDRE et "
              "jaunir les feuilles.",
        "ar": "نقص الأزوت أو الاصفرار الحديدي (شائع في التربة الكلسية) يُخفض NDRE ويُصفّر الأوراق.",
        "en": "Nitrogen deficiency or iron chlorosis (common on calcareous soils) lowers NDRE and yellows the leaves.",
    },
    "c_deficiency": {"fr": "Vérifier le programme de fertilisation ; analyse foliaire ou de sol si le doute persiste.",
                     "ar": "راجع برنامج التسميد؛ وقم بتحليل الأوراق أو التربة إذا استمر الشك.",
                     "en": "Review the fertilisation programme; leaf or soil analysis if in doubt."},
    "t_decline": {"fr": "Stress prolongé ou dépérissement", "ar": "إجهاد طويل أو ضعف الأشجار",
                  "en": "Prolonged stress or tree decline"},
    "d_decline": {
        "fr": "Perte d'eau et de chlorophylle ensemble : stress hydrique installé depuis un moment, asphyxie ou "
              "pourriture des racines, salinité, ou attaque qui affaiblit les arbres (maladie du bois, scolytes).",
        "ar": "فقدان الماء والكلوروفيل معًا: إجهاد مائي منذ مدة، اختناق أو تعفّن الجذور، ملوحة، أو هجوم يُضعف الأشجار "
              "(مرض الخشب، حفّارات الخشب).",
        "en": "Loss of water and chlorophyll together: long-standing water stress, root asphyxia or rot, salinity, "
              "or an attack weakening the trees (wood disease, bark beetles).",
    },
    "c_decline": {"fr": "Examiner les racines et le collet de quelques arbres en recul.",
                  "ar": "افحص الجذور وعنق الساق لبعض الأشجار المتراجعة.",
                  "en": "Examine the roots and collar of a few declining trees."},
    "t_local": {"fr": "Problème localisé", "ar": "مشكل في أماكن محدّدة", "en": "Localised problem"},
    "d_local": {
        "fr": "Une baisse par taches oriente vers une cause localisée : secteur ou ligne d'irrigation, goutteurs "
              "bouchés, zone de sol différente (sable, calcaire, sel), foyer de maladie ou de ravageurs qui démarre, "
              "arbres morts ou arrachés.",
        "ar": "التراجع في بقع يشير إلى سبب محلّي: قطاع أو خط سقي، قطّارات مسدودة، تربة مختلفة (رمل، كلس، ملح)، بداية "
              "بؤرة مرض أو حشرات، أشجار ميتة أو مقلوعة.",
        "en": "A patchy decline points to a local cause: irrigation sector or line, clogged drippers, different soil "
              "(sand, limestone, salt), an emerging disease or pest hotspot, dead or removed trees.",
    },
    "c_local": {
        "fr": "Aller d'abord dans les zones rouges de la carte du changement B − A, puis comparer avec une zone "
              "restée verte.",
        "ar": "اذهب أولًا إلى المناطق الحمراء في خريطة التغيّر B − A، ثم قارنها مع منطقة بقيت خضراء.",
        "en": "Go first to the red zones of the B − A change map, then compare with a zone that stayed green.",
    },
    "t_generic": {"fr": "Recul modéré de la végétation", "ar": "تراجع معتدل للغطاء النباتي",
                  "en": "Moderate vegetation decline"},
    "d_generic": {
        "fr": "Le recul est réel mais ne correspond pas à un profil net : plusieurs causes peuvent se mêler.",
        "ar": "التراجع حقيقي لكنه لا يطابق نمطًا واضحًا: قد تتداخل عدة أسباب.",
        "en": "The decline is real but does not match a clear pattern: several causes may combine.",
    },
    "c_generic": {"fr": "Visiter la parcelle en commençant par les zones rouges de la carte du changement.",
                  "ar": "زُر القطعة بدءًا بالمناطق الحمراء في خريطة التغيّر.",
                  "en": "Visit the plot starting with the red zones of the change map."},
    "note_close": {
        "fr": "Les deux dates sont proches (moins de 10 jours) : les petits écarts peuvent venir de l'atmosphère ou de "
              "l'angle de prise de vue.",
        "ar": "التاريخان متقاربان (أقل من 10 أيام): الفروق الصغيرة قد تأتي من الغلاف الجوي أو زاوية التصوير.",
        "en": "The two dates are close (under 10 days): small differences may come from the atmosphere or the "
              "viewing angle.",
    },
    "note_far": {
        "fr": "Plus de 4 mois séparent les deux dates : une partie du changement est saisonnière. La carte « Anomalie "
              "NDVI » aide à séparer le saisonnier de l'anormal.",
        "ar": "أكثر من 4 أشهر بين التاريخين: جزء من التغيّر موسمي. خريطة «شذوذ NDVI» تساعد على التمييز بين الموسمي "
              "وغير العادي.",
        "en": "More than 4 months between the two dates: part of the change is seasonal. The “NDVI anomaly” map "
              "helps separate seasonal from abnormal.",
    },
    "note_evergreen": {
        "fr": "La culture ({crop}) garde ses feuilles : une baisse en automne-hiver n'est pas due à la chute des "
              "feuilles.",
        "ar": "هذه الزراعة ({crop}) تحتفظ بأوراقها: الانخفاض في الخريف والشتاء ليس بسبب سقوط الأوراق.",
        "en": "This crop ({crop}) keeps its leaves: an autumn-winter drop is not due to leaf fall.",
    },
    "crop_unknown": {"fr": "non précisée", "ar": "غير محدّدة", "en": "not specified"},
    "disclaimer": {
        "fr": "Cette lecture est automatique et indicative. Le satellite mesure un changement de couleur, d'eau ou de "
              "chlorophylle du feuillage ; il ne voit ni l'insecte, ni le champignon, ni le goutte-à-goutte bouché. "
              "Plusieurs causes donnent la même image : seule une visite au champ (et si besoin l'avis d'un "
              "conseiller agricole ou d'un laboratoire) permet de conclure.",
        "ar": "هذا التفسير آلي وإرشادي. القمر الصناعي يقيس تغيّر لون الأوراق أو ماءها أو الكلوروفيل؛ لا يرى الحشرة ولا "
              "الفطر ولا القطّارة المسدودة. أسباب مختلفة قد تعطي نفس الصورة: وحدها زيارة الحقل (وعند الحاجة رأي "
              "مستشار فلاحي أو مختبر) تسمح بالحكم.",
        "en": "This reading is automatic and indicative. The satellite measures a change in leaf colour, water or "
              "chlorophyll; it cannot see the insect, the fungus or the clogged dripper. Several causes produce the "
              "same image: only a field visit (and if needed an agricultural advisor or a laboratory) can conclude.",
    },
}
