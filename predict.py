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

# Seuils d'alerte par indice (type de culture = générique ici)
# Ces seuils sont indicatifs et devraient être ajustés par culture
HEALTHY_RANGES = {
    "NDVI": {"min": 0.3, "max": 0.8, "description": "Vigueur de la végétation"},
    "NDWI": {"min": 0.2, "max": 0.7, "description": "Contenu en eau végétale"},
    "MSI": {"min": 0.0, "max": 1.2, "description": "Stress hydrique (bas = sain)"},
    "SAVI": {"min": 0.2, "max": 0.7, "description": "NDVI corrigé du sol"},
    "EVI": {"min": 0.2, "max": 0.6, "description": "Indice amélioré de végétation"},
}


# ---------------------------------------------------------------------------
# Recommandations structurées
# ---------------------------------------------------------------------------
RECOMMENDATIONS_DB = {
    0: {  # Normal
        "level": "info",
        "title": "Stress hydrique normal",
        "actions": [
            "Maintenir l'irrigation existante selon le calendrier cultural.",
            "Continuer le suivi hebdomadaire des indices de végétation.",
            "Surveiller l'évolution du NDWI pour anticiper tout changement.",
        ],
        "priority": "low",
    },
    1: {  # Modéré
        "level": "warning",
        "title": "Stress hydrique modéré détecté",
        "actions": [
            "Augmenter la fréquence d'irrigation (+20 à 30 %% d'apport).",
            "Surveiller les parcelles tous les 2 à 3 jours.",
            "Vérifier le contenu en eau du sol (sonde ou estimation NDWI).",
            "Envisager une irrigation de secours si sécheresse persistante.",
        ],
        "priority": "medium",
    },
    2: {  # Sévère
        "level": "critical",
        "title": "Stress hydrique SÉVÈRE",
        "actions": [
            "IRRIGATION PRIORITAIRE : augmenter les apports de +50 %% immédiatement.",
            "Surveillance quotidienne obligatoire.",
            "Vérifier le système d'irrigation (fuites, obstructions, pression).",
            "Envisager des mesures d'urgence : paillage, filets d'ombrage, irrigation nocturne.",
            "Contacter un agronome pour évaluation sur le terrain.",
        ],
        "priority": "high",
    },
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

    def get_recommendations(self, prediction: Dict[str, Any]) -> Dict[str, Any]:
        """
        Génère des recommandations structurées basées sur la prédiction.

        Args:
            prediction: Résultat de predict()

        Returns:
            Dict: Recommandations structurées (niveau, titre, actions, priorité)
        """
        class_idx = prediction["class_index"]
        rec = RECOMMENDATIONS_DB.get(class_idx, RECOMMENDATIONS_DB[0]).copy()
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

    def generate_report_data(self, prediction: Dict[str, Any], data: Dict[str, float]) -> Dict[str, Any]:
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
        recommendations = self.get_recommendations(prediction)
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
