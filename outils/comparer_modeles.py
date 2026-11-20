"""Compare, sur des campagnes RÉELLES jamais vues (leave-one-campaign-out), le modèle synthétique, le modèle réel
et les mélanges synthétique + réel.  Usage : python outils/comparer_modeles.py data/<ferme>/dataset.csv"""
import sys
import warnings

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import accuracy_score, balanced_accuracy_score, f1_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore")
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))
from train_model import FEATURE_COLUMNS  # noqa: E402

real = pd.read_csv(sys.argv[1])
synth = pd.read_csv(str(__import__("pathlib").Path(__file__).resolve().parents[1] / "training_data.csv"))
real = real[real["stress_class"].notna()].reset_index(drop=True)
print("real", real.shape, real["stress_class"].value_counts().sort_index().to_dict())


def pipe(**kw):
    rf = dict(n_estimators=300, max_depth=15, min_samples_split=2, min_samples_leaf=1, class_weight="balanced",
              random_state=42, n_jobs=-1)
    rf.update(kw)
    return Pipeline([("imp", SimpleImputer(strategy="median")), ("sc", StandardScaler()), ("rf", RandomForestClassifier(**rf))])


Xs, ys = synth[FEATURE_COLUMNS], synth["stress_class"].astype(int)
camps = [c for c, n in real["campagne"].value_counts().items() if n >= 10]


def loco(name, fit_fn):
    yt, yp = [], []
    for c in camps:
        test = real[real["campagne"] == c]
        train = real[real["campagne"] != c]
        model = fit_fn(train)
        yt += list(test["stress_class"].astype(int))
        yp += list(model.predict(test[FEATURE_COLUMNS]))
    yt, yp = np.array(yt), np.array(yp)
    res = dict(acc=accuracy_score(yt, yp), bal_acc=balanced_accuracy_score(yt, yp),
               f1_macro=f1_score(yt, yp, average="macro"), f1_w=f1_score(yt, yp, average="weighted"),
               severe_recall=float(((yp == 2) & (yt == 2)).sum() / max((yt == 2).sum(), 1)))
    print(f"{name:34s} " + "  ".join(f"{k}={v:.3f}" for k, v in res.items()))
    return res


results = {}
synth_model = pipe().fit(Xs, ys)
results["synthetique seul"] = loco("synthetique seul", lambda tr: synth_model)
results["reel seul"] = loco("reel seul", lambda tr: pipe(max_depth=10, min_samples_leaf=4, min_samples_split=10)
                            .fit(tr[FEATURE_COLUMNS], tr["stress_class"].astype(int)))
for w in (1, 5, 10, 20, 40):
    def fit(tr, w=w):
        X = pd.concat([Xs, tr[FEATURE_COLUMNS]], ignore_index=True)
        y = pd.concat([ys, tr["stress_class"].astype(int)], ignore_index=True)
        sw = np.r_[np.ones(len(Xs)), np.full(len(tr), float(w))]
        return pipe().fit(X, y, rf__sample_weight=sw)
    results[f"combine poids reel x{w}"] = loco(f"combine poids reel x{w}", fit)
# Errachidia synthetic zone only + real
er = synth[synth["zone"] == "errachidia"]
for w in (1, 5):
    def fit(tr, w=w):
        X = pd.concat([er[FEATURE_COLUMNS], tr[FEATURE_COLUMNS]], ignore_index=True)
        y = pd.concat([er["stress_class"].astype(int), tr["stress_class"].astype(int)], ignore_index=True)
        sw = np.r_[np.ones(len(er)), np.full(len(tr), float(w))]
        return pipe().fit(X, y, rf__sample_weight=sw)
    results[f"errachidia synth + reel x{w}"] = loco(f"errachidia synth + reel x{w}", fit)
print(pd.DataFrame(results).T.round(3).to_string())
