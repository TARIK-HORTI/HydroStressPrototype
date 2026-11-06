"""
train_model.py
===============
Module d'entraînement du modèle Random Forest pour la prédiction
du stress hydrique des cultures.

Améliorations majeures :
- Pipeline sklearn (StandardScaler + RandomForest) pour éviter toute fuite de données
- Split Train / Validation / Test strict
- GridSearchCV pour l'optimisation des hyperparamètres
- CalibratedClassifierCV pour calibrer les probabilités
- Métriques complètes : accuracy, precision, recall, F1, ROC-AUC, matrice normalisée
- Sauvegarde versionnée du modèle

Sortie : Classification du stress hydrique (0: normal, 1: modéré, 2: sévère)
"""

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import (
    train_test_split, GridSearchCV, StratifiedKFold, StratifiedGroupKFold, GroupShuffleSplit,
)
import sklearn
from sklearn.pipeline import Pipeline
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import (
    classification_report, confusion_matrix, accuracy_score,
    precision_score, recall_score, f1_score, roc_auc_score,
    ConfusionMatrixDisplay
)
import argparse
import joblib
import json
import logging
from pathlib import Path
from typing import Tuple, Dict, List, Any
from datetime import datetime

# Reproductibilité complète
import os
os.environ["PYTHONHASHSEED"] = "42"
np.random.seed(42)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
FEATURE_COLUMNS = [
    # Indices spectraux — moyennes
    "NDVI_mean", "NDWI_mean", "MSI_mean", "SAVI_mean", "EVI_mean",
    # Indices spectraux — min / max / std
    "NDVI_min", "NDVI_max", "NDVI_std",
    "NDWI_std",
    "MSI_min", "MSI_max", "MSI_std",
    # CHIRPS
    "precipitation_total_30j", "precipitation_total_7j", "precipitation_mean",
    "max_consecutive_dry_days", "rainy_days_count",
    # ERA5-Land
    "temperature_mean", "temperature_max", "temperature_min",
    "humidity_mean", "humidity_min",
    # Temporel cyclique
    "day_of_year_sin", "day_of_year_cos",
    # Site : situe la parcelle dans son climat (permet un modèle pour tout le Maroc)
    "elevation_m", "precip_annual_normal_mm",
]

LABEL_COLUMN = "stress_class"

# Grille d'hyperparamètres pour GridSearchCV
PARAM_GRID = {
    "rf__n_estimators": [100, 150, 200],
    "rf__max_depth": [10, 15, 20, None],
    "rf__min_samples_split": [2, 5, 10],
    "rf__min_samples_leaf": [1, 2, 4],
}


# ---------------------------------------------------------------------------
# Classe modèle
# ---------------------------------------------------------------------------
class HydroStressModel:
    """
    Modèle de prédiction du stress hydrique basé sur Random Forest
    avec pipeline complet (scaling + classification + calibration).
    """

    def __init__(self, random_state: int = 42):
        """
        Initialise le pipeline de modélisation.

        Le pipeline comprend :
        1. StandardScaler (normalisation Z-score, fitté UNIQUEMENT sur le train)
        2. RandomForestClassifier (forêt aléatoire avec class_weight='balanced')
        3. CalibratedClassifierCV (calibration Platt/isotonique des probabilités)

        Args:
            random_state: Seed pour la reproductibilité
        """
        self.random_state = random_state
        self.pipeline = None
        self.best_params = None
        self.cv_results = None
        self.is_trained = False

        # Métadonnées de traçabilité
        self.metadata = {
            "created_at": datetime.now().isoformat(),
            "random_state": random_state,
            "feature_columns": FEATURE_COLUMNS,
            "label_column": LABEL_COLUMN,
            "sklearn_version": sklearn.__version__,
            "region": "Maroc",
        }

        logger.info("✓ Modèle HydroStress initialisé (pipeline scaler + RF + calibration)")

    def _build_pipeline(self, rf_kwargs: Dict[str, Any] = None) -> Pipeline:
        """
        Construit le pipeline sklearn complet.

        Args:
            rf_kwargs: Paramètres du RandomForest (pour GridSearchCV)

        Returns:
            Pipeline: Pipeline sklearn
        """
        if rf_kwargs is None:
            rf_kwargs = {
                "n_estimators": 150,
                "max_depth": 15,
                "min_samples_split": 5,
                "min_samples_leaf": 2,
                "random_state": self.random_state,
                "n_jobs": -1,
                "class_weight": "balanced",
            }

        # Le RandomForest brut (sera calibré après)
        base_rf = RandomForestClassifier(**rf_kwargs)

        # Pipeline : scaler -> RF -> calibration
        # Note : CalibratedClassifierCV entoure le pipeline complet
        pipe = Pipeline([
            ("scaler", StandardScaler()),
            ("rf", base_rf),
        ])

        return pipe

    def prepare_data(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series]:
        """
        Prépare les features et labels à partir d'un DataFrame brut.

        Vérifie :
        - Présence des colonnes requises
        - Absence de valeurs manquantes (erreur : à nettoyer en amont)
        - Validité des labels (0, 1, 2)

        Args:
            df: DataFrame d'entraînement

        Returns:
            Tuple[pd.DataFrame, pd.Series]: (X, y)
        """
        # Vérifie les colonnes
        missing_cols = [c for c in FEATURE_COLUMNS if c not in df.columns]
        if missing_cols:
            raise ValueError(f"Colonnes manquantes dans le dataset : {missing_cols}")

        if LABEL_COLUMN not in df.columns:
            raise ValueError(f"Colonne de label '{LABEL_COLUMN}' manquante.")

        X = df[FEATURE_COLUMNS].copy()
        y = df[LABEL_COLUMN].copy()

        # Vérifie les labels
        invalid_labels = y[~y.isin([0, 1, 2])]
        if not invalid_labels.empty:
            raise ValueError(f"Labels invalides trouvés : {invalid_labels.unique()}. Attendu : [0, 1, 2].")

        # Gestion des valeurs manquantes
        na_count = X.isna().sum().sum()
        if na_count > 0:
            bad = X.columns[X.isna().any()].tolist()
            raise ValueError(
                f"{na_count} valeurs manquantes dans {bad}. Nettoyez le dataset avant l'entraînement."
            )

        # Vérification des ranges (warnings uniquement)
        for col in ["NDVI_mean", "NDWI_mean", "SAVI_mean", "EVI_mean"]:
            if (X[col] < -1).any() or (X[col] > 1).any():
                logger.warning(f"Valeurs {col} hors range [-1, 1] détectées.")
        if (X["MSI_mean"] < 0).any():
            logger.warning("Valeurs MSI_mean négatives détectées.")

        logger.info(f"✓ Données préparées : {len(X)} échantillons, {len(FEATURE_COLUMNS)} features")
        return X, y

    def train(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_val: pd.DataFrame = None,
        y_val: pd.Series = None,
        use_grid_search: bool = True,
        cv_folds: int = 5,
        groups_train: pd.Series = None,
    ) -> Dict[str, Any]:
        """
        Entraîne le modèle avec GridSearchCV et calibration.

        Workflow :
        1. GridSearchCV sur le train set (validation croisée interne)
        2. Réentraînement du meilleur modèle sur train + val
        3. Calibration des probabilités (sigmoïde, CV interne sur train + val)

        Si groups_train est fourni (ex. identifiant de parcelle), la validation
        croisée garde chaque groupe dans un seul fold pour éviter les fuites.

        Args:
            X_train: Features d'entraînement
            y_train: Labels d'entraînement
            X_val: Features de validation (optionnel, utilisé pour le réentraînement final)
            y_val: Labels de validation (optionnel)
            use_grid_search: Active l'optimisation des hyperparamètres
        data_source: Origine des données ("synthetic", "vhi", "terrain"...),
            affichée dans le dashboard
        group_column: Colonne identifiant la parcelle ; si présente, une même
            parcelle n'apparaît jamais à la fois en train et en test
            cv_folds: Nombre de folds pour la validation croisée

        Returns:
            Dict: Résultats d'entraînement
        """
        logger.info("=" * 60)
        logger.info("DÉMARRAGE DE L'ENTRAÎNEMENT")
        logger.info("=" * 60)

        # -------------------------------------------------------------------
        # 1. GridSearchCV (si activé)
        # -------------------------------------------------------------------
        if use_grid_search:
            logger.info("GridSearchCV en cours...")
            base_pipe = self._build_pipeline()

            if groups_train is not None:
                cv = StratifiedGroupKFold(n_splits=cv_folds, shuffle=True, random_state=self.random_state)
            else:
                cv = StratifiedKFold(n_splits=cv_folds, shuffle=True, random_state=self.random_state)
            grid = GridSearchCV(
                estimator=base_pipe,
                param_grid=PARAM_GRID,
                scoring="f1_weighted",
                cv=cv,
                n_jobs=-1,
                verbose=1,
                return_train_score=True,
            )
            grid.fit(X_train, y_train, groups=groups_train)

            self.best_params = grid.best_params_
            self.cv_results = pd.DataFrame(grid.cv_results_)

            logger.info(f"✓ Meilleurs hyperparamètres : {self.best_params}")
            logger.info(f"  Meilleur F1 (CV) : {grid.best_score_:.4f}")

            # Extraction des paramètres RF optimaux
            rf_kwargs = {
                "n_estimators": self.best_params["rf__n_estimators"],
                "max_depth": self.best_params["rf__max_depth"],
                "min_samples_split": self.best_params["rf__min_samples_split"],
                "min_samples_leaf": self.best_params["rf__min_samples_leaf"],
                "random_state": self.random_state,
                "n_jobs": -1,
                "class_weight": "balanced",
            }
        else:
            rf_kwargs = None

        # -------------------------------------------------------------------
        # 2. Réentraînement sur train (+ val si fourni)
        # -------------------------------------------------------------------
        if X_val is not None and y_val is not None:
            X_combined = pd.concat([X_train, X_val], ignore_index=True)
            y_combined = pd.concat([y_train, y_val], ignore_index=True)
            logger.info(f"Réentraînement sur train+val : {len(X_combined)} échantillons")
        else:
            X_combined = X_train
            y_combined = y_train
            logger.info(f"Réentraînement sur train : {len(X_combined)} échantillons")

        # -------------------------------------------------------------------
        # 3. Calibration des probabilités
        # -------------------------------------------------------------------
        # CalibratedClassifierCV entraîne 5 copies du pipeline (meilleurs
        # hyperparamètres) sur 4/5 des données et calibre chacune sur le 1/5
        # restant : les probabilités ne sont jamais calibrées sur les données
        # ayant servi à ajuster les arbres.
        logger.info("Calibration des probabilités (sigmoïde, cv=5)...")
        calibrated = CalibratedClassifierCV(
            estimator=self._build_pipeline(rf_kwargs),
            method="sigmoid",
            cv=5,
        )
        calibrated.fit(X_combined, y_combined)

        self.pipeline = calibrated
        self.is_trained = True

        # Métadonnées
        self.metadata["best_params"] = self.best_params
        self.metadata["cv_f1_weighted"] = float(grid.best_score_) if use_grid_search else None
        self.metadata["training_samples"] = len(X_combined)
        self.metadata["feature_count"] = len(FEATURE_COLUMNS)

        logger.info("✓ Entraînement et calibration terminés")
        return {
            "best_params": self.best_params,
            "cv_score": grid.best_score_ if use_grid_search else None,
            "training_samples": len(X_combined),
        }

    def evaluate(self, X_test: pd.DataFrame, y_test: pd.Series) -> Dict[str, Any]:
        """
        Évalue le modèle sur l'ensemble de test (jamais vu pendant l'entraînement).

        Métriques calculées :
        - Accuracy, Precision, Recall, F1 (weighted)
        - ROC-AUC (ovr weighted)
        - Matrice de confusion (absolue et normalisée)
        - Rapport de classification détaillé

        Args:
            X_test: Features de test
            y_test: Labels de test

        Returns:
            Dict: Métriques d'évaluation
        """
        if not self.is_trained:
            raise RuntimeError("Le modèle n'est pas entraîné.")

        logger.info("=" * 60)
        logger.info("ÉVALUATION SUR LE TEST SET")
        logger.info("=" * 60)

        y_pred = self.pipeline.predict(X_test)
        y_proba = self.pipeline.predict_proba(X_test)

        # Métriques globales
        acc = accuracy_score(y_test, y_pred)
        prec = precision_score(y_test, y_pred, average="weighted", zero_division=0)
        rec = recall_score(y_test, y_pred, average="weighted", zero_division=0)
        f1 = f1_score(y_test, y_pred, average="weighted", zero_division=0)

        # ROC-AUC multi-classe (One-vs-Rest)
        try:
            roc_auc = roc_auc_score(y_test, y_proba, multi_class="ovr", average="weighted")
        except ValueError:
            roc_auc = None

        # Matrices de confusion
        cm_abs = confusion_matrix(y_test, y_pred, labels=[0, 1, 2])
        cm_norm = confusion_matrix(y_test, y_pred, labels=[0, 1, 2], normalize="true")

        # Rapport
        report = classification_report(
            y_test, y_pred,
            target_names=["Normal", "Modéré", "Sévère"],
            zero_division=0,
            output_dict=True
        )

        logger.info(f"  Accuracy  : {acc:.4f}")
        logger.info(f"  Precision : {prec:.4f}")
        logger.info(f"  Recall    : {rec:.4f}")
        logger.info(f"  F1-Score  : {f1:.4f}")
        if roc_auc is not None:
            logger.info(f"  ROC-AUC   : {roc_auc:.4f}")

        self.metadata["test_metrics"] = {
            "samples": int(len(y_test)),
            "accuracy": float(acc),
            "precision_weighted": float(prec),
            "recall_weighted": float(rec),
            "f1_weighted": float(f1),
            "roc_auc_ovr_weighted": float(roc_auc) if roc_auc is not None else None,
            "confusion_matrix": cm_abs.tolist(),
            "per_class": {
                name: {k: float(report[name][k]) for k in ["precision", "recall", "f1-score"]}
                for name in ["Normal", "Modéré", "Sévère"]
            },
        }

        return {
            "accuracy": acc,
            "precision": prec,
            "recall": rec,
            "f1_score": f1,
            "roc_auc": roc_auc,
            "confusion_matrix_abs": cm_abs,
            "confusion_matrix_norm": cm_norm,
            "classification_report": report,
            "predictions": y_pred,
            "probabilities": y_proba,
        }

    def get_feature_importance(self) -> pd.DataFrame:
        """
        Retourne l'importance des features du Random Forest.

        Returns:
            pd.DataFrame: Features triées par importance décroissante
        """
        if not self.is_trained:
            raise RuntimeError("Le modèle n'est pas entraîné.")

        # Moyenne sur les 5 Random Forests du modèle calibré
        importances = np.mean([
            cc.estimator.named_steps["rf"].feature_importances_
            for cc in self.pipeline.calibrated_classifiers_
        ], axis=0)

        df = pd.DataFrame({
            "feature": FEATURE_COLUMNS,
            "importance": importances,
        }).sort_values("importance", ascending=False)

        logger.info("Top 10 features importantes :")
        for _, row in df.head(10).iterrows():
            logger.info(f"  {row['feature']:<25s} : {row['importance']:.4f}")

        return df

    def save(self, filepath: str) -> None:
        """
        Sauvegarde le modèle, les métadonnées et les résultats.

        Args:
            filepath: Chemin de sauvegarde (sans extension)
        """
        if not self.is_trained:
            logger.warning("Sauvegarde d'un modèle non entraîné.")

        Path(filepath).parent.mkdir(parents=True, exist_ok=True)

        # Sauvegarde du pipeline complet (inclut scaler + RF + calibration)
        joblib.dump(self.pipeline, f"{filepath}_pipeline.joblib")

        # Métadonnées JSON
        with open(f"{filepath}_metadata.json", "w", encoding="utf-8") as f:
            json.dump(self.metadata, f, indent=2, default=str)

        logger.info(f"✓ Modèle sauvegardé : {filepath}_pipeline.joblib")
        logger.info(f"✓ Métadonnées : {filepath}_metadata.json")

    def load(self, filepath: str) -> None:
        """
        Charge un modèle précédemment sauvegardé.

        Args:
            filepath: Chemin de chargement (sans extension)
        """
        pipeline_path = f"{filepath}_pipeline.joblib"
        meta_path = f"{filepath}_metadata.json"

        if not Path(pipeline_path).exists():
            raise FileNotFoundError(f"Modèle non trouvé : {pipeline_path}")

        self.pipeline = joblib.load(pipeline_path)

        with open(meta_path, "r", encoding="utf-8") as f:
            self.metadata = json.load(f)

        self.is_trained = True
        logger.info(f"✓ Modèle chargé depuis {filepath}")


# ---------------------------------------------------------------------------
# Fonction d'entraînement de production
# ---------------------------------------------------------------------------
def train_production_model(
    data_file: str,
    output_path: str = "models/hydrostress",
    test_size: float = 0.15,
    val_size: float = 0.15,
    use_grid_search: bool = True,
    data_source: str = "unknown",
    group_column: str = "parcel_id",
) -> Tuple[HydroStressModel, Dict[str, Any]]:
    """
    Pipeline complet d'entraînement d'un modèle de production.

    Args:
        data_file: Chemin du CSV d'entraînement
        output_path: Chemin de sauvegarde
        test_size: Proportion du test set (0.0 - 1.0)
        val_size: Proportion du validation set (0.0 - 1.0)
        use_grid_search: Active l'optimisation des hyperparamètres
        data_source: Origine des données ("synthetic", "vhi", "terrain"...),
            affichée dans le dashboard
        group_column: Colonne identifiant la parcelle ; si présente, une même
            parcelle n'apparaît jamais à la fois en train et en test

    Returns:
        Tuple[HydroStressModel, Dict]: Modèle entraîné et résultats
    """
    logger.info("=" * 60)
    logger.info("ENTRAÎNEMENT DU MODÈLE HYDROSTRESS — PRODUCTION")
    logger.info("=" * 60)

    # Chargement
    try:
        df = pd.read_csv(data_file)
        logger.info(f"Dataset chargé : {len(df)} échantillons, {len(df.columns)} colonnes")
    except Exception as e:
        raise RuntimeError(f"Impossible de charger le dataset : {e}")

    y_full = df[LABEL_COLUMN]
    groups = df[group_column] if group_column in df.columns else None

    if groups is not None:
        # Split par parcelle : évite qu'une parcelle soit vue en train et en test
        logger.info(f"Split groupé par '{group_column}' ({groups.nunique()} parcelles)")
        outer = GroupShuffleSplit(n_splits=1, test_size=val_size + test_size, random_state=42)
        train_idx, rest_idx = next(outer.split(df, y_full, groups))
        rest = df.iloc[rest_idx]
        inner = GroupShuffleSplit(n_splits=1, test_size=test_size / (val_size + test_size), random_state=42)
        val_idx, test_idx = next(inner.split(rest, rest[LABEL_COLUMN], rest[group_column]))
        X_train_full, X_val, X_test = df.iloc[train_idx], rest.iloc[val_idx], rest.iloc[test_idx]
        y_train_full, y_val, y_test = (part[LABEL_COLUMN] for part in (X_train_full, X_val, X_test))
    else:
        X_train_full, X_val_test, y_train_full, y_val_test = train_test_split(
            df, y_full, test_size=val_size + test_size, random_state=42, stratify=y_full
        )
        X_val, X_test, y_val, y_test = train_test_split(
            X_val_test, y_val_test, test_size=test_size / (val_size + test_size),
            random_state=42, stratify=y_val_test,
        )

    logger.info(f"Split : train={len(X_train_full)}, val={len(X_val)}, test={len(X_test)}")

    # Distribution des classes
    for name, y in [("Train", y_train_full), ("Val", y_val), ("Test", y_test)]:
        dist = y.value_counts().sort_index()
        logger.info(f"  {name} : {dict(dist)}")

    # Préparation des features
    model = HydroStressModel(random_state=42)
    model.metadata["data_source"] = data_source
    model.metadata["data_file"] = str(data_file)
    groups_train = X_train_full[group_column].reset_index(drop=True) if groups is not None else None
    X_train, y_train = model.prepare_data(X_train_full)
    X_val, y_val = model.prepare_data(X_val)
    X_test, y_test = model.prepare_data(X_test)

    # Entraînement
    train_results = model.train(
        X_train, y_train,
        X_val=X_val, y_val=y_val,
        use_grid_search=use_grid_search,
        groups_train=groups_train,
    )

    # Évaluation
    eval_results = model.evaluate(X_test, y_test)

    # Importance des features
    importance = model.get_feature_importance()

    # Sauvegarde
    model.save(output_path)

    # Résumé
    results = {
        "model": model,
        "train_results": train_results,
        "eval_results": eval_results,
        "feature_importance": importance,
    }

    logger.info("=" * 60)
    logger.info("ENTRAÎNEMENT TERMINÉ")
    logger.info("=" * 60)

    return model, results


# ---------------------------------------------------------------------------
# Point d'entrée
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Entraîne le modèle HydroStress.")
    parser.add_argument("data_file", help="CSV d'entraînement (24 features + stress_class)")
    parser.add_argument("--output", default="models/hydrostress")
    parser.add_argument("--source", default="unknown",
                        help="Origine des données : synthetic, vhi, terrain...")
    parser.add_argument("--no-grid-search", action="store_true")
    args = parser.parse_args()
    train_production_model(
        args.data_file, output_path=args.output,
        use_grid_search=not args.no_grid_search, data_source=args.source,
    )


if __name__ == "__main__":
    main()
