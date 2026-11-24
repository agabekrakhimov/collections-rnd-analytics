"""
02_eda_signals.py
-----------------
Exploratory data analysis + behavioural-signal discovery for the collections
portfolio. Produces publication-quality PNG charts (saved to ../outputs/charts)
and prints the key findings that feed the insights report.

Run after 01_generate_data.py:
    python 02_eda_signals.py
"""

import json
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib as mpl

from metrics import (
    build_kpis,
    channel_effectiveness,
    ptp_lift,
    recovery_by_bucket,
    recovery_by_engaged_band,
)

DATA = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(os.path.dirname(__file__), "..", "outputs", "charts")
os.makedirs(OUT, exist_ok=True)

# ---- shared styling ---------------------------------------------------------
mpl.rcParams.update({
    "figure.dpi": 120, "savefig.dpi": 120, "font.size": 11,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.titlesize": 13, "axes.titleweight": "bold",
    "axes.grid": True, "grid.alpha": 0.25,
})
TEAL, CORAL, NAVY = "#1f9e89", "#e8743b", "#2c3e50"

accounts = pd.read_csv(os.path.join(DATA, "accounts.csv"))
contacts = pd.read_csv(os.path.join(DATA, "contacts.csv"))

print("=" * 64)
print("EDA & BEHAVIOURAL SIGNALS")
print("=" * 64)
print(f"Overall 60-day recovery rate: {accounts['recovered_60d'].mean():.1%}")
print(f"Total balance at risk: ${accounts['outstanding_balance'].sum():,.0f}")
print(f"Total recovered:       ${accounts['amount_recovered'].sum():,.0f}")

# ---------------------------------------------------------------------------
# CHART 1 — Recovery rate by delinquency bucket
# ---------------------------------------------------------------------------
g = recovery_by_bucket(accounts)
fig, ax = plt.subplots(figsize=(7.5, 4.2))
bars = ax.bar(g.index, g.values * 100, color=TEAL)
ax.bar_label(bars, fmt="%.0f%%", padding=3)
ax.set_ylabel("60-day recovery rate")
ax.set_title("Recovery rate falls sharply with days-past-due at entry")
ax.set_ylim(0, max(g.values * 100) * 1.2)
plt.tight_layout(); plt.savefig(os.path.join(OUT, "01_recovery_by_bucket.png")); plt.close()
print("\n[1] Recovery by bucket:\n", (g * 100).round(1).to_string())

# ---------------------------------------------------------------------------
# CHART 2 — Channel engagement & promise-to-pay rate
# ---------------------------------------------------------------------------
ch = channel_effectiveness(contacts)
x = np.arange(len(ch)); w = 0.38
fig, ax = plt.subplots(figsize=(7.5, 4.2))
ax.bar(x - w/2, ch["engagement"] * 100, w, label="Engagement rate", color=TEAL)
ax.bar(x + w/2, ch["ptp"] * 100, w, label="Promise-to-pay rate", color=CORAL)
ax.set_xticks(x); ax.set_xticklabels([c.upper() for c in ch.index])
ax.set_ylabel("%"); ax.set_title("Channel effectiveness: calls & WhatsApp lead engagement")
ax.legend()
plt.tight_layout(); plt.savefig(os.path.join(OUT, "02_channel_effectiveness.png")); plt.close()
print("\n[2] Channel effectiveness:\n", (ch * 100).round(1).to_string())

# ---------------------------------------------------------------------------
# CHART 3 — Best-time-to-contact heatmap (weekday x hour)
# ---------------------------------------------------------------------------
piv = (contacts.groupby(["weekday", "contact_hour"])["engaged"].mean()
       .unstack("contact_hour"))
fig, ax = plt.subplots(figsize=(9, 4))
im = ax.imshow(piv.values, aspect="auto", cmap="viridis")
ax.set_yticks(range(7)); ax.set_yticklabels(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"])
ax.set_xticks(range(len(piv.columns))); ax.set_xticklabels(piv.columns)
ax.set_xlabel("Hour of day"); ax.set_title("Engagement heatmap — evenings & weekends win")
fig.colorbar(im, ax=ax, label="Engagement rate")
plt.tight_layout(); plt.savefig(os.path.join(OUT, "03_contact_timing_heatmap.png")); plt.close()

# ---------------------------------------------------------------------------
# CHART 4 — Contact intensity vs recovery (diminishing returns?)
# ---------------------------------------------------------------------------
order = ["0", "1", "2-3", "4+"]
ig = recovery_by_engaged_band(accounts)
fig, ax = plt.subplots(figsize=(7.5, 4.2))
ax.plot(order, ig.values * 100, "-o", color=NAVY, linewidth=2.5, markersize=9)
for xi, yi in zip(order, ig.values * 100):
    ax.annotate(f"{yi:.0f}%", (xi, yi), textcoords="offset points", xytext=(0, 9), ha="center")
ax.set_xlabel("Engaged (answered) contacts"); ax.set_ylabel("Recovery rate")
ax.set_title("Engaged conversations drive recovery — but returns flatten")
plt.tight_layout(); plt.savefig(os.path.join(OUT, "04_contact_intensity.png")); plt.close()
print("\n[4] Recovery by engaged-contact band:\n", (ig * 100).round(1).to_string())

# ---------------------------------------------------------------------------
# CHART 5 — Promise-to-pay lift, stratified by risk band
# ---------------------------------------------------------------------------
lift = ptp_lift(accounts)
x = np.arange(len(lift)); w = 0.38
fig, ax = plt.subplots(figsize=(7.5, 4.2))
ax.bar(x - w/2, lift["No PTP"] * 100, w, label="No PTP", color="#b0b8c1")
ax.bar(x + w/2, lift["PTP secured"] * 100, w, label="PTP secured", color=TEAL)
ax.set_xticks(x); ax.set_xticklabels([r.title() for r in lift.index])
ax.set_ylabel("Recovery rate"); ax.set_title("Securing a promise-to-pay lifts recovery in every risk band")
ax.legend()
plt.tight_layout(); plt.savefig(os.path.join(OUT, "05_ptp_lift.png")); plt.close()
print("\n[5] PTP lift by risk band:\n", (lift * 100).round(1).to_string())

# save a small KPI json for the dashboard. allow_nan=False so an empty
# bucket cannot be written as NaN (that file is not valid JSON).
kpis = build_kpis(accounts, contacts)
with open(os.path.join(DATA, "kpis.json"), "w") as f:
    json.dump(kpis, f, indent=2, allow_nan=False)

print("\nCharts saved to outputs/charts/. EDA complete.")
