import json

import pandas as pd
import pytest

from metrics import (
    build_kpis,
    channel_effectiveness,
    contact_activity,
    delinquency_bucket,
    engaged_band,
    ptp_lift,
    recovery_by_bucket,
    risk_band,
    tag_intent,
)


@pytest.mark.parametrize(
    "dpd, bucket",
    [
        (0, "1-15 DPD"),
        (15, "1-15 DPD"),
        (16, "16-30 DPD"),
        (30, "16-30 DPD"),
        (31, "31-60 DPD"),
        (60, "31-60 DPD"),
        (61, "61-90 DPD"),
        (90, "61-90 DPD"),
        (91, "90+ DPD"),
        (120, "90+ DPD"),
    ],
)
def test_delinquency_bucket_boundaries(dpd, bucket):
    assert delinquency_bucket(dpd) == bucket


def test_delinquency_bucket_rejects_missing():
    with pytest.raises(ValueError):
        delinquency_bucket(float("nan"))


@pytest.mark.parametrize(
    "n, band",
    [(0, "0"), (1, "1"), (2, "2-3"), (3, "2-3"), (4, "4+"), (9, "4+")],
)
def test_engaged_band(n, band):
    assert engaged_band(n) == band


def test_risk_band_cutoff():
    assert risk_band(679) == "subprime"
    assert risk_band(680) == "prime"


def test_tag_intent_matches_lexicon_and_falls_through():
    assert tag_intent("I lost my job last month and money is tight") == "hardship"
    assert tag_intent("Let us set up a payment plan I can afford") == "cooperative"
    assert tag_intent("I do not recognise this debt") == "resistant"
    assert tag_intent("please send the details by email") == "neutral"
    assert tag_intent(None) == "neutral"
    # hardship is listed first, so it wins when both lexicons match
    assert tag_intent("hospital, but I can do a payment plan") == "hardship"


def test_contact_activity_counts_ptp_and_refusals():
    contacts = pd.DataFrame({
        "contact_id": [1, 2, 3, 4],
        "account_id": [10, 10, 10, 11],
        "engaged": [True, True, False, False],
        "outcome": ["promise_to_pay", "refused", "no_answer", "no_answer"],
    })
    activity = contact_activity(contacts).set_index("account_id")
    assert activity.loc[10, "n_contacts"] == 3
    assert activity.loc[10, "n_engaged"] == 2
    assert activity.loc[10, "promise_to_pay"] == 1
    assert activity.loc[10, "refused"] == 1
    assert activity.loc[11, "n_contacts"] == 1
    assert activity.loc[11, "n_engaged"] == 0


def test_recovery_and_channel_rates_on_a_tiny_portfolio():
    accounts = pd.DataFrame({
        "delinquency_bucket": ["1-15 DPD", "1-15 DPD", "90+ DPD"],
        "recovered_60d": [1, 0, 0],
        "outstanding_balance": [100.0, 100.0, 50.0],
        "amount_recovered": [40.0, 0.0, 0.0],
        "n_engaged": [2, 0, 1],
        "credit_score": [700, 700, 500],
        "promise_to_pay": [1, 0, 0],
    })
    contacts = pd.DataFrame({
        "channel": ["call", "sms", "call"],
        "engaged": [True, False, True],
        "outcome": ["promise_to_pay", "no_answer", "refused"],
    })
    rates = recovery_by_bucket(accounts)
    assert rates["1-15 DPD"] == pytest.approx(0.5)
    assert "16-30 DPD" not in rates.index
    channels = channel_effectiveness(contacts)
    assert channels.loc["sms", "engagement"] == 0
    assert channels.loc["call", "ptp"] == pytest.approx(0.5)
    lift = ptp_lift(accounts)
    assert lift.loc["prime", "PTP secured"] == 1
    assert lift.loc["prime", "No PTP"] == 0


def test_build_kpis_rejects_a_missing_recovery_rate():
    accounts = pd.DataFrame({
        "delinquency_bucket": ["1-15 DPD"],
        "recovered_60d": [float("nan")],
        "outstanding_balance": [100.0],
        "amount_recovered": [0.0],
    })
    contacts = pd.DataFrame({
        "channel": ["call"],
        "engaged": [True],
        "outcome": ["promise_to_pay"],
    })
    with pytest.raises(ValueError):
        build_kpis(accounts, contacts)


def test_build_kpis_dumps_as_strict_json():
    accounts = pd.DataFrame({
        "delinquency_bucket": ["31-60 DPD", "31-60 DPD"],
        "recovered_60d": [1, 0],
        "outstanding_balance": [80.0, 120.0],
        "amount_recovered": [80.0, 0.0],
    })
    contacts = pd.DataFrame({
        "channel": ["email"],
        "engaged": [False],
        "outcome": ["no_answer"],
    })
    payload = build_kpis(accounts, contacts)
    encoded = json.dumps(payload, allow_nan=False)
    assert "NaN" not in encoded
    assert json.loads(encoded)["recovery_rate"] == pytest.approx(0.5)
