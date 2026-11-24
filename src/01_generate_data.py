"""
01_generate_data.py
--------------------
Generates a realistic *synthetic* dataset for a fintech debt-collections
R&D analytics project. No real customer data is used — all records are
simulated, but the relationships between variables are designed to mimic
patterns seen in real lending/collections portfolios so that the downstream
analysis, modelling and NLP produce meaningful, defensible insights.

Outputs (written to ../data/):
    customers.csv      one row per borrower
    accounts.csv       one row per delinquent account in collections
    contacts.csv       one row per outreach attempt (call / sms / email / whatsapp)
    payments.csv       one row per payment made after entering collections
    transcripts.csv    one row per call with a short synthetic transcript

Run:
    python 01_generate_data.py
"""

import os
import numpy as np
import pandas as pd

from metrics import contact_activity, delinquency_bucket

RNG = np.random.default_rng(42)          # reproducible
N_CUSTOMERS = 8000                       # portfolio size
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
os.makedirs(DATA_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# 1. CUSTOMERS
# ---------------------------------------------------------------------------
regions = ["Mexico City", "Guadalajara", "Monterrey", "Belgrade", "Novi Sad", "Online"]
employment = ["employed", "self_employed", "gig", "unemployed"]
income_bands = ["low", "mid", "high"]

customer_id = np.arange(1, N_CUSTOMERS + 1)
age = RNG.integers(21, 65, N_CUSTOMERS)
emp = RNG.choice(employment, N_CUSTOMERS, p=[0.55, 0.20, 0.15, 0.10])
income = RNG.choice(income_bands, N_CUSTOMERS, p=[0.45, 0.40, 0.15])
tenure_months = RNG.integers(1, 60, N_CUSTOMERS)
prior_defaults = RNG.poisson(0.4, N_CUSTOMERS).clip(0, 5)
region = RNG.choice(regions, N_CUSTOMERS)

# A latent "credit risk" score 300-850 (higher = better). Built from drivers
# so the model later has real signal to learn.
base = 680
risk = (
    base
    + (income == "high") * 40 + (income == "mid") * 10 - (income == "low") * 25
    + (emp == "employed") * 25 - (emp == "unemployed") * 60 - (emp == "gig") * 15
    + (tenure_months / 60) * 30
    - prior_defaults * 35
    + RNG.normal(0, 40, N_CUSTOMERS)
).clip(300, 850).round().astype(int)

customers = pd.DataFrame({
    "customer_id": customer_id,
    "age": age,
    "employment_status": emp,
    "income_band": income,
    "tenure_months": tenure_months,
    "prior_defaults": prior_defaults,
    "region": region,
    "credit_score": risk,
})

# ---------------------------------------------------------------------------
# 2. ACCOUNTS (loans that have rolled into collections)
# ---------------------------------------------------------------------------
products = ["personal_loan", "credit_line", "bnpl", "auto"]
prod = RNG.choice(products, N_CUSTOMERS, p=[0.4, 0.3, 0.2, 0.1])
outstanding = (RNG.lognormal(mean=8.0, sigma=0.7, size=N_CUSTOMERS)).round(2)  # ~ $300-$15k
outstanding = outstanding.clip(80, 20000)

# Days past due when account entered the collections workflow.
dpd_entry = RNG.choice([8, 15, 31, 61, 91], N_CUSTOMERS, p=[0.30, 0.30, 0.22, 0.12, 0.06])

entry_dates = pd.to_datetime("2025-01-01") + pd.to_timedelta(RNG.integers(0, 150, N_CUSTOMERS), unit="D")

accounts = pd.DataFrame({
    "account_id": np.arange(100001, 100001 + N_CUSTOMERS),
    "customer_id": customer_id,
    "product": prod,
    "outstanding_balance": outstanding,
    "dpd_at_entry": dpd_entry,
    "delinquency_bucket": [delinquency_bucket(d) for d in dpd_entry],
    "entered_collections_date": entry_dates,
})
accounts = accounts.merge(customers[["customer_id", "credit_score", "employment_status",
                                      "income_band", "region", "prior_defaults"]],
                          on="customer_id", how="left")

# ---------------------------------------------------------------------------
# 3. CONTACTS (outreach attempts) — timing & channel carry behavioural signal
# ---------------------------------------------------------------------------
channels = ["call", "sms", "email", "whatsapp"]
contact_rows = []
contact_id = 1
for _, a in accounts.iterrows():
    n_contacts = RNG.integers(1, 9)
    for _ in range(n_contacts):
        ch = RNG.choice(channels, p=[0.45, 0.25, 0.15, 0.15])
        hour = int(RNG.integers(8, 21))          # contact attempt hour (08:00-20:00)
        weekday = int(RNG.integers(0, 7))         # 0=Mon
        # Probability the contact is answered/engaged depends on channel + timing.
        p_engage = 0.25
        p_engage += 0.12 if ch == "call" else 0.0
        p_engage += 0.10 if ch == "whatsapp" else 0.0
        p_engage += 0.10 if 17 <= hour <= 20 else 0.0   # evenings engage more
        p_engage += 0.05 if weekday >= 5 else 0.0        # weekends
        engaged = RNG.random() < min(p_engage, 0.85)
        # Outcome conditional on engagement and customer risk.
        if not engaged:
            outcome = "no_answer"
        else:
            score = a["credit_score"]
            r = RNG.random() + (score - 600) / 600.0
            if r > 0.85:
                outcome = "promise_to_pay"
            elif r > 0.55:
                outcome = "partial_payment"
            elif r > 0.30:
                outcome = "callback_requested"
            else:
                outcome = "refused"
        contact_rows.append((contact_id, a["account_id"], ch, hour, weekday, engaged, outcome))
        contact_id += 1

contacts = pd.DataFrame(contact_rows, columns=[
    "contact_id", "account_id", "channel", "contact_hour", "weekday", "engaged", "outcome"])

# ---------------------------------------------------------------------------
# 4. Derive RECOVERY OUTCOME per account from the signals above
# ---------------------------------------------------------------------------
agg = contact_activity(contacts)
accounts = accounts.merge(agg, on="account_id", how="left").fillna(
    {"n_contacts": 0, "n_engaged": 0, "promise_to_pay": 0, "refused": 0})

# Latent probability of recovery within 60 days.
z = (
    -1.2
    + (accounts["credit_score"] - 600) / 120.0
    + accounts["n_engaged"] * 0.18
    + accounts["promise_to_pay"] * 0.55
    - accounts["refused"] * 0.40
    - (accounts["dpd_at_entry"] / 90.0) * 0.9
    - np.log1p(accounts["outstanding_balance"]) * 0.12
    - accounts["prior_defaults"] * 0.10
)
p_recover = 1 / (1 + np.exp(-z))
accounts["recovered_60d"] = (RNG.random(len(accounts)) < p_recover).astype(int)

# Recovered amount (share of balance) for recovered accounts.
recovery_share = np.where(
    accounts["recovered_60d"] == 1,
    RNG.beta(5, 2, len(accounts)),         # recovered: most of balance
    RNG.beta(1, 8, len(accounts)),          # not recovered: little/none
)
accounts["amount_recovered"] = (accounts["outstanding_balance"] * recovery_share).round(2)

# ---------------------------------------------------------------------------
# 5. PAYMENTS
# ---------------------------------------------------------------------------
pay_rows = []
pid = 1
for _, a in accounts.iterrows():
    if a["amount_recovered"] > 5:
        n_pay = RNG.integers(1, 4)
        amounts = RNG.dirichlet(np.ones(n_pay)) * a["amount_recovered"]
        for amt in amounts:
            day_offset = int(RNG.integers(1, 60))
            pay_rows.append((pid, a["account_id"],
                             (a["entered_collections_date"] + pd.Timedelta(days=day_offset)).date(),
                             round(amt, 2)))
            pid += 1
payments = pd.DataFrame(pay_rows, columns=["payment_id", "account_id", "payment_date", "amount"])

# ---------------------------------------------------------------------------
# 6. CALL TRANSCRIPTS (synthetic, for NLP) — only for engaged calls
# ---------------------------------------------------------------------------
hardship_phrases = [
    "I lost my job last month and money is tight",
    "I have been in the hospital and missed work",
    "my hours were cut so I cannot pay the full amount",
    "I had an unexpected family emergency",
]
cooperative_phrases = [
    "I can pay next week when I get paid",
    "let us set up a payment plan I can afford",
    "I want to clear this balance, what are my options",
    "I will make a partial payment today",
]
resistant_phrases = [
    "I do not recognise this debt and I dispute it",
    "stop calling me about this",
    "I already paid this, check your records",
    "I am not going to pay this right now",
]
neutral_phrases = [
    "can you remind me of the balance and due date",
    "please send the details by email",
    "I need to think about it and call back",
]

call_contacts = contacts[(contacts["channel"] == "call") & (contacts["engaged"])].copy()
# join recovery outcome so transcript tone correlates with outcome
call_contacts = call_contacts.merge(
    accounts[["account_id", "recovered_60d"]], on="account_id", how="left")

trans_rows = []
for _, c in call_contacts.iterrows():
    recovered = c["recovered_60d"] == 1
    if c["outcome"] == "promise_to_pay" or (recovered and RNG.random() < 0.6):
        text = RNG.choice(cooperative_phrases)
        tone = "cooperative"
    elif c["outcome"] == "refused" or (not recovered and RNG.random() < 0.4):
        text = RNG.choice(resistant_phrases)
        tone = "resistant"
    elif RNG.random() < 0.35:
        text = RNG.choice(hardship_phrases)
        tone = "hardship"
    else:
        text = RNG.choice(neutral_phrases)
        tone = "neutral"
    opener = RNG.choice(["Hello, ", "Hi, ", "Yes, ", "Okay so "])
    closer = RNG.choice([" thanks for calling.", " that's all for now.", " appreciate the help.", ""])
    transcript = f"{opener}{text}{closer}"
    trans_rows.append((c["contact_id"], c["account_id"], tone, transcript))

transcripts = pd.DataFrame(trans_rows, columns=["contact_id", "account_id", "true_tone", "transcript"])

# ---------------------------------------------------------------------------
# Save
# ---------------------------------------------------------------------------
customers.to_csv(os.path.join(DATA_DIR, "customers.csv"), index=False)
accounts.to_csv(os.path.join(DATA_DIR, "accounts.csv"), index=False)
contacts.to_csv(os.path.join(DATA_DIR, "contacts.csv"), index=False)
payments.to_csv(os.path.join(DATA_DIR, "payments.csv"), index=False)
transcripts.to_csv(os.path.join(DATA_DIR, "transcripts.csv"), index=False)

print("Data generated:")
print(f"  customers   : {len(customers):>6}")
print(f"  accounts    : {len(accounts):>6}  (recovery rate {accounts['recovered_60d'].mean():.1%})")
print(f"  contacts    : {len(contacts):>6}")
print(f"  payments    : {len(payments):>6}")
print(f"  transcripts : {len(transcripts):>6}")
