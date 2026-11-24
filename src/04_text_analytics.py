"""
04_text_analytics.py
---------------------
NLP on call transcripts (unstructured data) to extract *behavioural signals*
that are invisible in structured fields. This mirrors a real speech-to-text /
conversation-analytics use case: turn what borrowers actually say into features
that predict — and explain — recovery.

Steps:
  1. Rule-based intent tagging (hardship / cooperative / resistant / neutral).
  2. TF-IDF + Logistic Regression to predict recovery from transcript text only,
     proving the text carries independent signal.
  3. Surface the words most predictive of recovery vs non-recovery.

Outputs:
  outputs/charts/09_intent_recovery.png
  outputs/charts/10_predictive_words.png
  outputs/text_signal_metrics.json

Run after 01:
    python 04_text_analytics.py
"""

import os, json
import pandas as pd

from metrics import tag_intent
import matplotlib.pyplot as plt
import matplotlib as mpl

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score

DATA = os.path.join(os.path.dirname(__file__), "..", "data")
OUT_C = os.path.join(os.path.dirname(__file__), "..", "outputs", "charts")
OUT = os.path.join(os.path.dirname(__file__), "..", "outputs")
os.makedirs(OUT_C, exist_ok=True)
mpl.rcParams.update({"figure.dpi": 120, "savefig.dpi": 120, "font.size": 11,
                     "axes.spines.top": False, "axes.spines.right": False,
                     "axes.titlesize": 13, "axes.titleweight": "bold",
                     "axes.grid": True, "grid.alpha": 0.25})
TEAL, CORAL = "#1f9e89", "#e8743b"

trans = pd.read_csv(os.path.join(DATA, "transcripts.csv"))
acc = pd.read_csv(os.path.join(DATA, "accounts.csv"))[["account_id", "recovered_60d"]]
df = trans.merge(acc, on="account_id", how="left").dropna(subset=["recovered_60d"])
df["recovered_60d"] = df["recovered_60d"].astype(int)

print("=" * 64); print("CALL-TRANSCRIPT NLP"); print("=" * 64)
print(f"Transcripts analysed: {len(df)}")

# ---------------------------------------------------------------------------
# 1. Rule-based intent detection (lexicon approach)
# ---------------------------------------------------------------------------
df["intent"] = df["transcript"].apply(tag_intent)

intent_rec = df.groupby("intent")["recovered_60d"].agg(["mean", "count"]).sort_values("mean")
fig, ax = plt.subplots(figsize=(7.5, 4.2))
colors = [CORAL if i in ("resistant", "hardship") else TEAL for i in intent_rec.index]
bars = ax.bar(intent_rec.index, intent_rec["mean"] * 100, color=colors)
ax.bar_label(bars, fmt="%.0f%%", padding=3)
ax.set_ylabel("Recovery rate"); ax.set_xlabel("Detected call intent")
ax.set_title("Call intent is a strong recovery signal")
plt.tight_layout(); plt.savefig(os.path.join(OUT_C, "09_intent_recovery.png")); plt.close()
print("\nRecovery by detected intent:\n",
      (intent_rec.assign(mean=lambda d: (d["mean"]*100).round(1))).to_string())

# ---------------------------------------------------------------------------
# 2. Can transcript TEXT ALONE predict recovery? (TF-IDF + LogReg)
# ---------------------------------------------------------------------------
Xtr, Xte, ytr, yte = train_test_split(df["transcript"], df["recovered_60d"],
                                       test_size=0.25, random_state=11,
                                       stratify=df["recovered_60d"])
vec = TfidfVectorizer(ngram_range=(1, 2), min_df=5, stop_words="english")
Xtr_v, Xte_v = vec.fit_transform(Xtr), vec.transform(Xte)
clf = LogisticRegression(max_iter=1000)
clf.fit(Xtr_v, ytr)
auc = roc_auc_score(yte, clf.predict_proba(Xte_v)[:, 1])
print(f"\nText-only model ROC-AUC: {auc:.3f}  (text carries standalone signal)")

# ---------------------------------------------------------------------------
# 3. Most predictive words/phrases
# ---------------------------------------------------------------------------
coefs = pd.Series(clf.coef_[0], index=vec.get_feature_names_out())
top_pos = coefs.sort_values(ascending=False).head(8)
top_neg = coefs.sort_values().head(8)
combined = pd.concat([top_neg, top_pos])
fig, ax = plt.subplots(figsize=(7.5, 5.5))
colors = [CORAL] * len(top_neg) + [TEAL] * len(top_pos)
ax.barh(combined.index, combined.values, color=colors)
ax.axvline(0, color="black", linewidth=0.8)
ax.set_title("Words that predict recovery (teal) vs non-recovery (coral)")
ax.set_xlabel("Logistic-regression weight")
plt.tight_layout(); plt.savefig(os.path.join(OUT_C, "10_predictive_words.png")); plt.close()

with open(os.path.join(OUT, "text_signal_metrics.json"), "w") as f:
    json.dump({"text_only_roc_auc": round(float(auc), 3),
               "recovery_by_intent": {k: round(float(v), 3)
                                      for k, v in intent_rec["mean"].items()}}, f, indent=2)
print("\nText-analytics charts saved to outputs/charts/.")
