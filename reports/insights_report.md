# Collections R&D — Insights Report

**Audience:** Collections Operations, Product & Data stakeholders
**Author:** Ogabek
**Scope:** 8,000-account delinquency portfolio (synthetic), 60-day recovery window

---

## 1. Executive summary

Of **$30.3M** in balance at risk across 8,000 delinquent accounts, **24.4%** of
accounts were recovered within 60 days, returning **$7.76M**. The analysis
isolates four levers that move recovery — **timing of intervention, conversation
quality, channel mix, and securing a promise-to-pay** — and shows that a simple
propensity model concentrates recoverable accounts well enough to re-prioritise
agent effort for a meaningful lift.

---

## 2. Findings & recommendations

### 2.1 Intervene earlier — recovery decays with age
Recovery falls from **27.2%** (1–15 DPD) to **15.2%** (90+ DPD). Every bucket of
delay measurably reduces the odds of getting money back.
**→ Recommendation:** move treatment capacity earlier in the delinquency curve;
pilot proactive outreach at 1–15 DPD for medium/high balances.

### 2.2 Optimise for conversations, not dials
Accounts with **0** engaged (answered) contacts recover **15.9%**; with **4+**,
**43.2%**. The relationship is monotonic but flattens — the first one or two
*real conversations* carry most of the value.
**→ Recommendation:** target *engaged-contact* rate as the operational KPI, not
attempt volume. Cap low-value repeat dialing.

### 2.3 Re-balance channel & timing
Calls (41.5%) and WhatsApp (39.0%) engage far better than SMS/email (~30%), and
engagement peaks in **evenings and weekends**.
**→ Recommendation:** route high-value accounts to call/WhatsApp; shift dialer
windows toward evenings. Reserve SMS/email for low-balance, self-cure segments.

### 2.4 Make the promise-to-pay the goal of every call
Securing a PTP roughly **doubles** recovery in both risk bands
(prime 23%→45%, subprime 10%→24%).
**→ Recommendation:** script and coach toward an explicit PTP; track PTP-capture
rate per agent.

### 2.5 Mine call transcripts for real-time signal
A model using **only transcript text** reaches **ROC-AUC 0.80**. "Cooperative"
calls recover **59.7%** vs **3.3%** for "resistant" — language is a leading
indicator available the moment a call ends.
**→ Recommendation:** stand up a speech-to-text → intent-tagging pipeline to flag
hardship and resistance for tailored treatment and to feed the propensity model.

### 2.6 Prioritise with a propensity score
The recovery-propensity model (ROC-AUC 0.73) rank-orders accounts so the **top
decile recovers 60%** vs **5%** in the bottom — a **12× lift**. Top drivers:
promise-to-pay, credit score, engaged contacts, balance, and DPD at entry.
**→ Recommendation:** route senior agents to high-propensity / high-balance
accounts; use low scores to trigger lower-cost digital treatment or settlement.

---

## 3. Hypotheses tested

| Hypothesis | Method | Result |
|---|---|---|
| Earlier intervention → higher recovery | Recovery by DPD bucket | **Supported** |
| More conversations → higher recovery (with diminishing returns) | Recovery by engaged-contact band | **Supported** |
| PTP raises recovery independent of risk | Stratified by credit band | **Supported** |
| Channel & timing affect engagement | Channel rates + weekday×hour heatmap | **Supported** |
| Call language carries standalone signal | TF-IDF text-only model | **Supported (AUC 0.80)** |

---

## 4. Limitations & next steps
- Synthetic data: magnitudes are illustrative; replicate on production data.
- 60-day window only; extend to 30/90-day and roll-rate analysis.
- Observational, not causal — recommend an **A/B test** on contact timing and
  early-intervention before full rollout.
- Add cost-to-collect to move from recovery-rate to **net-recovery** optimisation.
