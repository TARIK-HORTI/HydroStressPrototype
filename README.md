# 💧 HydroStressPrototype — Errachidia

**Prédiction du stress hydrique des cultures par télédétection et Machine Learning, dans la province d'Errachidia (Drâa-Tafilalet, Maroc)**

---

## 🎯 Description

HydroStressPrototype est une application web de suivi du stress hydrique des parcelles agricoles des oasis de la province d'Errachidia : vallée du Ziz, Tafilalet (Erfoud, Rissani, Jorf, Aoufous), Ghéris (Goulmima, Tinejdad) et Boudnib. Elle combine Sentinel-2, CHIRPS, ERA5-Land et un Random Forest calibré pour classer une parcelle en trois classes :

- **🟢 Normal** — Aucune action requise
- **🟡 Modéré** — Surveillance renforcée et ajustement de l'irrigation
- **🔴 Sévère** — Intervention urgente nécessaire

L'exploitation est **contrainte à la province** : la carte est centrée sur Errachidia, les parcelles hors zone sont refusées, et les seuils, valeurs par défaut et recommandations (palmier dattier, luzerne, céréales, olivier, maraîchage) sont adaptés au contexte aride local. La configuration régionale est dans `region.py`.

> ⚠️ **Modèle fourni = données synthétiques.** `models/` contient un modèle entraîné sur un dataset synthétique calé sur le climat d'Errachidia (`generate_training_data.py`). Il sert à faire tourner l'application de bout en bout ; ses prédictions ne sont pas validées sur le terrain. Pour un modèle exploitable, construisez un dataset réel avec `build_dataset.py` ou avec vos relevés, puis réentraînez.

---

## 🏗️ Architecture

```
HydroStressPrototype/
├── region.py                  # Zone d'étude : emprise, oasis, cultures, normales climatiques
├── extract_data.py            # Extraction Sentinel-2, CHIRPS, ERA5-Land + authentification Earth Engine
├── build_dataset.py           # Dataset réel : features + étiquettes VHI (MODIS) dans les oasis
├── generate_training_data.py  # Dataset synthétique calé sur le climat d'Errachidia
├── train_model.py             # Entraînement Random Forest + calibration (CLI)
├── predict.py                 # Prédiction, interprétation, recommandations locales
├── app.py                     # Interface Streamlit
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

1. Ouvrir **📊 Analyse**, choisir une oasis dans la barre latérale et la culture de la parcelle
2. Dessiner la parcelle sur la carte (vue satellite, ≤ 10 km², dans la province)
3. Choisir la date d'analyse (ERA5-Land et CHIRPS sont publiés avec environ une semaine de retard)
4. Extraire les données puis lancer la prédiction
5. Lire les recommandations adaptées à la culture

### 3. Entraîner un modèle

```bash
# Dataset synthétique (démonstration)
python generate_training_data.py -n 1500 -o training_data.csv
python train_model.py training_data.csv --source synthetic

# Dataset réel avec étiquettes VHI (Earth Engine requis, long : plusieurs heures)
python build_dataset.py --points-per-oasis 15 --start 2019-01-01 --end 2024-12-31 --output data/errachidia_vhi.csv
python train_model.py data/errachidia_vhi.csv --source vhi
```

Si le CSV contient une colonne `parcel_id`, le découpage train/val/test et la validation croisée se font par parcelle, pour qu'une même parcelle ne soit jamais à la fois en entraînement et en test. Les métriques de test sont enregistrées dans `models/hydrostress_metadata.json` et affichées dans le **📈 Dashboard**.

#### Étiquettes VHI (`build_dataset.py`)

Le Vegetation Health Index (Kogan) compare le NDVI (MODIS MOD13Q1) et la température de surface (MODIS MOD11A2) à l'historique 2001+ du même pixel à la même période : `VHI = 0.5·VCI + 0.5·TCI`. Classes : VHI ≥ 40 → Normal, 20–40 → Modéré, < 20 → Sévère. C'est une étiquette indirecte : des observations de terrain (ORMVA du Tafilalet, agriculteurs) restent la référence pour valider le modèle.

### 4. Tests

```bash
pip install pytest
pytest -q
```

Les tests couvrent la validation des parcelles (zone, surface, auto-intersection), l'agrégation des features météo, le générateur de données et l'aller-retour entraînement → prédiction. Ils tournent sans accès Earth Engine et sont exécutés par GitHub Actions (`.github/workflows/ci.yml`).

---

## 📊 Format CSV d'entraînement

Le fichier CSV doit contenir les colonnes suivantes :

### Features (24 colonnes)

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

### Label (1 colonne)

| Colonne | Description | Valeurs |
|---------|-------------|---------|
| `stress_class` | Classe de stress hydrique | `0`=Normal, `1`=Modéré, `2`=Sévère |

### Exemple de ligne

```csv
NDVI_mean,NDWI_mean,MSI_mean,SAVI_mean,EVI_mean,NDVI_min,NDVI_max,NDVI_std,NDWI_std,MSI_min,MSI_max,MSI_std,precipitation_total_30j,precipitation_total_7j,precipitation_mean,max_consecutive_dry_days,rainy_days_count,temperature_mean,temperature_max,temperature_min,humidity_mean,humidity_min,day_of_year_sin,day_of_year_cos,stress_class
0.48,0.18,0.69,0.35,0.30,0.30,0.62,0.08,0.05,0.48,0.95,0.12,3.5,0.0,0.12,24.0,2.0,30.5,43.0,19.0,28.0,9.0,0.47,-0.88,1
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
- **Features** : 24 (5 indices spectraux + 7 CHIRPS + 5 ERA5 + 2 cycliques)

---

## 🐛 Dépannage

| Problème | Solution |
|----------|----------|
| `ee.EEException: Earth Engine...` | Vérifiez l'authentification (voir « Authentification Earth Engine ») |
| `FileNotFoundError: modèle non trouvé` | Entraînez d'abord le modèle avec `train_model.py` |
| `Parcelle hors zone` | Dessinez la parcelle dans la province d'Errachidia (rectangle bleu sur la carte) |
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
