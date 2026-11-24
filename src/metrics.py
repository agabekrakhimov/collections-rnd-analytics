"""
metrics.py
----------
Calculations shared by the generator, the EDA, and the transcript script.
No plotting and no file I/O, so the same functions can be checked on a
handful of rows.

The delinquency buckets, engaged-contact bands, and intent lexicon match
the rules already used in the analysis.
"""

import math

import pandas as pd

BUCKETS = ("1-15 DPD", "16-30 DPD", "31-60 DPD", "61-90 DPD", "90+ DPD")
ENGAGED_BANDS = ("0", "1", "2-3", "4+")

INTENT_LEXICON = {
    "hardship": ["lost my job", "hospital", "hours were cut", "emergency", "tight"],
    "cooperative": ["payment plan", "pay next week", "partial payment", "clear this", "options"],
    "resistant": ["dispute", "stop calling", "already paid", "not going to pay", "do not recognise"],
}


def delinquency_bucket(dpd):
    """Map days-past-due at entry to the portfolio bucket."""
    if pd.isna(dpd):
        raise ValueError("dpd is missing")
    d = float(dpd)
    if d <= 15:
        return "1-15 DPD"
    if d <= 30:
        return "16-30 DPD"
    if d <= 60:
        return "31-60 DPD"
    if d <= 90:
        return "61-90 DPD"
    return "90+ DPD"


def engaged_band(n_engaged):
    """Band the number of answered contacts the way the intensity chart does."""
    if pd.isna(n_engaged):
        raise ValueError("n_engaged is missing")
    n = float(n_engaged)
    if n == 0:
        return "0"
    if n == 1:
        return "1"
    if n <= 3:
        return "2-3"
    return "4+"


def risk_band(credit_score, prime_cutoff=680):
    if pd.isna(credit_score):
        raise ValueError("credit_score is missing")
    return "prime" if float(credit_score) >= prime_cutoff else "subprime"


def tag_intent(text, lexicon=None):
    """First matching lexicon wins. Missing text is treated as neutral."""
    if text is None or (isinstance(text, float) and math.isnan(text)):
        return "neutral"
    folded = str(text).lower()
    lex = INTENT_LEXICON if lexicon is None else lexicon
    for intent, keywords in lex.items():
        if any(keyword in folded for keyword in keywords):
            return intent
    return "neutral"


def contact_activity(contacts):
    """Per-account outreach totals stored on the accounts table."""
    required = {"account_id", "contact_id", "engaged", "outcome"}
    missing = required - set(contacts.columns)
    if missing:
        raise ValueError(f"contacts missing columns: {sorted(missing)}")
    return contacts.groupby("account_id", as_index=False).agg(
        n_contacts=("contact_id", "count"),
        n_engaged=("engaged", "sum"),
        promise_to_pay=("outcome", lambda s: (s == "promise_to_pay").sum()),
        refused=("outcome", lambda s: (s == "refused").sum()),
    )


def recovery_by_bucket(accounts):
    """Mean 60-day recovery for buckets that actually have accounts.

    Empty buckets are left out. Including them used to write NaN into
    kpis.json, which is not valid JSON.
    """
    present = [b for b in BUCKETS if b in set(accounts["delinquency_bucket"])]
    rates = (
        accounts.groupby("delinquency_bucket")["recovered_60d"].mean().reindex(present)
    )
    if rates.isna().any():
        bad = rates[rates.isna()].index.tolist()
        raise ValueError(f"recovery rate is missing for buckets: {bad}")
    return rates


def channel_effectiveness(contacts):
    """Engagement and promise-to-pay rate by channel, lowest engagement first."""
    return contacts.groupby("channel").agg(
        engagement=("engaged", "mean"),
        ptp=("outcome", lambda s: (s == "promise_to_pay").mean()),
    ).sort_values("engagement")


def recovery_by_engaged_band(accounts):
    frame = accounts.copy()
    frame["engaged_band"] = frame["n_engaged"].map(engaged_band)
    return (
        frame.groupby("engaged_band")["recovered_60d"].mean().reindex(list(ENGAGED_BANDS))
    )


def ptp_lift(accounts):
    """Recovery with and without a promise-to-pay, split by risk band."""
    frame = accounts.copy()
    frame["risk_band"] = frame["credit_score"].map(risk_band)
    frame["has_ptp"] = (frame["promise_to_pay"] > 0).map(
        {True: "PTP secured", False: "No PTP"}
    )
    lift = frame.groupby(["risk_band", "has_ptp"])["recovered_60d"].mean().unstack()
    return lift[["No PTP", "PTP secured"]]


def _require_finite(value, path):
    if isinstance(value, dict):
        for key, item in value.items():
            _require_finite(item, f"{path}.{key}")
        return
    if isinstance(value, bool):
        return
    if isinstance(value, int):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{path} is not a finite number")
        return
    raise TypeError(f"{path} has unsupported type {type(value).__name__}")


def build_kpis(accounts, contacts):
    """Headline numbers written to data/kpis.json."""
    rates = recovery_by_bucket(accounts)
    channels = channel_effectiveness(contacts)
    kpis = {
        "n_accounts": int(len(accounts)),
        "recovery_rate": float(accounts["recovered_60d"].mean()),
        "balance_at_risk": float(accounts["outstanding_balance"].sum()),
        "recovered": float(accounts["amount_recovered"].sum()),
        "recovery_by_bucket": {k: float(v) for k, v in rates.items()},
        "channel_engagement": {k: float(v) for k, v in channels["engagement"].items()},
    }
    _require_finite(kpis, "kpis")
    return kpis
