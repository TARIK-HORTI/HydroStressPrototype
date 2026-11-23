"""
i18n_pages.py
=============
Textes du rapport d'analyse, de la validation météo, des sections du bas de page
(modèle, simulation, contributions, entraînement sur une ferme) et de la légende de
la carte, en français, arabe et anglais. Utilisés via i18n.t().
"""

from typing import Dict

PAGES: Dict[str, Dict[str, str]] = {
    # --- Carte : légende des points --------------------------------------------------------------
    "map_legend": {
        "fr": "Les points colorés sur la carte sont les <b>localités de référence</b> des 9 zones agricoles : "
              "la couleur indique la zone. Survolez un point pour voir son nom. Votre parcelle est rattachée à la "
              "zone du point le plus proche, qui fixe les seuils, les cultures proposées et l'organisme à contacter.",
        "ar": "النقط الملوّنة على الخريطة هي <b>الأماكن المرجعية</b> للمناطق الفلاحية التسع: اللون يدل على المنطقة. "
              "مرّر الفأرة فوق نقطة لترى اسمها. تُلحق قطعتك بمنطقة أقرب نقطة، وهي التي تحدّد العتبات والزراعات "
              "المقترحة والجهة التي يجب الاتصال بها.",
        "en": "The coloured dots on the map are the <b>reference localities</b> of the 9 farming areas: the colour "
              "shows the area. Hover over a dot to see its name. Your plot is linked to the area of the nearest dot, "
              "which sets the thresholds, suggested crops and the office to contact.",
    },
    # --- Analyse ---------------------------------------------------------------------------------
    "an_running": {"fr": "Analyse de la parcelle en cours…", "ar": "جارٍ تحليل القطعة…", "en": "Analysing the plot…"},
    "an_validate": {"fr": "Validation de la parcelle", "ar": "التحقق من القطعة", "en": "Checking the plot"},
    "an_demo": {"fr": "Génération des données de démonstration", "ar": "إنشاء بيانات للعرض", "en": "Generating demo data"},
    "an_connect": {"fr": "Connexion à Google Earth Engine", "ar": "الاتصال بـ Google Earth Engine",
                   "en": "Connecting to Google Earth Engine"},
    "an_extract": {"fr": "Extraction Sentinel-2, CHIRPS et ERA5-Land (30 à 90 s)",
                   "ar": "استخراج بيانات Sentinel-2 وCHIRPS وERA5-Land (من 30 إلى 90 ثانية)",
                   "en": "Extracting Sentinel-2, CHIRPS and ERA5-Land (30 to 90 s)"},
    "an_predict": {"fr": "Prédiction du stress hydrique", "ar": "توقّع الإجهاد المائي", "en": "Predicting water stress"},
    "an_done": {"fr": "Analyse terminée", "ar": "انتهى التحليل", "en": "Analysis complete"},
    "an_failed": {"fr": "Analyse impossible", "ar": "تعذّر التحليل", "en": "Analysis failed"},
    "an_error": {"fr": "Erreur : {msg}", "ar": "خطأ: {msg}", "en": "Error: {msg}"},
    "an_ee_hint": {
        "fr": " — Vérifiez l'accès Earth Engine : secret GCP_SERVICE_ACCOUNT_JSON sur Streamlit Cloud (voir README).",
        "ar": " — تحقّق من الولوج إلى Earth Engine: السرّ GCP_SERVICE_ACCOUNT_JSON في Streamlit Cloud (انظر README).",
        "en": " — Check Earth Engine access: GCP_SERVICE_ACCOUNT_JSON secret on Streamlit Cloud (see README).",
    },
    "zone_near": {"fr": "{zone} (près de {place})", "ar": "{zone} (قرب {place})", "en": "{zone} (near {place})"},
    # --- Rapport ---------------------------------------------------------------------------------
    "rp_title": {"fr": "Rapport d'analyse", "ar": "تقرير التحليل", "en": "Analysis report"},
    "rp_demo": {
        "fr": "⚠ Données de démonstration : ce rapport montre le fonctionnement du tableau de bord, les valeurs ne "
              "viennent pas des satellites pour cette parcelle.",
        "ar": "⚠ بيانات للعرض: هذا التقرير يوضّح طريقة عمل اللوحة، والقيم ليست من الأقمار الصناعية لهذه القطعة.",
        "en": "⚠ Demo data: this report shows how the dashboard works; the values do not come from satellites for "
              "this plot.",
    },
    "rp_level": {"fr": "Niveau de stress hydrique", "ar": "مستوى الإجهاد المائي", "en": "Water stress level"},
    "rp_conf_line": {
        "fr": "Confiance {conf:.1f} % · {zone} · {crop} · {date}<br>Parcelle de {ha} ha · centre {lat}, {lon}",
        "ar": "الثقة {conf:.1f} % · {zone} · {crop} · {date}<br>قطعة مساحتها {ha} هكتار · المركز {lat}، {lon}",
        "en": "Confidence {conf:.1f} % · {zone} · {crop} · {date}<br>Plot of {ha} ha · centre {lat}, {lon}",
    },
    "rp_probs": {"fr": "Probabilités", "ar": "الاحتمالات", "en": "Probabilities"},
    "kpi_ndvi": {"fr": "NDVI · vigueur", "ar": "NDVI · القوة", "en": "NDVI · vigour"},
    "kpi_ndwi": {"fr": "NDWI · eau foliaire", "ar": "NDWI · ماء الأوراق", "en": "NDWI · leaf water"},
    "kpi_msi": {"fr": "MSI · stress", "ar": "MSI · الإجهاد", "en": "MSI · stress"},
    "kpi_rain30": {"fr": "Pluie 30 jours", "ar": "الأمطار 30 يومًا", "en": "Rain, 30 days"},
    "kpi_tmax30": {"fr": "T° max 30 jours", "ar": "الحرارة القصوى 30 يومًا", "en": "Max temp., 30 days"},
    "kpi_dry": {"fr": "Jours secs consécutifs", "ar": "أيام جافة متتالية", "en": "Consecutive dry days"},
    "rp_s2": {
        "fr": "Composite Sentinel-2 de {n} image(s) sur {d} jours · {v} de pixels valides (hors nuages).",
        "ar": "تركيب Sentinel-2 من {n} صورة على {d} يومًا · {v} من النقاط صالحة (بدون سحب).",
        "en": "Sentinel-2 composite of {n} image(s) over {d} days · {v} valid pixels (cloud-free).",
    },
    "rp_weather": {"fr": "Météo de la période", "ar": "الطقس خلال الفترة", "en": "Weather over the period"},
    "rp_reco": {"fr": "Recommandations · priorité {p}", "ar": "التوصيات · الأولوية {p}", "en": "Recommendations · priority {p}"},
    "rp_indices": {"fr": "Indices spectraux", "ar": "المؤشرات الطيفية", "en": "Spectral indices"},
    "col_index": {"fr": "Indice", "ar": "المؤشر", "en": "Index"},
    "col_value": {"fr": "Valeur", "ar": "القيمة", "en": "Value"},
    "col_ref": {"fr": "Référence", "ar": "المرجع", "en": "Reference"},
    "col_state": {"fr": "État", "ar": "الحالة", "en": "Status"},
    "col_desc": {"fr": "Description", "ar": "الوصف", "en": "Description"},
    "rp_export": {"fr": "Exporter", "ar": "التصدير", "en": "Export"},
    "rp_dl_html": {"fr": "⬇️ Télécharger le rapport (HTML)", "ar": "⬇️ تحميل التقرير (HTML)", "en": "⬇️ Download the report (HTML)"},
    "rp_dl_json": {"fr": "⬇️ Données de l'analyse (JSON)", "ar": "⬇️ بيانات التحليل (JSON)", "en": "⬇️ Analysis data (JSON)"},
    "rp_print": {"fr": "Le rapport HTML s'ouvre dans le navigateur et s'imprime en PDF (Ctrl+P).",
                 "ar": "يُفتح تقرير HTML في المتصفح ويمكن طباعته بصيغة PDF (Ctrl+P).",
                 "en": "The HTML report opens in the browser and prints to PDF (Ctrl+P)."},
    "pl_rain": {"fr": "Pluie (mm)", "ar": "الأمطار (مم)", "en": "Rain (mm)"},
    "pl_tmax": {"fr": "T° max", "ar": "الحرارة القصوى", "en": "Max temp."},
    "pl_tmean": {"fr": "T° moyenne", "ar": "متوسط الحرارة", "en": "Mean temp."},
    # --- Rapport HTML ----------------------------------------------------------------------------
    "html_title": {"fr": "Rapport HydroStress — {date}", "ar": "تقرير HydroStress — {date}", "en": "HydroStress report — {date}"},
    "html_h1": {"fr": "💧 Rapport de stress hydrique", "ar": "💧 تقرير الإجهاد المائي", "en": "💧 Water stress report"},
    "html_head": {
        "fr": "{region} · Zone : {zone} · Culture : {crop}<br>Date analysée : <b>{date}</b> · Parcelle : {ha} ha, "
              "centre {lat}, {lon}<br>Généré le {gen}",
        "ar": "{region} · المنطقة: {zone} · الزراعة: {crop}<br>تاريخ التحليل: <b>{date}</b> · القطعة: {ha} هكتار، "
              "المركز {lat}، {lon}<br>أُنشئ في {gen}",
        "en": "{region} · Area: {zone} · Crop: {crop}<br>Date analysed: <b>{date}</b> · Plot: {ha} ha, "
              "centre {lat}, {lon}<br>Generated on {gen}",
    },
    "html_conf": {"fr": "confiance {conf:.1f} %", "ar": "الثقة {conf:.1f} %", "en": "confidence {conf:.1f} %"},
    "html_indicators": {"fr": "Indicateurs", "ar": "المؤشرات", "en": "Indicators"},
    "html_ndvi": {"fr": "NDVI moyen", "ar": "متوسط NDVI", "en": "Mean NDVI"},
    "html_ndwi": {"fr": "NDWI moyen", "ar": "متوسط NDWI", "en": "Mean NDWI"},
    "html_msi": {"fr": "MSI moyen", "ar": "متوسط MSI", "en": "Mean MSI"},
    "html_ref_range": {"fr": "Plage de référence", "ar": "المجال المرجعي", "en": "Reference range"},
    "html_warn_demo": {"fr": "Données de DÉMONSTRATION : les valeurs ne proviennent pas des satellites pour cette parcelle.",
                       "ar": "بيانات للعرض: القيم لا تأتي من الأقمار الصناعية لهذه القطعة.",
                       "en": "DEMO data: the values do not come from satellites for this plot."},
    "html_warn_synth": {"fr": "Modèle entraîné sur des données synthétiques : résultat indicatif, non validé sur le terrain.",
                        "ar": "نموذج مدرَّب على بيانات اصطناعية: النتيجة إرشادية وغير مؤكَّدة ميدانيًا.",
                        "en": "Model trained on synthetic data: indicative result, not validated in the field."},
    "html_sources": {
        "fr": "Sources : Sentinel-2 (Copernicus), CHIRPS (UCSB-CHG), ERA5-Land (ECMWF). Modèle : Random Forest calibré "
              "({src}, entraîné le {at}). Identifiant : {id}",
        "ar": "المصادر: Sentinel-2 (Copernicus)، CHIRPS (UCSB-CHG)، ERA5-Land (ECMWF). النموذج: Random Forest "
              "({src}، دُرّب في {at}). المعرّف: {id}",
        "en": "Sources: Sentinel-2 (Copernicus), CHIRPS (UCSB-CHG), ERA5-Land (ECMWF). Model: calibrated Random Forest "
              "({src}, trained on {at}). ID: {id}",
    },
    # --- Validation par station --------------------------------------------------------------------
    "st_title": {"fr": "Validation par station météo (NOAA)", "ar": "التحقق بمحطة الأرصاد الجوية (NOAA)",
                 "en": "Validation with a weather station (NOAA)"},
    "st_intro": {
        "fr": "Compare la météo utilisée (ERA5-Land, CHIRPS) aux observations de la station synoptique la plus proche "
              "(moins de 150 km). Les stations sont trop espacées pour remplacer ces données, mais elles permettent de "
              "vérifier leur cohérence.",
        "ar": "يقارن معطيات الطقس المستعملة (ERA5-Land، CHIRPS) بقياسات أقرب محطة رصد (أقل من 150 كلم). المحطات "
              "متباعدة جدًا لتعويض هذه المعطيات، لكنها تسمح بالتحقق من انسجامها.",
        "en": "Compares the weather data used (ERA5-Land, CHIRPS) with observations from the nearest synoptic station "
              "(under 150 km). Stations are too far apart to replace these data, but they let you check consistency.",
    },
    "st_demo": {"fr": "Indisponible pour les données de démonstration.", "ar": "غير متوفر لبيانات العرض.",
                "en": "Not available for demo data."},
    "st_btn": {"fr": "Comparer avec la station la plus proche", "ar": "المقارنة مع أقرب محطة",
               "en": "Compare with the nearest station"},
    "st_searching": {"fr": "Recherche de la station et téléchargement des observations…",
                     "ar": "البحث عن المحطة وتحميل القياسات…", "en": "Finding the station and downloading observations…"},
    "st_unavailable": {"fr": "Service NOAA indisponible : {e}", "ar": "خدمة NOAA غير متوفرة: {e}",
                       "en": "NOAA service unavailable: {e}"},
    "st_none": {"fr": "Aucune station disponible.", "ar": "لا توجد محطة متاحة.", "en": "No station available."},
    "st_none_near": {"fr": "Aucune station NOAA à moins de {km} km.", "ar": "لا توجد محطة NOAA على بعد أقل من {km} كلم.",
                     "en": "No NOAA station within {km} km."},
    "st_no_data": {"fr": "Les stations proches n'ont pas de données sur cette période.",
                   "ar": "المحطات القريبة ليست لديها معطيات في هذه الفترة.",
                   "en": "Nearby stations have no data for this period."},
    "st_header": {"fr": "**{name}** · {km} km de la parcelle · altitude {alt} m",
                  "ar": "**{name}** · على بعد {km} كلم من القطعة · الارتفاع {alt} م",
                  "en": "**{name}** · {km} km from the plot · elevation {alt} m"},
    "st_tmean": {"fr": "T° moyenne (°C)", "ar": "متوسط الحرارة (°م)", "en": "Mean temp. (°C)"},
    "st_tmax": {"fr": "T° max (°C)", "ar": "الحرارة القصوى (°م)", "en": "Max temp. (°C)"},
    "st_rain": {"fr": "Pluie (mm/jour)", "ar": "الأمطار (مم/يوم)", "en": "Rain (mm/day)"},
    "st_col_var": {"fr": "Variable", "ar": "المتغيّر", "en": "Variable"},
    "st_col_days": {"fr": "Jours comparés", "ar": "الأيام المقارَنة", "en": "Days compared"},
    "st_col_bias": {"fr": "Biais (maillé − station)", "ar": "الانحياز (الشبكة − المحطة)", "en": "Bias (grid − station)"},
    "st_col_mae": {"fr": "Erreur moyenne", "ar": "متوسط الخطأ", "en": "Mean error"},
    "st_col_corr": {"fr": "Corrélation", "ar": "الارتباط", "en": "Correlation"},
    "st_rain_total": {"fr": "Cumul de pluie sur les jours communs : station {s} mm, CHIRPS {g} mm.",
                      "ar": "مجموع الأمطار في الأيام المشتركة: المحطة {s} مم، CHIRPS {g} مم.",
                      "en": "Total rain over common days: station {s} mm, CHIRPS {g} mm."},
    "st_series_station": {"fr": "Station · T° moyenne", "ar": "المحطة · متوسط الحرارة", "en": "Station · mean temp."},
    "st_series_era5": {"fr": "ERA5-Land · T° moyenne", "ar": "ERA5-Land · متوسط الحرارة", "en": "ERA5-Land · mean temp."},
    # --- Modèle ----------------------------------------------------------------------------------
    "md_source": {"fr": "Source des données", "ar": "مصدر البيانات", "en": "Data source"},
    "md_samples": {"fr": "Échantillons", "ar": "العيّنات", "en": "Samples"},
    "md_accuracy": {"fr": "Exactitude (test)", "ar": "الدقة (الاختبار)", "en": "Accuracy (test)"},
    "md_trained": {"fr": "Entraîné le", "ar": "تاريخ التدريب", "en": "Trained on"},
    "md_synth": {
        "fr": "Le modèle actuel est entraîné sur des données synthétiques calées sur les climats des zones agricoles du "
              "Maroc. Il sera remplacé par un modèle entraîné sur des données réelles (build_dataset.py).",
        "ar": "النموذج الحالي مدرَّب على بيانات اصطناعية مضبوطة على مناخ المناطق الفلاحية بالمغرب، وسيُعوَّض بنموذج "
              "مدرَّب على بيانات حقيقية.",
        "en": "The current model is trained on synthetic data matched to the climates of Morocco's farming areas. It "
              "will be replaced by a model trained on real data (build_dataset.py).",
    },
    "md_real": {
        "fr": "Modèle entraîné sur des données réelles de {origin}{details} : registres d'irrigation et images "
              "satellite. Le stress de chaque date vient d'un bilan hydrique FAO-56 (climat + apports réels) ; le test "
              "porte sur des campagnes jamais vues. Pour d'autres régions et cultures, les résultats restent "
              "indicatifs : partagez vos données (section « 🤝 Aidez-nous à améliorer le modèle ») pour l'élargir.",
        "ar": "نموذج مدرَّب على بيانات حقيقية من {origin}{details}: سجلات السقي وصور الأقمار الصناعية. الإجهاد في كل "
              "تاريخ محسوب بموازنة مائية FAO-56 (المناخ + كميات الماء الفعلية)، والاختبار يتم على مواسم لم يرها "
              "النموذج. في مناطق وزراعات أخرى تبقى النتائج إرشادية: شارك بياناتك (قسم «🤝 ساعدنا على تحسين "
              "النموذج») لتوسيعه.",
        "en": "Model trained on real data from {origin}{details}: irrigation logs and satellite images. The stress on "
              "each date comes from an FAO-56 water balance (climate + actual water applied); testing uses seasons "
              "never seen. For other regions and crops, results remain indicative: share your data (section “🤝 Help "
              "us improve the model”) to extend it.",
    },
    # --- Simulation ------------------------------------------------------------------------------
    "sm_zone": {"fr": "Zone agricole", "ar": "المنطقة الفلاحية", "en": "Farming area"},
    "sm_rain": {"fr": "Pluie 30 jours (mm)", "ar": "الأمطار 30 يومًا (مم)", "en": "Rain, 30 days (mm)"},
    "sm_dry": {"fr": "Jours secs consécutifs", "ar": "أيام جافة متتالية", "en": "Consecutive dry days"},
    "sm_crop": {"fr": "Culture", "ar": "الزراعة", "en": "Crop"},
    "sm_tmean": {"fr": "T° moyenne (°C)", "ar": "متوسط الحرارة (°م)", "en": "Mean temp. (°C)"},
    "sm_tmax": {"fr": "T° max (°C)", "ar": "الحرارة القصوى (°م)", "en": "Max temp. (°C)"},
    "sm_rh": {"fr": "Humidité moyenne (%)", "ar": "متوسط الرطوبة (%)", "en": "Mean humidity (%)"},
    "sm_result": {"fr": "Résultat simulé", "ar": "النتيجة المحاكاة", "en": "Simulated result"},
    "sm_conf": {"fr": "Confiance {c:.1f} %", "ar": "الثقة {c:.1f} %", "en": "Confidence {c:.1f} %"},
    # --- Contributions ---------------------------------------------------------------------------
    "ct_intro": {
        "fr": "Le modèle apprend à partir de **vraies fermes**. Chaque ferme qui partage ses registres d'irrigation le "
              "rend plus juste pour sa région et sa culture. Les données servent uniquement à entraîner HydroStress : "
              "le nom et la position de votre ferme ne sont jamais publiés.",
        "ar": "يتعلّم النموذج من **ضيعات حقيقية**. كل ضيعة تشارك سجلات السقي تجعله أدقّ لمنطقتها وزراعتها. تُستعمل "
              "البيانات فقط لتدريب HydroStress: اسم ضيعتك وموقعها لا يُنشران أبدًا.",
        "en": "The model learns from **real farms**. Every farm that shares its irrigation logs makes it more accurate "
              "for its region and crop. Data are used only to train HydroStress: your farm's name and location are "
              "never published.",
    },
    "ct_useful": {
        "fr": "**Données les plus utiles**\n- Registres d'irrigation **jour par jour** (m³, heures × débit ou relevés de "
              "compteur), sur plusieurs campagnes : un fichier Excel par campagne convient.\n- La culture, l'écartement "
              "de plantation, la surface et l'année de plantation de la parcelle.\n- En plus si vous les avez : "
              "observations de stress (dates, symptômes), rendements par campagne, analyses de sol, limites de la "
              "parcelle (KML / GeoJSON).",
        "ar": "**البيانات الأكثر فائدة**\n- سجلات السقي **يومًا بيوم** (م³، الساعات × الصبيب أو قراءات العدّاد) على عدة "
              "مواسم: ملف Excel لكل موسم يكفي.\n- الزراعة، ومسافة الغرس، والمساحة، وسنة الغرس.\n- وإن توفرت: ملاحظات "
              "الإجهاد (التواريخ، الأعراض)، المردود في كل موسم، تحاليل التربة، حدود القطعة (KML / GeoJSON).",
        "en": "**Most useful data**\n- **Day-by-day** irrigation logs (m³, hours × flow or meter readings) over several "
              "seasons: one Excel file per season is fine.\n- The crop, planting spacing, area and planting year of the "
              "plot.\n- If you have them: stress observations (dates, symptoms), yields per season, soil analyses, plot "
              "boundaries (KML / GeoJSON).",
    },
    "ct_soon": {"fr": "📬 L'envoi de données ouvre très bientôt. En attendant, contactez-nous pour partager vos registres.",
                "ar": "📬 سيُفتح إرسال البيانات قريبًا جدًا. في انتظار ذلك، تواصل معنا لمشاركة سجلاتك.",
                "en": "📬 Data upload opens very soon. Meanwhile, contact us to share your logs."},
    "ct_you": {"fr": "**1. Vous**", "ar": "**1. أنت**", "en": "**1. You**"},
    "ct_name": {"fr": "Nom et prénom *", "ar": "الاسم الكامل *", "en": "Full name *"},
    "ct_phone": {"fr": "Téléphone / WhatsApp", "ar": "الهاتف / واتساب", "en": "Phone / WhatsApp"},
    "ct_email": {"fr": "E-mail", "ar": "البريد الإلكتروني", "en": "E-mail"},
    "ct_org": {"fr": "Exploitation, coopérative ou organisme (facultatif)", "ar": "الضيعة أو التعاونية أو الهيئة (اختياري)",
               "en": "Farm, cooperative or organisation (optional)"},
    "ct_plot": {"fr": "**2. La parcelle**", "ar": "**2. القطعة**", "en": "**2. The plot**"},
    "ct_plot_name": {"fr": "Nom de la parcelle (ex. Bloc 4) *", "ar": "اسم القطعة (مثلًا: بلوك 4) *",
                     "en": "Plot name (e.g. Block 4) *"},
    "ct_lat": {"fr": "Latitude *", "ar": "خط العرض *", "en": "Latitude *"},
    "ct_lat_help": {"fr": "Sur la carte ci-dessus ou dans Google Maps : clic droit sur la parcelle.",
                    "ar": "على الخريطة أعلاه أو في Google Maps: نقرة يمنى على القطعة.",
                    "en": "On the map above or in Google Maps: right-click on the plot."},
    "ct_lon": {"fr": "Longitude *", "ar": "خط الطول *", "en": "Longitude *"},
    "ct_crop": {"fr": "Culture *", "ar": "الزراعة *", "en": "Crop *"},
    "ct_spacing": {"fr": "Écartement (m) : entre rangs x sur le rang", "ar": "مسافة الغرس (م): بين الخطوط × على الخط",
                   "en": "Spacing (m): between rows x along the row"},
    "ct_area": {"fr": "Surface (ha) *", "ar": "المساحة (هكتار) *", "en": "Area (ha) *"},
    "ct_year": {"fr": "Année de plantation", "ar": "سنة الغرس", "en": "Planting year"},
    "ct_irrigation": {"fr": "Irrigation", "ar": "نوع السقي", "en": "Irrigation"},
    "ct_soil": {"fr": "Sol", "ar": "التربة", "en": "Soil"},
    "ct_files": {"fr": "**3. Vos fichiers**", "ar": "**3. ملفاتك**", "en": "**3. Your files**"},
    "ct_registers": {"fr": "Registres d'irrigation (un fichier par campagne)", "ar": "سجلات السقي (ملف لكل موسم)",
                     "en": "Irrigation logs (one file per season)"},
    "ct_others": {"fr": "Autres fichiers utiles (facultatif)", "ar": "ملفات أخرى مفيدة (اختياري)",
                  "en": "Other useful files (optional)"},
    "ct_comment": {"fr": "Remarques (période couverte, changements de culture, panne, etc.)",
                   "ar": "ملاحظات (الفترة المشمولة، تغيير الزراعة، عطل، إلخ)",
                   "en": "Notes (period covered, crop changes, breakdowns, etc.)"},
    "ct_consent": {
        "fr": "J'accepte que ces données soient utilisées par HydroStress pour entraîner et évaluer son modèle. Le nom "
              "et la position de ma ferme ne seront jamais publiés, et je peux demander leur suppression à tout moment.",
        "ar": "أوافق على أن تستعمل HydroStress هذه البيانات لتدريب نموذجها وتقييمه. لن يُنشر اسم ضيعتي ولا موقعها "
              "أبدًا، ويمكنني طلب حذفها في أي وقت.",
        "en": "I agree that HydroStress may use these data to train and evaluate its model. My farm's name and location "
              "will never be published, and I can ask for their deletion at any time.",
    },
    "ct_send": {"fr": "📤 Envoyer mes données", "ar": "📤 إرسال بياناتي", "en": "📤 Send my data"},
    "ct_err_position": {"fr": "Indiquez la position de la parcelle (latitude et longitude).",
                        "ar": "حدّد موقع القطعة (خط العرض وخط الطول).",
                        "en": "Enter the plot's position (latitude and longitude)."},
    "ct_err_name": {"fr": "Indiquez le nom de la parcelle.", "ar": "اكتب اسم القطعة.", "en": "Enter the plot name."},
    "ct_err_area": {"fr": "Indiquez la surface de la parcelle.", "ar": "اكتب مساحة القطعة.", "en": "Enter the plot area."},
    "ct_err_consent": {"fr": "Cochez la case d'accord pour l'utilisation des données.",
                       "ar": "ضع علامة على خانة الموافقة على استعمال البيانات.",
                       "en": "Tick the box to agree to the use of the data."},
    "ct_err_you": {"fr": "Indiquez votre nom.", "ar": "اكتب اسمك.", "en": "Enter your name."},
    "ct_err_contact": {"fr": "Indiquez un téléphone (WhatsApp) ou un e-mail pour qu'on puisse vous recontacter.",
                       "ar": "اكتب رقم هاتف (واتساب) أو بريدًا إلكترونيًا لنتمكّن من التواصل معك.",
                       "en": "Enter a phone (WhatsApp) or an e-mail so we can get back to you."},
    "ct_err_email": {"fr": "L'adresse e-mail ne semble pas valide.", "ar": "يبدو أن البريد الإلكتروني غير صحيح.",
                     "en": "The e-mail address does not look valid."},
    "ct_err_file": {"fr": "Ajoutez au moins un fichier (registre d'irrigation de préférence).",
                    "ar": "أضف ملفًا واحدًا على الأقل (يُفضَّل سجل السقي).",
                    "en": "Add at least one file (preferably an irrigation log)."},
    "ct_err_max_files": {"fr": "{n} fichiers au maximum.", "ar": "{n} ملفات كحد أقصى.", "en": "{n} files at most."},
    "ct_err_max_mb": {"fr": "{n} Mo au maximum au total.", "ar": "{n} ميغابايت كحد أقصى في المجموع.",
                      "en": "{n} MB at most in total."},
    "ct_sending": {"fr": "Lecture des registres et envoi…", "ar": "قراءة السجلات والإرسال…", "en": "Reading logs and sending…"},
    "ct_failed": {"fr": "L'envoi n'a pas abouti ({e}). Réessayez plus tard ou contactez-nous.",
                  "ar": "لم يكتمل الإرسال ({e}). أعد المحاولة لاحقًا أو تواصل معنا.",
                  "en": "Sending failed ({e}). Try again later or contact us."},
    "ct_thanks": {"fr": "Merci ! Vos données sont bien reçues. Référence : **{ref}**. Gardez-la si vous voulez nous écrire "
                        "à leur sujet.",
                  "ar": "شكرًا! توصّلنا ببياناتك. المرجع: **{ref}**. احتفظ به إذا أردت مراسلتنا بشأنها.",
                  "en": "Thank you! Your data were received. Reference: **{ref}**. Keep it if you want to write to us "
                        "about them."},
    "ct_read": {"fr": "Registres lus du {a} au {b} :", "ar": "السجلات المقروءة من {a} إلى {b}:",
                "en": "Logs read from {a} to {b}:"},
    "ct_unread": {"fr": "Nous n'avons pas pu lire automatiquement vos registres : nous les traiterons à la main.",
                  "ar": "لم نتمكن من قراءة سجلاتك آليًا: سنعالجها يدويًا.",
                  "en": "We could not read your logs automatically: we will process them by hand."},
    # --- Entraîner sur ma ferme -----------------------------------------------------------------
    "fm_intro": {
        "fr": "Décrivez la ferme, téléchargez son climat et lisez ses registres d'irrigation : un bilan hydrique FAO-56 "
              "en déduit le stress réel subi chaque jour, qui sert d'étiquette pour entraîner le modèle.",
        "ar": "صف الضيعة، وحمّل مناخها، واقرأ سجلات السقي: موازنة مائية FAO-56 تستخرج منها الإجهاد الحقيقي في كل يوم، "
              "ويُستعمل كتسمية لتدريب النموذج.",
        "en": "Describe the farm, download its climate and read its irrigation logs: an FAO-56 water balance derives "
              "the actual daily stress, used as the label to train the model.",
    },
    "fm_new": {"fr": "➕ Nouvelle ferme", "ar": "➕ ضيعة جديدة", "en": "➕ New farm"},
    "fm_saved": {"fr": "Ferme enregistrée : {name}", "ar": "تم حفظ الضيعة: {name}", "en": "Farm saved: {name}"},
    "fm_farm": {"fr": "Ferme", "ar": "الضيعة", "en": "Farm"},
    "fm_name": {"fr": "Nom (bloc, parcelle)", "ar": "الاسم (بلوك، قطعة)", "en": "Name (block, plot)"},
    "fm_lat": {"fr": "Latitude", "ar": "خط العرض", "en": "Latitude"},
    "fm_lon": {"fr": "Longitude", "ar": "خط الطول", "en": "Longitude"},
    "fm_area": {"fr": "Surface (ha)", "ar": "المساحة (هكتار)", "en": "Area (ha)"},
    "fm_save": {"fr": "💾 Enregistrer la ferme", "ar": "💾 حفظ الضيعة", "en": "💾 Save the farm"},
    "fm_default_name": {"fr": "Ma ferme", "ar": "ضيعتي", "en": "My farm"},
    "fm_step1": {"fr": "**1. Climat quotidien**", "ar": "**1. المناخ اليومي**", "en": "**1. Daily climate**"},
    "fm_step2": {"fr": "**2. Registres d'irrigation**", "ar": "**2. سجلات السقي**", "en": "**2. Irrigation logs**"},
    "fm_step3": {"fr": "**3. Bilan hydrique et étiquettes**", "ar": "**3. الموازنة المائية والتسميات**",
                 "en": "**3. Water balance and labels**"},
    "fm_step4": {"fr": "**4. Données satellite (Earth Engine)**", "ar": "**4. بيانات الأقمار الصناعية (Earth Engine)**",
                 "en": "**4. Satellite data (Earth Engine)**"},
    "fm_step5": {"fr": "**5. Entraînement du modèle**", "ar": "**5. تدريب النموذج**", "en": "**5. Model training**"},
    "fm_years": {"fr": "Années", "ar": "السنوات", "en": "Years"},
    "fm_source": {"fr": "Source", "ar": "المصدر", "en": "Source"},
    "fm_dl_climate": {"fr": "⬇️ Télécharger le climat", "ar": "⬇️ تحميل المناخ", "en": "⬇️ Download climate"},
    "fm_dl_climate_spin": {"fr": "Téléchargement année par année...", "ar": "التحميل سنة بسنة...",
                           "en": "Downloading year by year..."},
    "fm_dl_failed": {"fr": "Téléchargement impossible : {e}", "ar": "تعذّر التحميل: {e}", "en": "Download failed: {e}"},
    "fm_registers": {"fr": "Registres d'irrigation (Excel, un fichier par campagne)",
                     "ar": "سجلات السقي (Excel، ملف لكل موسم)", "en": "Irrigation logs (Excel, one file per season)"},
    "fm_read": {"fr": "📖 Lire les registres", "ar": "📖 قراءة السجلات", "en": "📖 Read the logs"},
    "fm_need_area": {"fr": "Indiquez la surface de la ferme pour convertir les m³ en mm.",
                     "ar": "اكتب مساحة الضيعة لتحويل م³ إلى مم.", "en": "Enter the farm area to convert m³ to mm."},
    "fm_empty_months": {"fr": "Mois sans aucun apport : {months}. Arrêt réel ou registre manquant ? Les longues périodes "
                              "vides ne sont pas étiquetées.",
                        "ar": "أشهر بدون أي سقي: {months}. توقف فعلي أم سجل ناقص؟ الفترات الطويلة الفارغة لا تُسمّى.",
                        "en": "Months with no water applied: {months}. Real stop or missing log? Long empty periods are "
                              "not labelled."},
    "fm_irr": {"fr": "Irrigation (mm)", "ar": "السقي (مم)", "en": "Irrigation (mm)"},
    "fm_rain_eff": {"fr": "Pluie efficace (mm)", "ar": "المطر الفعّال (مم)", "en": "Effective rain (mm)"},
    "fm_etc": {"fr": "Besoin ETc (mm)", "ar": "الحاجة ETc (مم)", "en": "Need ETc (mm)"},
    "fm_ks": {"fr": "Ks moyen", "ar": "متوسط Ks", "en": "Mean Ks"},
    "fm_mm_month": {"fr": "mm / mois", "ar": "مم / شهر", "en": "mm / month"},
    "fm_no_dates": {"fr": "Aucune date étiquetable : climat et registres ne couvrent pas la même période.",
                    "ar": "لا يوجد تاريخ قابل للتسمية: المناخ والسجلات لا يغطيان نفس الفترة.",
                    "en": "No date can be labelled: climate and logs do not cover the same period."},
    "fm_normal": {"fr": "🟢 normal", "ar": "🟢 عادي", "en": "🟢 normal"},
    "fm_moderate": {"fr": "🟡 modéré", "ar": "🟡 متوسط", "en": "🟡 moderate"},
    "fm_severe": {"fr": "🔴 sévère", "ar": "🔴 حادّ", "en": "🔴 severe"},
    "fm_dl_labels": {"fr": "Télécharger les étiquettes (CSV)", "ar": "تحميل التسميات (CSV)", "en": "Download labels (CSV)"},
    "fm_every": {"fr": "Une date tous les", "ar": "تاريخ كل", "en": "One date every"},
    "fm_every_help": {"fr": "Moins de dates = extraction plus rapide, mais moins d'exemples pour l'entraînement.",
                      "ar": "تواريخ أقل = استخراج أسرع، لكن أمثلة أقل للتدريب.",
                      "en": "Fewer dates = faster extraction, but fewer training examples."},
    "fm_restart": {"fr": "Recommencer", "ar": "البدء من جديد", "en": "Start over"},
    "fm_restart_help": {"fr": "Ignorer le dataset déjà extrait et tout refaire.", "ar": "تجاهل البيانات المستخرجة وإعادة كل شيء.",
                        "en": "Ignore the dataset already extracted and redo everything."},
    "fm_extract": {"fr": "🛰️ Extraire les données satellite (Earth Engine)", "ar": "🛰️ استخراج بيانات الأقمار الصناعية (Earth Engine)",
                   "en": "🛰️ Extract satellite data (Earth Engine)"},
    "fm_ee_connect": {"fr": "Connexion à Earth Engine…", "ar": "الاتصال بـ Earth Engine…", "en": "Connecting to Earth Engine…"},
    "fm_done": {"fr": "Terminé", "ar": "انتهى", "en": "Done"},
    "fm_samples": {"fr": "{n} échantillons ({s} dates sans image Sentinel-2 exploitable).",
                   "ar": "{n} عيّنة ({s} تاريخ بدون صورة Sentinel-2 صالحة).",
                   "en": "{n} samples ({s} dates without a usable Sentinel-2 image)."},
    "fm_extract_failed": {"fr": "Extraction interrompue : {e}. Relancez : elle reprendra là où elle s'est arrêtée.",
                          "ar": "توقف الاستخراج: {e}. أعد التشغيل وسيستأنف من حيث توقّف.",
                          "en": "Extraction interrupted: {e}. Run it again: it will resume where it stopped."},
    "fm_dl_dataset": {"fr": "Télécharger le dataset (CSV)", "ar": "تحميل البيانات (CSV)", "en": "Download the dataset (CSV)"},
    "fm_few_campaigns": {"fr": "{n} campagne(s) dans le dataset : il en faut au moins {m} pour entraîner et tester.",
                         "ar": "{n} موسم في البيانات: يلزم {m} على الأقل للتدريب والاختبار.",
                         "en": "{n} season(s) in the dataset: at least {m} are needed to train and test."},
    "fm_grid": {"fr": "Recherche des meilleurs réglages (plus long, plus précis)", "ar": "البحث عن أفضل الإعدادات (أطول، أدقّ)",
                "en": "Search for the best settings (longer, more accurate)"},
    "fm_train": {"fr": "🧠 Entraîner le modèle sur cette ferme", "ar": "🧠 تدريب النموذج على هذه الضيعة",
                 "en": "🧠 Train the model on this farm"},
    "fm_training": {"fr": "Entraînement en cours…", "ar": "جارٍ التدريب…", "en": "Training…"},
    "fm_train_failed": {"fr": "Entraînement impossible : {e}", "ar": "تعذّر التدريب: {e}", "en": "Training failed: {e}"},
    "fm_f1": {"fr": "F1 pondéré", "ar": "F1 الموزون", "en": "Weighted F1"},
    "fm_test_samples": {"fr": "Échantillons de test", "ar": "عيّنات الاختبار", "en": "Test samples"},
    "fm_test_note": {"fr": "Le test porte sur des campagnes jamais vues pendant l'entraînement.",
                     "ar": "يتم الاختبار على مواسم لم يرها النموذج أثناء التدريب.",
                     "en": "Testing uses seasons never seen during training."},
    "fm_dl_model": {"fr": "⬇️ Télécharger le modèle (zip)", "ar": "⬇️ تحميل النموذج (zip)", "en": "⬇️ Download the model (zip)"},
    "fm_dl_model_help": {"fr": "Envoyez ce fichier pour qu'il devienne le modèle de l'application.",
                         "ar": "أرسل هذا الملف ليصبح نموذج التطبيق.", "en": "Send this file so it becomes the app's model."},
}
