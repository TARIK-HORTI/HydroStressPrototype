# 💧 HydroStressPrototype

**Prédiction du stress hydrique des cultures par télédétection et Machine Learning**

---

## 🎯 Description

HydroStressPrototype est une application web complète de prédiction du stress hydrique des cultures. Elle combine des données satellitaires Sentinel-2, des données météorologiques (CHIRPS, ERA5-Land) et un modèle de Machine Learning (Random Forest calibré) pour classifier l'état hydrique d'une parcelle en trois classes :

- **🟢 Normal** — Aucune action requise
- **🟡 Modéré** — Surveillance renforcée et ajustement de l'irrigation
- **🔴 Sévère** — Intervention urgente nécessaire

---

## 🏗️ Architecture

```
HydroStressPrototype/
├── extract_data.py      # Extraction Sentinel-2, CHIRPS, ERA5-Land
├── train_model.py       # Entraînement Random Forest + Calibration
├── predict.py           # Prédiction avec validation et traçabilité
├── app.py               # Interface Streamlit interactive
├── requirements.txt     # Dépendances Python
└── README.md            # Documentation
```

---

## 📦 Installation

### Prérequis

- **Python** : 3.9, 3.10 ou 3.11 (numpy 1.24.x n'est pas compatible avec Python 3.12+)
- **Compte Google** avec accès à [Google Earth Engine](https://earthengine.google.com/)
- **Dataset d'entraînement** au format CSV (voir section Format CSV)

### Étapes

1. **Cloner le repository**
   ```bash
   git clone <url-du-repo>
   cd HydroStressPrototype
   ```

2. **Créer un environnement virtuel**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   # ou
   venv\Scripts\activate   # Windows
   ```

3. **Installer les dépendances**
   ```bash
   pip install -r requirements.txt
   ```

4. **Authentifier Google Earth Engine**
   ```bash
   earthengine authenticate
   ```
   Suivez les instructions pour lier votre compte Google.

---

## 🚀 Utilisation

### 1. Entraîner le modèle

Préparez un fichier CSV d'entraînement (voir format ci-dessous), puis :

```bash
python -c "from train_model import train_production_model; train_production_model('data/train.csv')"
```

Le modèle sera sauvegardé dans `models/hydrostress_pipeline.joblib`.

### 2. Lancer l'application

```bash
streamlit run app.py
```

L'application sera accessible sur `http://localhost:8501`.

### 3. Workflow d'analyse

1. **Délimiter** une parcelle sur la carte interactive (Folium)
2. **Sélectionner** une date d'analyse
3. **Extraire** les données satellites (Sentinel-2) et météorologiques (CHIRPS + ERA5-Land)
4. **Obtenir** la prédiction du stress hydrique avec probabilités calibrées
5. **Consulter** les recommandations agronomiques personnalisées

---

## 📊 Format CSV d'entraînement

Le fichier CSV doit contenir les colonnes suivantes :

### Features (22 colonnes)

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
| `precipitation_total_30j` | Cumul précipitations 30 jours | mm |
| `precipitation_total_7j` | Cumul précipitations 7 jours | mm |
| `precipitation_mean` | Moyenne journalière de précipitation | mm/jour |
| `max_consecutive_dry_days` | Max jours consécutifs sans pluie (>0.1mm) | jours |
| `rainy_days_count` | Nombre de jours avec pluie | jours |
| `temperature_mean` | Température moyenne | °C |
| `temperature_max` | Température maximale | °C |
| `temperature_min` | Température minimale | °C |
| `humidity_mean` | Humidité relative moyenne | % |
| `humidity_min` | Humidité relative minimale | % |
| `day_of_year_sin` | Composante sinus du jour de l'année | [-1, 1] |
| `day_of_year_cos` | Composante cosinus du jour de l'année | [-1, 1] |

### Label (1 colonne)

| Colonne | Description | Valeurs |
|---------|-------------|---------|
| `stress_class` | Classe de stress hydrique | `0`=Normal, `1`=Modéré, `2`=Sévère |

### Exemple de ligne

```csv
NDVI_mean,NDWI_mean,MSI_mean,SAVI_mean,EVI_mean,NDVI_min,NDVI_max,NDVI_std,NDWI_std,MSI_min,MSI_max,MSI_std,precipitation_total_30j,precipitation_total_7j,precipitation_mean,max_consecutive_dry_days,rainy_days_count,temperature_mean,temperature_max,temperature_min,humidity_mean,humidity_min,day_of_year_sin,day_of_year_cos,stress_class
0.65,0.50,0.85,0.58,0.48,0.45,0.75,0.08,0.06,0.72,1.05,0.12,45.0,12.0,1.5,5.0,10.0,28.5,35.0,22.0,60.0,45.0,0.5,0.866,0
```

---

## 🔬 Indices Spectraux

| Indice | Formule | Interprétation |
|--------|---------|----------------|
| **NDVI** | (NIR − Red) / (NIR + Red) | Vigueur de la végétation |
| **NDWI** | (NIR − SWIR) / (NIR + SWIR) | Contenu en eau de la végétation |
| **MSI** | SWIR / NIR | Stress hydrique (valeurs élevées = stress) |
| **SAVI** | ((NIR − Red) / (NIR + Red + L)) × (1 + L) | NDVI corrigé pour le sol nu |
| **EVI** | 2.5 × (NIR − Red) / (NIR + 6×Red − 7.5×Blue + 1) | Indice amélioré, moins saturé |

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
- **Calibration** : Platt scaling (sigmoïde) des probabilités
- **Classes** : 3 (Normal, Modéré, Sévère)
- **Features** : 24 (5 indices spectraux + 7 CHIRPS + 5 ERA5 + 2 cycliques)

---

## 🐛 Dépannage

| Problème | Solution |
|----------|----------|
| `ee.EEException: Earth Engine...` | Exécutez `earthengine authenticate` |
| `FileNotFoundError: modèle non trouvé` | Entraînez d'abord le modèle avec `train_model.py` |
| `ValueError: Parcelle trop grande` | Dessinez une parcelle < 10 km² |
| `Aucune image Sentinel-2` | Essayez une date plus ancienne ou élargissez la fenêtre temporelle |
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
