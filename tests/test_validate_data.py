import json
from pathlib import Path

import pandas as pd
import pytest

from validate_data import load_strict_json, validate_directory, validate_frames


ROOT = Path(__file__).resolve().parents[1]


def _portfolio():
    customers = pd.DataFrame({
        "customer_id": [1, 2],
        "age": [30, 45],
        "employment_status": ["employed", "unemployed"],
        "income_band": ["mid", "low"],
        "tenure_months": [12, 3],
        "prior_defaults": [0, 2],
        "region": ["Mexico City", "Online"],
        "credit_score": [700, 500],
    })
    accounts = pd.DataFrame({
        "account_id": [100001, 100002],
        "customer_id": [1, 2],
        "product": ["personal_loan", "bnpl"],
        "outstanding_balance": [1000.0, 500.0],
        "dpd_at_entry": [8, 91],
        "delinquency_bucket": ["1-15 DPD", "90+ DPD"],
        "entered_collections_date": ["2025-01-10", "2025-02-01"],
        "credit_score": [700, 500],
        "employment_status": ["employed", "unemployed"],
        "income_band": ["mid", "low"],
        "region": ["Mexico City", "Online"],
        "prior_defaults": [0, 2],
        "n_contacts": [2, 1],
        "n_engaged": [1, 0],
        "promise_to_pay": [1, 0],
        "refused": [0, 0],
        "recovered_60d": [1, 0],
        "amount_recovered": [400.0, 0.0],
    })
    contacts = pd.DataFrame({
        "contact_id": [1, 2, 3],
        "account_id": [100001, 100001, 100002],
        "channel": ["call", "sms", "email"],
        "contact_hour": [18, 10, 9],
        "weekday": [5, 1, 0],
        "engaged": [True, False, False],
        "outcome": ["promise_to_pay", "no_answer", "no_answer"],
    })
    payments = pd.DataFrame({
        "payment_id": [1],
        "account_id": [100001],
        "payment_date": ["2025-01-20"],
        "amount": [400.0],
    })
    transcripts = pd.DataFrame({
        "contact_id": [1],
        "account_id": [100001],
        "true_tone": ["cooperative"],
        "transcript": ["Hello, I can pay next week when I get paid."],
    })
    return customers, accounts, contacts, payments, transcripts


def test_tiny_portfolio_passes():
    assert validate_frames(*_portfolio()) == []


def test_flags_duplicate_key_orphan_and_bad_channel():
    customers, accounts, contacts, payments, transcripts = _portfolio()
    accounts.loc[1, "account_id"] = 100001
    contacts.loc[2, "account_id"] = 999
    contacts.loc[0, "channel"] = "pigeon"
    problems = validate_frames(customers, accounts, contacts, payments, transcripts)
    text = "\n".join(problems)
    assert "duplicate" in text
    assert "not in accounts" in text
    assert "channel" in text


def test_flags_bucket_mismatch_and_engaged_outcome():
    customers, accounts, contacts, payments, transcripts = _portfolio()
    accounts.loc[0, "delinquency_bucket"] = "90+ DPD"
    contacts.loc[1, "outcome"] = "promise_to_pay"  # still marked unanswered
    problems = "\n".join(validate_frames(customers, accounts, contacts, payments, transcripts))
    assert "does not match dpd_at_entry" in problems
    assert "engaged vs outcome" in problems


def test_flags_rollup_and_over_recovery():
    customers, accounts, contacts, payments, transcripts = _portfolio()
    accounts.loc[0, "n_engaged"] = 0
    accounts.loc[0, "amount_recovered"] = 5000
    problems = "\n".join(validate_frames(customers, accounts, contacts, payments, transcripts))
    assert "n_engaged" in problems
    assert "outstanding balance" in problems


def test_flags_payment_outside_window_and_transcript_on_sms():
    customers, accounts, contacts, payments, transcripts = _portfolio()
    payments.loc[0, "payment_date"] = "2025-06-01"
    transcripts.loc[0, "contact_id"] = 2  # the SMS, which was not answered
    problems = "\n".join(validate_frames(customers, accounts, contacts, payments, transcripts))
    assert "1-60 days" in problems
    assert "engaged call" in problems


def test_strict_json_rejects_nan(tmp_path):
    path = tmp_path / "kpis.json"
    path.write_text('{"recovery_rate": NaN}\n')
    with pytest.raises(ValueError):
        load_strict_json(path)


def test_directory_round_trip_checks_kpis(tmp_path):
    customers, accounts, contacts, payments, transcripts = _portfolio()
    customers.to_csv(tmp_path / "customers.csv", index=False)
    accounts.to_csv(tmp_path / "accounts.csv", index=False)
    contacts.to_csv(tmp_path / "contacts.csv", index=False)
    payments.to_csv(tmp_path / "payments.csv", index=False)
    transcripts.to_csv(tmp_path / "transcripts.csv", index=False)
    (tmp_path / "kpis.json").write_text(json.dumps({
        "n_accounts": 2,
        "recovery_rate": 0.5,
        "balance_at_risk": 1500.0,
        "recovered": 400.0,
        "recovery_by_bucket": {"1-15 DPD": 1.0, "90+ DPD": 0.0},
        "channel_engagement": {"email": 0.0, "sms": 0.0, "call": 1.0},
    }))
    assert validate_directory(tmp_path) == []

    bad = json.loads((tmp_path / "kpis.json").read_text())
    bad["recovery_by_bucket"]["16-30 DPD"] = 0.2
    (tmp_path / "kpis.json").write_text(json.dumps(bad))
    problems = "\n".join(validate_directory(tmp_path))
    assert "recovery_by_bucket" in problems


def test_checked_in_portfolio_passes():
    problems = validate_directory(ROOT / "data")
    assert problems == []
