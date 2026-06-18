"""
03_model.py
-----------
Recovery-propensity model: predict the probability that a delinquent account
is recovered within 60 days, so collections can prioritise effort and route
treatment. Trains a regularised Logistic Regression (interpretable baseline)
and a Gradient Boosting model (performance), compares them, and exports:

    outputs/charts/06_roc_curve.png
    outputs/charts/07_feature_importance.png
    outputs/charts/08_score_deciles.png
    outputs/model_scores.csv           (account_id, recovery_probability, decile)
    outputs/model_metrics.json

Run after 01 + 02:
    python 03_model.py
"""

import os, json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib as mpl

from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.metrics import roc_auc_score, roc_curve, average_precision_score

DATA = os.path.join(os.path.dirname(__file__), "..", "data")
OUT_C = os.path.join(os.path.dirname(__file__), "..", "outputs", "charts")
OUT = os.path.join(os.path.dirname(__file__), "..", "outputs")
os.makedirs(OUT_C, exist_ok=True)

mpl.rcParams.update({"figure.dpi": 120, "savefig.dpi": 120, "font.size": 11,
                     "axes.spines.top": False, "axes.spines.right": False,
                     "axes.titlesize": 13, "axes.titleweight": "bold",
                     "axes.grid": True, "grid.alpha": 0.25})
TEAL, CORAL, NAVY = "#1f9e89", "#e8743b", "#2c3e50"

acc = pd.read_csv(os.path.join(DATA, "accounts.csv"))

# ---- feature set ------------------------------------------------------------
num = ["outstanding_balance", "dpd_at_entry", "credit_score", "prior_defaults",
       "n_contacts", "n_engaged", "promise_to_pay", "refused"]
cat = ["product", "income_band", "employment_status", "delinquency_bucket", "region"]
y = acc["recovered_60d"]
X = acc[num + cat]

X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.25, random_state=7, stratify=y)

pre = ColumnTransformer([
    ("num", StandardScaler(), num),
    ("cat", OneHotEncoder(handle_unknown="ignore"), cat),
])

models = {
    "Logistic Regression": LogisticRegression(max_iter=2000, C=1.0),
    "Gradient Boosting": GradientBoostingClassifier(random_state=7),
}

metrics, fitted = {}, {}
print("=" * 64); print("RECOVERY-PROPENSITY MODEL"); print("=" * 64)
for name, est in models.items():
    pipe = Pipeline([("pre", pre), ("clf", est)])
    pipe.fit(X_tr, y_tr)
    p = pipe.predict_proba(X_te)[:, 1]
    auc = roc_auc_score(y_te, p)
    ap = average_precision_score(y_te, p)
    metrics[name] = {"roc_auc": round(float(auc), 4), "avg_precision": round(float(ap), 4)}
    fitted[name] = pipe
    print(f"{name:>22}:  ROC-AUC = {auc:.3f}   PR-AUC = {ap:.3f}")

best_name = max(metrics, key=lambda k: metrics[k]["roc_auc"])
best = fitted[best_name]
print(f"\nBest model: {best_name}")

# ---------------------------------------------------------------------------
# CHART 6 — ROC curves
# ---------------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(6.2, 5.2))
for name, pipe in fitted.items():
    p = pipe.predict_proba(X_te)[:, 1]
    fpr, tpr, _ = roc_curve(y_te, p)
    ax.plot(fpr, tpr, linewidth=2.2, label=f"{name} (AUC={metrics[name]['roc_auc']:.3f})")
ax.plot([0, 1], [0, 1], "--", color="grey", linewidth=1)
ax.set_xlabel("False positive rate"); ax.set_ylabel("True positive rate")
ax.set_title("Recovery-propensity model — ROC"); ax.legend(loc="lower right")
plt.tight_layout(); plt.savefig(os.path.join(OUT_C, "06_roc_curve.png")); plt.close()

# ---------------------------------------------------------------------------
# CHART 7 — Feature importance (from Gradient Boosting)
# ---------------------------------------------------------------------------
gb = fitted["Gradient Boosting"]
ohe = gb.named_steps["pre"].named_transformers_["cat"]
feat_names = num + list(ohe.get_feature_names_out(cat))
imp = gb.named_steps["clf"].feature_importances_
fi = pd.Series(imp, index=feat_names).sort_values(ascending=True).tail(12)
fig, ax = plt.subplots(figsize=(7.5, 5))
ax.barh(fi.index, fi.values, color=TEAL)
ax.set_title("What drives recovery? (top features)"); ax.set_xlabel("Importance")
plt.tight_layout(); plt.savefig(os.path.join(OUT_C, "07_feature_importance.png")); plt.close()
print("\nTop drivers:\n", fi.sort_values(ascending=False).head(6).round(3).to_string())

# ---------------------------------------------------------------------------
# CHART 8 — Score deciles: does the model rank-order risk? (lift / gains)
# ---------------------------------------------------------------------------
p_all = best.predict_proba(X)[:, 1]
acc_scored = acc[["account_id", "outstanding_balance", "recovered_60d"]].copy()
acc_scored["recovery_probability"] = p_all
acc_scored["decile"] = pd.qcut(p_all, 10, labels=False, duplicates="drop") + 1
dec = acc_scored.groupby("decile")["recovered_60d"].mean() * 100
fig, ax = plt.subplots(figsize=(7.5, 4.2))
bars = ax.bar(dec.index.astype(str), dec.values, color=NAVY)
ax.bar_label(bars, fmt="%.0f%%", padding=2, fontsize=9)
ax.set_xlabel("Model score decile (10 = most likely to recover)")
ax.set_ylabel("Actual recovery rate")
ax.set_title("Model cleanly rank-orders accounts by recovery likelihood")
plt.tight_layout(); plt.savefig(os.path.join(OUT_C, "08_score_deciles.png")); plt.close()

# top vs bottom decile lift
top, bot = dec.loc[dec.index.max()], dec.loc[dec.index.min()]
print(f"\nDecile lift: top decile recovers {top:.0f}% vs bottom {bot:.0f}%  "
      f"({top/bot:.1f}x)")

# ---- exports ----------------------------------------------------------------
acc_scored.to_csv(os.path.join(OUT, "model_scores.csv"), index=False)
with open(os.path.join(OUT, "model_metrics.json"), "w") as f:
    json.dump({"models": metrics, "best_model": best_name,
               "top_decile_recovery": round(float(top), 1),
               "bottom_decile_recovery": round(float(bot), 1)}, f, indent=2)
print("\nModel artefacts saved to outputs/.")
