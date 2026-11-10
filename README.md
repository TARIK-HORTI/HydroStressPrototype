# 💧 HydroStressPrototype — Maroc

**Prédiction du stress hydrique des cultures par télédétection et Machine Learning, partout au Maroc**

---

## 🎯 Description

HydroStressPrototype est un tableau de bord web de suivi du stress hydrique des parcelles agricoles au Maroc. Il combine Sentinel-2, CHIRPS, ERA5-Land et un Random Forest calibré pour classer une parcelle en trois classes :

- **🟢 Normal** — Aucune action requise
- **🟡 Modéré** — Surveillance renforcée et ajustement de l'irrigation
- **🔴 Sévère** — Intervention urgente nécessaire

### Couverture nationale

Les données météo (CHIRPS ~5 km, ERA5-Land ~9 km) et satellite (Sentinel-2, 10 m) couvrent tout le pays : aucune station météo n'est nécessaire pour l'analyse. Chaque parcelle est rattachée automatiquement à la **zone agricole de référence** la plus proche (`region.py`), qui fournit les cultures dominantes, les seuils d'interprétation et l'organisme d'encadrement :

| Zone | Localités de référence | Cultures |
|------|------------------------|----------|
| Gharb – Loukkos | Kénitra, Sidi Slimane, Sidi Kacem, Souk El Arbaa, Ksar El Kébir | Agrumes, canne à sucre, betterave, riz, céréales, maraîchage |
| Saïs – Meknès – Fès | Meknès, Fès, El Hajeb, Sefrou | Céréales, olivier, vigne, arboriculture, maraîchage |
| Tadla – Béni Mellal | Béni Mellal, Fquih Ben Salah, Souk Sebt, Kasba Tadla | Betterave, céréales, agrumes, olivier, luzerne |
| Haouz – Marrakech | Marrakech, Aït Ourir, Chichaoua, El Kelâa des Sraghna | Olivier, céréales, agrumes, maraîchage, luzerne |
| Chaouia – Doukkala | Settat, Berrechid, Sidi Bennour, El Jadida | Céréales, betterave, maraîchage, légumineuses |
| Souss – Massa | Agadir, Ouled Teima, Taroudant, Biougra, Tiznit | Agrumes, maraîchage sous serre, arganier, bananier, olivier |
| Oriental – Moulouya | Berkane, Oujda, Zaïo, Taourirt | Agrumes, olivier, céréales, maraîchage, vigne |
| Errachidia – Tafilalet | Errachidia, Aoufous, Erfoud, Jorf, Rissani, Goulmima, Tinejdad, Boudnib | Palmier dattier, luzerne, céréales, olivier, maraîchage |
| Drâa – Ouarzazate – Zagora | Ouarzazate, Skoura, Kelâat M'Gouna, Tinghir, Agdz, Zagora | Palmier dattier, luzerne, céréales, rosier à parfum, olivier |

Le modèle reçoit en plus deux caractéristiques du site, l'**altitude** (SRTM) et le **cumul annuel moyen de pluie 1991-2020** (CHIRPS), pour qu'un même modèle s'applique du Gharb humide aux oasis du Drâa.

Les **stations synoptiques** (NOAA GSOD, accès libre) servent à **valider** la météo d'une analyse : le rapport compare ERA5-Land et CHIRPS à la station la plus proche (< 150 km). Elles ne remplacent pas les données maillées, car elles sont trop espacées.

> ⚠️ **Modèle fourni = données synthétiques.** `models/` contient un modèle entraîné sur un dataset synthétique calé sur les climats des 9 zones (`generate_training_data.py`). Il sert à faire tourner l'application de bout en bout ; ses prédictions ne sont pas validées sur le terrain. Pour un modèle exploitable, construisez un dataset réel avec `build_dataset.py` ou avec vos relevés, puis réentraînez.

---

## 🏗️ Architecture

```
HydroStressPrototype/
├── region.py                  # Maroc : emprise, 9 zones agricoles, localités, cultures, normales
├── extract_data.py            # Extraction Sentinel-2, CHIRPS, ERA5-Land + authentification Earth Engine
├── build_dataset.py           # Dataset réel : features + étiquettes VHI (MODIS) dans toutes les zones
├── farm.py                    # Ferme : position, culture, écartement, sol, irrigation, Kc corrigé
├── climate_history.py         # Climat quotidien Open-Meteo / NASA POWER + features météo
├── irrigation_register.py     # Lecture des registres d'irrigation Excel
├── water_balance.py           # Bilan hydrique FAO-56 -> Ks -> classe de stress
├── farm_dataset.py            # Entraînement sur une ferme réelle (CLI en 6 étapes)
├── farm_ui.py                 # Section Streamlit « Entraîner sur ma ferme »
├── stations.py                # Validation par les stations météo NOAA GSOD
├── generate_training_data.py  # Dataset synthétique calé sur les climats des zones
├── train_model.py             # Entraînement Random Forest + calibration (CLI)
├── predict.py                 # Prédiction, interprétation, recommandations locales
├── app.py                     # Tableau de bord Streamlit (une seule page)
├── report.py                  # Rapport d'analyse (export HTML)
├── demo.py                    # Données de démonstration (sans Earth Engine)
├── .streamlit/config.toml     # Thème de l'interface
├── models/                    # Modèle entraîné + métadonnées (métriques de test incluses)
├── tests/                     # Tests pytest (sans accès Earth Engine)
└── requirements.txt
```

---

## 📦 Installation

### Prérequis

- **Python** 3.10, 3.11 ou 3.12
- Un projet Google Cloud avec **Google Earth Engine** activé

### Étapes

```bash
git clone https://github.com/TARIK-HORTI/HydroStressPrototype.git
cd HydroStressPrototype
python -m venv venv
source venv/bin/activate        # Windows : venv\Scripts\activate
pip install -r requirements.txt
```

### Authentification Earth Engine

L'application essaie, dans cet ordre :

1. **Streamlit Cloud** : dans *Settings → Secrets* de l'app (ou `.streamlit/secrets.toml` en local), collez le fichier JSON du compte de service tel quel :
   ```toml
   GCP_SERVICE_ACCOUNT_JSON = '''
   { "type": "service_account", "project_id": "...", ... }
   '''
   ```
   L'ancien format (table `[GCP_SERVICE_ACCOUNT]` avec les champs du JSON) reste accepté. Le compte de service doit être enregistré pour Earth Engine et avoir le rôle *Earth Engine Resource Viewer* (ou plus) sur le projet.
2. **Fichier JSON local** : `export EE_SERVICE_ACCOUNT_FILE=/chemin/compte-service.json` (ou `GOOGLE_APPLICATION_CREDENTIALS`).
3. **Compte utilisateur** : `earthengine authenticate`, puis `export EE_PROJECT=<id-du-projet-gcp>`.

---

## 🚀 Utilisation

### 1. Lancer l'application

```bash
streamlit run app.py
```

Puis ouvrez `http://localhost:8501`.

### 2. Workflow d'analyse

Tout se passe sur une seule page :

1. Choisir la région agricole, la localité et la culture dans le panneau de droite
2. Dessiner la parcelle sur la carte satellite (≤ 10 km², au Maroc) : la zone est détectée automatiquement
3. Choisir la date d'analyse (ERA5-Land et CHIRPS sont publiés avec environ une semaine de retard)
4. Cliquer **Analyser la parcelle** : extraction, prédiction et rapport s'enchaînent
5. Lire le rapport sous la carte et le télécharger (HTML imprimable en PDF, ou JSON)

Le bouton **Voir un exemple** affiche un rapport avec des données de démonstration (sans Earth Engine), clairement signalées comme telles. Les informations sur le modèle et une simulation manuelle sont en bas de page.

### 3. Entraîner un modèle

```bash
# Dataset synthétique (démonstration)
python generate_training_data.py -n 3000 -o training_data.csv
python train_model.py training_data.csv --source synthetic

# Dataset réel avec étiquettes VHI (Earth Engine requis, long : plusieurs heures)
python build_dataset.py --points-per-place 4 --start 2019-01-01 --end 2024-12-31 --output data/maroc_vhi.csv
python train_model.py data/maroc_vhi.csv --source vhi

# Une ou plusieurs zones seulement
python build_dataset.py --zones haouz souss --points-per-place 6 --output data/haouz_souss.csv
```

Si le CSV contient une colonne `parcel_id`, le découpage train/val/test et la validation croisée se font par parcelle, pour qu'une même parcelle ne soit jamais à la fois en entraînement et en test. Les métriques de test sont enregistrées dans `models/hydrostress_metadata.json` et affichées dans le **📈 Dashboard**.

#### Étiquettes VHI (`build_dataset.py`)

Le Vegetation Health Index (Kogan) compare le NDVI (MODIS MOD13Q1) et la température de surface (MODIS MOD11A2) à l'historique 2001+ du même pixel à la même période : `VHI = 0.5·VCI + 0.5·TCI`. Classes : VHI ≥ 40 → Normal, 20–40 → Modéré, < 20 → Sévère. C'est une étiquette indirecte : des observations de terrain (ORMVA du Tafilalet, agriculteurs) restent la référence pour valider le modèle.

#### Données réelles d'une ferme (`farm_dataset.py`)

Les registres d'irrigation d'une ferme donnent une étiquette plus directe que le VHI : un **bilan hydrique FAO-56** jour par jour (climat téléchargé + apports réels) calcule le coefficient de stress **Ks** de la culture (1 = aucune contrainte). Moyenne de Ks sur 10 jours : ≥ 0,85 → Normal, 0,60–0,85 → Modéré, < 0,60 → Sévère (seuils réglables avec `--ks-thresholds`).

La ferme se décrit une fois : position, culture, **écartement** (densité et couverture du sol, qui corrigent le Kc d'un verger jeune ou peu dense), surface, année de plantation, sol et système d'irrigation. Le climat quotidien est téléchargé sans compte depuis **Open-Meteo** (ERA5-Land, ET0 Penman-Monteith) ou **NASA POWER**.

```bash
python farm_dataset.py init --name "Bloc 4" --lat 31.887705 --lon -4.155879 \
    --crop amandier --spacing 7x5 --area-ha 102 --planting-year 2018 --irrigation goutte --soil sableux
python farm_dataset.py climate farms/bloc-4.json --start 2018-01-01 --end 2025-12-31
python farm_dataset.py irrigation farms/bloc-4.json registres/*.xlsx   # un fichier Excel par campagne
python farm_dataset.py balance farms/bloc-4.json      # bilan + étiquettes, sans Earth Engine
python farm_dataset.py build farms/bloc-4.json        # + Sentinel-2 (Earth Engine) -> data/bloc-4/dataset.csv
python farm_dataset.py train farms/bloc-4.json        # découpage par campagne agricole
```

Les mêmes étapes, sauf `build` et `train`, sont disponibles dans l'application (section **🌴 Entraîner sur ma ferme**). La lecture des registres (`irrigation_register.py`) s'adapte aux mises en page qui changent d'une campagne à l'autre (colonne `m3`, différence de compteur `dif /m3` ou `m3/ha`), corrige les années mal saisies et signale les mois sans aucun apport : une longue période vide est traitée comme un registre manquant et n'est pas étiquetée.

### 4. Tests

```bash
pip install pytest
pytest -q
```

Les tests couvrent la validation des parcelles (zone, surface, auto-intersection), l'agrégation des features météo, le générateur de données et l'aller-retour entraînement → prédiction. Ils tournent sans accès Earth Engine et sont exécutés par GitHub Actions (`.github/workflows/ci.yml`).

---

## 📊 Format CSV d'entraînement

Le fichier CSV doit contenir les colonnes suivantes :

### Features (26 colonnes)

| Colonne | Description | Unité / Range |
|---------|-------------|---------------|
| `NDVI_mean` | Moyenne NDVI sur la parcelle | [-1, 1] |
| `NDWI_mean` | Moyenne NDWI sur la parcelle | [-1, 1] |
| `MSI_mean` | Moyenne MSI sur la parcelle | [0, ∞) |
| `SAVI_mean` | Moyenne SAVI sur la parcelle | [-1, 1] |
| `EVI_mean` | Moyenne EVI sur la parcelle | [-1, 1] |
| `NDVI_min` | Minimum NDVI | [-1, 1] |
| `NDVI_max` | Maximum NDVI | [-1, 1] |
| `NDVI_std` | Écart-type NDVI | [0, ∞) |
| `NDWI_std` | Écart-type NDWI | [0, ∞) |
| `MSI_min` | Minimum MSI | [0, ∞) |
| `MSI_max` | Maximum MSI | [0, ∞) |
| `MSI_std` | Écart-type MSI | [0, ∞) |
| `precipitation_total_30j` | Cumul précipitations sur les 30 derniers jours | mm |
| `precipitation_total_7j` | Cumul précipitations 7 jours | mm |
| `precipitation_mean` | Moyenne journalière de précipitation | mm/jour |
| `max_consecutive_dry_days` | Max jours consécutifs sans pluie (>0.1mm) | jours |
| `rainy_days_count` | Nombre de jours avec pluie | jours |
| `temperature_mean` | Moyenne des températures journalières moyennes (30 j) | °C |
| `temperature_max` | Maximum des températures maximales journalières (30 j) | °C |
| `temperature_min` | Minimum des températures minimales journalières (30 j) | °C |
| `humidity_mean` | Humidité relative moyenne (30 j) | % |
| `humidity_min` | Humidité relative minimale estimée (T max, point de rosée) | % |
| `day_of_year_sin` | Composante sinus du jour de l'année | [-1, 1] |
| `day_of_year_cos` | Composante cosinus du jour de l'année | [-1, 1] |
| `elevation_m` | Altitude du site (SRTM) | m |
| `precip_annual_normal_mm` | Cumul annuel moyen de pluie 1991-2020 (CHIRPS) | mm |

### Label (1 colonne)

| Colonne | Description | Valeurs |
|---------|-------------|---------|
| `stress_class` | Classe de stress hydrique | `0`=Normal, `1`=Modéré, `2`=Sévère |

### Exemple de ligne

```csv
NDVI_mean,NDWI_mean,MSI_mean,SAVI_mean,EVI_mean,NDVI_min,NDVI_max,NDVI_std,NDWI_std,MSI_min,MSI_max,MSI_std,precipitation_total_30j,precipitation_total_7j,precipitation_mean,max_consecutive_dry_days,rainy_days_count,temperature_mean,temperature_max,temperature_min,humidity_mean,humidity_min,day_of_year_sin,day_of_year_cos,elevation_m,precip_annual_normal_mm,stress_class
0.48,0.18,0.69,0.35,0.30,0.30,0.62,0.08,0.05,0.48,0.95,0.12,3.5,0.0,0.12,24.0,2.0,30.5,43.0,19.0,28.0,9.0,0.47,-0.88,1050,120,1
```

---

## 🔬 Indices Spectraux

| Indice | Formule | Interprétation |
|--------|---------|----------------|
| **NDVI** | (NIR − Red) / (NIR + Red) | Vigueur de la végétation |
| **NDWI** (Gao) | (NIR − SWIR) / (NIR + SWIR) | Contenu en eau de la végétation |
| **MSI** | SWIR / NIR | Stress hydrique (valeurs élevées = stress) |
| **SAVI** | ((NIR − Red) / (NIR + Red + L)) × (1 + L) | NDVI corrigé pour le sol nu |
| **EVI** | 2.5 × (NIR − Red) / (NIR + 6×Red − 7.5×Blue + 1) | Indice amélioré, moins saturé |

Les réflectances Sentinel-2 L2A sont converties en [0, 1] (÷ 10 000) avant le calcul, ce qui est indispensable pour SAVI et EVI. Les indices sont calculés sur un composite médian des images de la fenêtre après masquage des nuages (bande SCL) ; l'analyse est refusée si moins de 30 % de la parcelle a des pixels valides.

---

## 🛰️ Sources de Données

| Source | Type | Résolution | Période |
|--------|------|------------|---------|
| **Sentinel-2** (COPERNICUS/S2_SR_HARMONIZED) | Multispectral | 10–20 m | 2017–présent |
| **CHIRPS** (UCSB-CHG/CHIRPS/DAILY) | Précipitations | 0.05° (~5 km) | 1981–présent |
| **ERA5-Land** (ECMWF/ERA5_LAND/DAILY_AGGR) | Température, rosée | 0.1° (~9 km) | 1950–présent |

---

## ⚙️ Modèle Machine Learning

- **Algorithme** : Random Forest (scikit-learn)
- **Pipeline** : StandardScaler → RandomForest → CalibratedClassifierCV
- **Optimisation** : GridSearchCV (5-fold stratifié)
- **Calibration** : Platt scaling (sigmoïde), validation croisée interne à 5 plis
- **Classes** : 3 (Normal, Modéré, Sévère)
- **Features** : 26 (indices spectraux, CHIRPS, ERA5-Land, saison, altitude, normale de pluie)

---

## 🐛 Dépannage

| Problème | Solution |
|----------|----------|
| `ee.EEException: Earth Engine...` | Vérifiez l'authentification (voir « Authentification Earth Engine ») |
| `FileNotFoundError: modèle non trouvé` | Entraînez d'abord le modèle avec `train_model.py` |
| `Parcelle hors zone` | Dessinez la parcelle au Maroc |
| `Parcelle trop grande` | Dessinez une parcelle < 10 km² |
| `CHIRPS / ERA5-Land : x jour(s) disponibles` | Données pas encore publiées : choisissez une date plus ancienne |
| `Sentinel-2 : pas assez d'images sans nuages` | Choisissez une autre date ou élargissez la fenêtre du composite |
| `ModuleNotFoundError` | Vérifiez que vous êtes dans le bon environnement virtuel |

---

## 📄 Licence

Ce projet est distribué sous licence MIT. Voir le fichier `LICENSE` pour plus de détails.

---

## 🙏 Crédits

- Données Sentinel-2 : Copernicus Programme de l'Union Européenne
- Données CHIRPS : Climate Hazards Group, UCSB
- Données ERA5-Land : Copernicus Climate Change Service (C3S)
- Framework : Streamlit, Plotly, scikit-learn, Google Earth Engine
