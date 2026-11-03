"""
predict.py
===========
Module de prédiction du stress hydrique pour de nouvelles données.

Fonctionnalités :
- Chargement du pipeline complet (scaler + RF + calibration)
- Validation des ranges des indices spectraux
- Prédiction vectorisée (batch)
- Probabilités calibrées
- Recommandations structurées (séparation logique / présentation)
- Traçabilité des prédictions
"""

import numpy as np
import pandas as pd
import joblib
import json
import sklearn
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constantes métier
# ---------------------------------------------------------------------------
CLASS_NAMES = ["Normal", "Modéré", "Sévère"]
CLASS_COLORS_HEX = ["#22c55e", "#f59e0b", "#ef4444"]  # Vert, Orange, Rouge

# Ranges physiologiques des indices (pour la validation)
INDEX_RANGES = {
    "NDVI_mean": (-1.0, 1.0),
    "NDWI_mean": (-1.0, 1.0),
    "MSI_mean": (0.0, 10.0),
    "SAVI_mean": (-1.0, 1.0),
    "EVI_mean": (-1.0, 1.0),
}

# Seuils indicatifs pour les parcelles irriguées des oasis d'Errachidia
# (palmeraies avec cultures sous-jacentes, luzerne, céréales). Le sol nu
# désertique environnant a un NDVI ~0.08-0.15. À affiner avec des relevés terrain.
HEALTHY_RANGES = {
    "NDVI": {"min": 0.25, "max": 0.75, "description": "Vigueur de la végétation"},
    "NDWI": {"min": 0.0, "max": 0.5, "description": "Contenu en eau végétale"},
    "MSI": {"min": 0.0, "max": 1.0, "description": "Stress hydrique (bas = sain)"},
    "SAVI": {"min": 0.18, "max": 0.6, "description": "NDVI corrigé du sol"},
    "EVI": {"min": 0.15, "max": 0.55, "description": "Indice amélioré de végétation"},
}


# ---------------------------------------------------------------------------
# Recommandations — province d'Errachidia
# ---------------------------------------------------------------------------
RECOMMENDATIONS_DB = {
    0: {  # Normal
        "level": "info",
        "title": "Stress hydrique normal",
        "actions": [
            "Maintenir le calendrier d'irrigation actuel (tour d'eau de la séguia, khettara ou forage).",
            "Continuer le suivi des indices toutes les 1 à 2 semaines (revisite Sentinel-2 : 5 jours).",
            "En été (juin-août), anticiper : les besoins augmentent fortement avec des maximales > 40 °C.",
        ],
        "priority": "low",
    },
    1: {  # Modéré
        "level": "warning",
        "title": "Stress hydrique modéré détecté",
        "actions": [
            "Rapprocher les irrigations : +20 à 30 % d'apport, de préférence tôt le matin ou le soir.",
            "Vérifier le réseau goutte-à-goutte (colmatage des goutteurs, pression) ou l'état des séguias.",
            "Pailler le sol (palmes sèches, résidus de luzerne) pour limiter l'évaporation.",
            "Surveiller la parcelle tous les 2 à 3 jours.",
        ],
        "priority": "medium",
    },
    2: {  # Sévère
        "level": "critical",
        "title": "Stress hydrique SÉVÈRE",
        "actions": [
            "IRRIGATION PRIORITAIRE : augmenter les apports de +50 % dès que possible.",
            "Prioriser les cultures pérennes (palmier dattier, olivier) si l'eau est limitée.",
            "Contrôler le niveau du puits / forage et la salinité de l'eau d'irrigation.",
            "Contacter l'ORMVA du Tafilalet ou un technicien agricole pour une visite terrain.",
        ],
        "priority": "high",
    },
}

# Conseils complémentaires par culture (classe 1 et 2)
CROP_TIPS = {
    "Palmier dattier": [
        "Palmier dattier : irriguer en cuvette au pied, surtout pendant la nouaison et le grossissement des dattes (avril-septembre).",
    ],
    "Luzerne": [
        "Luzerne : éviter la coupe pendant le pic de stress et irriguer juste après chaque coupe.",
    ],
    "Céréales (blé / orge)": [
        "Céréales : le stress au tallage et à l'épiaison (février-avril) a l'impact le plus fort sur le rendement.",
    ],
    "Olivier": [
        "Olivier : un apport à la floraison et au grossissement des fruits limite la chute de production.",
    ],
    "Maraîchage": [
        "Maraîchage : passer à des irrigations courtes et fréquentes, ombrage léger aux heures chaudes.",
    ],
}


# ---------------------------------------------------------------------------
# Prédicteur
# ---------------------------------------------------------------------------
class HydroStressPredictor:
    """
    Effectue les prédictions de stress hydrique avec un modèle entraîné.
    """

    def __init__(self, model_path: str = "models/hydrostress"):
        """
        Initialise le prédicteur en chargeant le pipeline sauvegardé.

        Args:
            model_path: Chemin du modèle (sans extension _pipeline.joblib)

        Raises:
            FileNotFoundError: Si le modèle n'existe pas
            RuntimeError: Si les métadonnées sont incompatibles
        """
        self.model_path = model_path
        self.pipeline = None
        self.metadata = None
        self.feature_columns = None

        self._load_model()
        logger.info("✓ Prédicteur initialisé et prêt")

    def _load_model(self) -> None:
        """Charge le pipeline et les métadonnées depuis le disque."""
        pipeline_file = f"{self.model_path}_pipeline.joblib"
        meta_file = f"{self.model_path}_metadata.json"

        if not Path(pipeline_file).exists():
            raise FileNotFoundError(
                f"Modèle non trouvé : {pipeline_file}. "
                f"Exécutez d'abord train_model.py pour entraîner un modèle."
            )

        self.pipeline = joblib.load(pipeline_file)

        with open(meta_file, "r", encoding="utf-8") as f:
            self.metadata = json.load(f)

        self.feature_columns = self.metadata.get("feature_columns", [])

        trained_with = self.metadata.get("sklearn_version")
        if trained_with and trained_with != sklearn.__version__:
            logger.warning(
                f"Modèle entraîné avec scikit-learn {trained_with}, version installée "
                f"{sklearn.__version__} : réentraînez le modèle si les prédictions échouent."
            )
        logger.info(f"✓ Pipeline chargé : {len(self.feature_columns)} features")

    def validate_input(self, data: Dict[str, float]) -> List[str]:
        """
        Valide les valeurs d'entrée et retourne une liste de warnings.

        Vérifie :
        - Présence de toutes les features requises
        - Ranges physiologiques des indices spectraux
        - Cohérence min <= mean <= max

        Args:
            data: Dictionnaire de features

        Returns:
            List[str]: Liste des warnings (vide si tout est OK)
        """
        warnings = []

        # Vérifie les colonnes manquantes
        missing = [c for c in self.feature_columns if c not in data]
        if missing:
            warnings.append(f"Features manquantes : {missing}")
            return warnings  # On ne peut pas continuer sans toutes les features

        # Vérifie les ranges
        for col, (vmin, vmax) in INDEX_RANGES.items():
            val = data.get(col)
            if val is not None and (val < vmin or val > vmax):
                warnings.append(
                    f"{col} = {val:.3f} hors range [{vmin}, {vmax}]"
                )

        # Cohérence min <= mean <= max
        for prefix in ["NDVI", "MSI"]:
            mn = data.get(f"{prefix}_min", np.nan)
            mx = data.get(f"{prefix}_max", np.nan)
            mean = data.get(f"{prefix}_mean", np.nan)
            if not np.isnan(mn) and not np.isnan(mx) and not np.isnan(mean):
                if mn > mean:
                    warnings.append(f"{prefix}_min ({mn:.3f}) > {prefix}_mean ({mean:.3f})")
                if mean > mx:
                    warnings.append(f"{prefix}_mean ({mean:.3f}) > {prefix}_max ({mx:.3f})")

        return warnings

    def prepare_data(self, data: Dict[str, float]) -> pd.DataFrame:
        """
        Prépare un DataFrame aligné sur les features du modèle.

        Args:
            data: Dictionnaire de features

        Returns:
            pd.DataFrame: DataFrame 1 ligne avec les colonnes dans l'ordre exact
        """
        row = {col: data.get(col, 0.0) for col in self.feature_columns}
        df = pd.DataFrame([row])
        return df

    def predict(self, data: Dict[str, float]) -> Dict[str, Any]:
        """
        Effectue une prédiction unitaire de stress hydrique.

        Args:
            data: Dictionnaire de features agrégées

        Returns:
            Dict: Résultat structuré avec classe, probabilités, confiance, warnings
        """
        # Validation
        warnings = self.validate_input(data)
        if any("manquantes" in w for w in warnings):
            raise ValueError(f"Données incomplètes : {warnings}")
        nan_features = [c for c in self.feature_columns if data[c] is None or np.isnan(data[c])]
        if nan_features:
            raise ValueError(f"Valeurs manquantes (NaN) : {nan_features}")

        # Préparation
        X = self.prepare_data(data)

        # Prédiction
        pred_class = int(self.pipeline.predict(X)[0])
        proba = self.pipeline.predict_proba(X)[0]
        confidence = float(np.max(proba) * 100.0)

        # Résultat structuré
        result = {
            "prediction_id": f"pred_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}",
            "timestamp": datetime.now().isoformat(),
            "class_index": pred_class,
            "class_name": CLASS_NAMES[pred_class],
            "class_color_hex": CLASS_COLORS_HEX[pred_class],
            "confidence_percent": round(confidence, 2),
            "probabilities": {
                "normal": round(float(proba[0]) * 100, 2),
                "moderate": round(float(proba[1]) * 100, 2),
                "severe": round(float(proba[2]) * 100, 2),
            },
            "warnings": warnings,
            "input_summary": {k: round(v, 4) for k, v in data.items() if k in self.feature_columns},
        }

        logger.info(
            f"Prédiction : {result['class_name']} (confiance {result['confidence_percent']:.1f}%)"
        )
        return result

    def predict_batch(self, data_list: List[Dict[str, float]]) -> pd.DataFrame:
        """
        Effectue des prédictions vectorisées sur plusieurs parcelles.

        Cette méthode est optimisée : un seul DataFrame, un seul transform,
        une seule prédiction.

        Args:
            data_list: Liste de dictionnaires de features

        Returns:
            pd.DataFrame: Résultats des prédictions
        """
        if not data_list:
            return pd.DataFrame()

        # Construction d'un DataFrame batch
        rows = []
        for d in data_list:
            row = {col: d.get(col, 0.0) for col in self.feature_columns}
            rows.append(row)

        X_batch = pd.DataFrame(rows)

        # Prédictions vectorisées
        preds = self.pipeline.predict(X_batch)
        probas = self.pipeline.predict_proba(X_batch)

        # Assemblage des résultats
        results = []
        for i, (pred, proba) in enumerate(zip(preds, probas)):
            confidence = float(np.max(proba) * 100.0)
            results.append({
                "batch_index": i,
                "class_index": int(pred),
                "class_name": CLASS_NAMES[int(pred)],
                "class_color_hex": CLASS_COLORS_HEX[int(pred)],
                "confidence_percent": round(confidence, 2),
                "prob_normal": round(float(proba[0]) * 100, 2),
                "prob_moderate": round(float(proba[1]) * 100, 2),
                "prob_severe": round(float(proba[2]) * 100, 2),
            })

        logger.info(f"✓ Batch de {len(data_list)} prédictions terminé")
        return pd.DataFrame(results)

    def get_recommendations(self, prediction: Dict[str, Any], crop: Optional[str] = None) -> Dict[str, Any]:
        """
        Génère des recommandations structurées basées sur la prédiction.

        Args:
            prediction: Résultat de predict()
            crop: Culture de la parcelle (voir region.CROPS), optionnelle

        Returns:
            Dict: Recommandations structurées (niveau, titre, actions, priorité)
        """
        class_idx = prediction["class_index"]
        rec = dict(RECOMMENDATIONS_DB.get(class_idx, RECOMMENDATIONS_DB[0]))
        rec["actions"] = list(rec["actions"])
        if crop and class_idx > 0:
            rec["actions"] += CROP_TIPS.get(crop, [])
        rec["prediction_id"] = prediction.get("prediction_id")
        rec["confidence"] = prediction.get("confidence_percent")
        return rec

    def interpret_indices(self, data: Dict[str, float]) -> Dict[str, Dict[str, Any]]:
        """
        Interprète chaque indice spectral par rapport aux seuils physiologiques.

        Args:
            data: Données d'entrée

        Returns:
            Dict: Interprétation par indice (valeur, description, statut, range)
        """
        interpretation = {}

        for idx_name, meta in HEALTHY_RANGES.items():
            mean_key = f"{idx_name}_mean"
            val = data.get(mean_key)

            if val is None:
                status = "unknown"
            elif meta["min"] <= val <= meta["max"]:
                status = "healthy"
            elif val < meta["min"]:
                status = "low"
            else:
                status = "high"

            interpretation[idx_name] = {
                "value": round(val, 4) if val is not None else None,
                "description": meta["description"],
                "healthy_range": [meta["min"], meta["max"]],
                "status": status,
            }

        return interpretation

    def generate_report_data(self, prediction: Dict[str, Any], data: Dict[str, float],
                             crop: Optional[str] = None) -> Dict[str, Any]:
        """
        Génère un rapport structuré complet (données brutes, sans formatage).

        Ce dictionnaire peut être consommé par l'interface (Streamlit, API, etc.)
        pour un rendu visuel.

        Args:
            prediction: Résultat de predict()
            data: Données d'entrée

        Returns:
            Dict: Rapport structuré
        """
        recommendations = self.get_recommendations(prediction, crop)
        interpretation = self.interpret_indices(data)

        return {
            "prediction": prediction,
            "recommendations": recommendations,
            "indices_interpretation": interpretation,
            "model_metadata": {
                "model_path": self.model_path,
                "feature_count": len(self.feature_columns),
                "training_date": self.metadata.get("created_at"),
            },
        }

    def log_prediction(self, prediction: Dict[str, Any], filepath: str = "predictions_log.jsonl") -> None:
        """
        Sauvegarde la prédiction dans un fichier JSON Lines pour traçabilité.

        Args:
            prediction: Résultat de predict()
            filepath: Chemin du fichier de log
        """
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, "a", encoding="utf-8") as f:
            f.write(json.dumps(prediction, default=str) + "\n")


# ---------------------------------------------------------------------------
# Point d'entrée test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("Module de prédiction HydroStress.")
    print("Utilisation : predictor = HydroStressPredictor(); predictor.predict(data)")
