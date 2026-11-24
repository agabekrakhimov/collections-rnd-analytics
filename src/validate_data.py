"""
validate_data.py
----------------
Check the collections CSVs before EDA or modelling runs.

The checks are the ones that have already bitten this project, or that
would silently change a chart if a row was wrong:

- primary keys and foreign keys line up
- buckets, channels, and outcomes stay inside the known sets
- delinquency_bucket agrees with dpd_at_entry
- an unanswered contact is exactly outcome = no_answer
- account rollups (attempts, engaged, PTP, refused) match the contact log
- copied customer attributes on accounts still match customers
- payments sit inside the 60-day recovery window and reconcile to the
  recovered amount (split payments are rounded, so a few dollars of drift
  is allowed)
- engaged calls have one transcript
- kpis.json is strict JSON and matches the tables (no NaN)

Run from the project root:
    python src/validate_data.py
"""

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

from metrics import (
    BUCKETS,
    contact_activity,
    delinquency_bucket,
    build_kpis,
)

CHANNELS = ("call", "sms", "email", "whatsapp")
OUTCOMES = (
    "no_answer",
    "promise_to_pay",
    "partial_payment",
    "callback_requested",
    "refused",
)
PRODUCTS = ("personal_loan", "credit_line", "bnpl", "auto")
EMPLOYMENT = ("employed", "self_employed", "gig", "unemployed")
INCOME_BANDS = ("low", "mid", "high")
REGIONS = ("Mexico City", "Guadalajara", "Monterrey", "Belgrade", "Novi Sad", "Online")
TONES = ("cooperative", "resistant", "hardship", "neutral")

# Dirichlet splits are rounded to cents, so the payment total can drift
# from amount_recovered by a few dollars. Anything larger is a bad join.
PAYMENT_RECONCILE_TOLERANCE = 5.0

CUSTOMER_COLUMNS = [
    "customer_id", "age", "employment_status", "income_band", "tenure_months",
    "prior_defaults", "region", "credit_score",
]
ACCOUNT_COLUMNS = [
    "account_id", "customer_id", "product", "outstanding_balance", "dpd_at_entry",
    "delinquency_bucket", "entered_collections_date", "credit_score",
    "employment_status", "income_band", "region", "prior_defaults", "n_contacts",
    "n_engaged", "promise_to_pay", "refused", "recovered_60d", "amount_recovered",
]
CONTACT_COLUMNS = [
    "contact_id", "account_id", "channel", "contact_hour", "weekday", "engaged", "outcome",
]
PAYMENT_COLUMNS = ["payment_id", "account_id", "payment_date", "amount"]
TRANSCRIPT_COLUMNS = ["contact_id", "account_id", "true_tone", "transcript"]

COPIED_FROM_CUSTOMER = [
    "credit_score", "employment_status", "income_band", "region", "prior_defaults",
]


class DataValidationError(Exception):
    def __init__(self, problems):
        self.problems = list(problems)
        bullet = "\n".join(f"- {problem}" for problem in self.problems)
        super().__init__(f"{len(self.problems)} data check(s) failed:\n{bullet}")


def _require_columns(frame, columns, name, problems):
    missing = [col for col in columns if col not in frame.columns]
    if missing:
        problems.append(f"{name} is missing columns: {missing}")
        return False
    return True


def _nulls(frame, columns, name, problems):
    for col in columns:
        n = int(frame[col].isna().sum())
        if n:
            problems.append(f"{name}.{col} has {n} null value(s)")


def _unique(frame, column, name, problems):
    n = int(frame[column].duplicated().sum())
    if n:
        problems.append(f"{name}.{column} has {n} duplicate row(s)")


def _in_set(frame, column, allowed, name, problems):
    bad = ~frame[column].isin(allowed)
    n = int(bad.sum())
    if n:
        sample = sorted(frame.loc[bad, column].astype(str).unique())[:5]
        problems.append(f"{name}.{column} has {n} value(s) outside {list(allowed)} (e.g. {sample})")


def _range(frame, column, low, high, name, problems):
    values = pd.to_numeric(frame[column], errors="coerce")
    bad = values.isna() | (values < low) | (values > high)
    n = int(bad.sum())
    if n:
        problems.append(f"{name}.{column} has {n} value(s) outside [{low}, {high}]")


def _as_bool(series):
    if series.dtype == bool:
        return series
    mapped = series.map({
        True: True, False: False,
        1: True, 0: False,
        "True": True, "False": False,
        "true": True, "false": False,
        "1": True, "0": False,
    })
    return mapped


def load_strict_json(path):
    """Reject NaN/Infinity. The stdlib loader accepts those; most parsers do not."""

    def reject(constant):
        raise ValueError(f"{path} contains {constant}, which is not strict JSON")

    with open(path) as handle:
        return json.load(handle, parse_constant=reject)


def validate_frames(customers, accounts, contacts, payments, transcripts):
    problems = []
    frames = {
        "customers": (customers, CUSTOMER_COLUMNS),
        "accounts": (accounts, ACCOUNT_COLUMNS),
        "contacts": (contacts, CONTACT_COLUMNS),
        "payments": (payments, PAYMENT_COLUMNS),
        "transcripts": (transcripts, TRANSCRIPT_COLUMNS),
    }
    ready = True
    for name, (frame, columns) in frames.items():
        if not _require_columns(frame, columns, name, problems):
            ready = False
    if not ready:
        return problems

    _nulls(customers, CUSTOMER_COLUMNS, "customers", problems)
    _nulls(accounts, ACCOUNT_COLUMNS, "accounts", problems)
    _nulls(contacts, CONTACT_COLUMNS, "contacts", problems)
    _nulls(payments, PAYMENT_COLUMNS, "payments", problems)
    _nulls(transcripts, ["contact_id", "account_id", "true_tone", "transcript"], "transcripts", problems)

    _unique(customers, "customer_id", "customers", problems)
    _unique(accounts, "account_id", "accounts", problems)
    _unique(contacts, "contact_id", "contacts", problems)
    _unique(payments, "payment_id", "payments", problems)
    _unique(transcripts, "contact_id", "transcripts", problems)

    orphan_accounts = ~accounts["customer_id"].isin(customers["customer_id"])
    if int(orphan_accounts.sum()):
        problems.append(f"{int(orphan_accounts.sum())} accounts.customer_id values are not in customers")
    orphan_contacts = ~contacts["account_id"].isin(accounts["account_id"])
    if int(orphan_contacts.sum()):
        problems.append(f"{int(orphan_contacts.sum())} contacts.account_id values are not in accounts")
    orphan_payments = ~payments["account_id"].isin(accounts["account_id"])
    if int(orphan_payments.sum()):
        problems.append(f"{int(orphan_payments.sum())} payments.account_id values are not in accounts")
    orphan_transcripts = ~transcripts["account_id"].isin(accounts["account_id"])
    if int(orphan_transcripts.sum()):
        problems.append(f"{int(orphan_transcripts.sum())} transcripts.account_id values are not in accounts")

    _in_set(customers, "employment_status", EMPLOYMENT, "customers", problems)
    _in_set(customers, "income_band", INCOME_BANDS, "customers", problems)
    _in_set(customers, "region", REGIONS, "customers", problems)
    _in_set(accounts, "product", PRODUCTS, "accounts", problems)
    _in_set(accounts, "delinquency_bucket", BUCKETS, "accounts", problems)
    _in_set(accounts, "employment_status", EMPLOYMENT, "accounts", problems)
    _in_set(accounts, "income_band", INCOME_BANDS, "accounts", problems)
    _in_set(accounts, "region", REGIONS, "accounts", problems)
    _in_set(contacts, "channel", CHANNELS, "contacts", problems)
    _in_set(contacts, "outcome", OUTCOMES, "contacts", problems)
    _in_set(transcripts, "true_tone", TONES, "transcripts", problems)

    _range(customers, "age", 18, 80, "customers", problems)
    _range(customers, "tenure_months", 0, 600, "customers", problems)
    _range(customers, "prior_defaults", 0, 20, "customers", problems)
    _range(customers, "credit_score", 300, 850, "customers", problems)
    _range(accounts, "outstanding_balance", 80, 20000, "accounts", problems)
    _range(accounts, "dpd_at_entry", 0, 365, "accounts", problems)
    _range(accounts, "credit_score", 300, 850, "accounts", problems)
    _range(accounts, "amount_recovered", 0, 20000, "accounts", problems)
    _range(contacts, "contact_hour", 8, 20, "contacts", problems)
    _range(contacts, "weekday", 0, 6, "contacts", problems)
    _range(payments, "amount", 0.01, 20000, "payments", problems)

    recovered = pd.to_numeric(accounts["recovered_60d"], errors="coerce")
    bad_flag = ~recovered.isin([0, 1])
    if int(bad_flag.sum()):
        problems.append(f"accounts.recovered_60d has {int(bad_flag.sum())} value(s) other than 0 or 1")

    over = accounts["amount_recovered"] > accounts["outstanding_balance"] + 0.01
    if int(over.sum()):
        problems.append(
            f"{int(over.sum())} accounts recovered more than the outstanding balance"
        )

    known_dpd = accounts["dpd_at_entry"].notna()
    expected_bucket = accounts.loc[known_dpd, "dpd_at_entry"].map(delinquency_bucket)
    mismatch = accounts.loc[known_dpd, "delinquency_bucket"] != expected_bucket
    if int(mismatch.sum()):
        problems.append(
            f"{int(mismatch.sum())} accounts have delinquency_bucket that does not match dpd_at_entry"
        )

    engaged = _as_bool(contacts["engaged"])
    if engaged.isna().any():
        problems.append(f"contacts.engaged has {int(engaged.isna().sum())} value(s) that are not true/false")
    else:
        no_answer = contacts["outcome"] == "no_answer"
        disagree = no_answer == engaged
        if int(disagree.sum()):
            problems.append(
                f"{int(disagree.sum())} contacts disagree on engaged vs outcome "
                "(no_answer should be exactly the unanswered rows)"
            )

    copied = accounts.merge(customers, on="customer_id", how="left", suffixes=("", "_src"))
    linked = copied["customer_id"].isin(customers["customer_id"])
    for col in COPIED_FROM_CUSTOMER:
        differ = linked & (copied[col] != copied[f"{col}_src"])
        if int(differ.sum()):
            problems.append(
                f"{int(differ.sum())} accounts have {col} that does not match customers"
            )

    accounts_unique = not accounts["account_id"].duplicated().any()
    activity = contact_activity(contacts)
    rolled = accounts.merge(activity, on="account_id", how="left", suffixes=("", "_log"))
    for col in ("n_contacts", "n_engaged", "promise_to_pay", "refused"):
        logged = rolled[f"{col}_log"].fillna(0)
        gap = (rolled[col].astype(float) - logged.astype(float)).abs() > 1e-6
        if int(gap.sum()):
            problems.append(
                f"{int(gap.sum())} accounts have {col} that does not match the contact log"
            )

    entry = pd.to_datetime(accounts["entered_collections_date"], errors="coerce")
    if entry.isna().any():
        problems.append(f"accounts.entered_collections_date has {int(entry.isna().sum())} unparseable value(s)")
    paid_on = pd.to_datetime(payments["payment_date"], errors="coerce")
    if paid_on.isna().any():
        problems.append(f"payments.payment_date has {int(paid_on.isna().sum())} unparseable value(s)")
    elif accounts_unique and not entry.isna().any():
        entry_by_account = pd.Series(entry.values, index=accounts["account_id"])
        opened = entry_by_account.reindex(payments["account_id"]).reset_index(drop=True)
        lag = (paid_on - opened).dt.days
        outside = lag.isna() | (lag < 1) | (lag > 60)
        if int(outside.sum()):
            problems.append(
                f"{int(outside.sum())} payments fall outside 1-60 days after collections entry"
            )

    if accounts_unique:
        paid = payments.groupby("account_id")["amount"].sum()
        recovered_amt = accounts.set_index("account_id")["amount_recovered"]
        compared = recovered_amt.to_frame("recovered").join(paid.rename("paid"), how="left")
        compared["paid"] = compared["paid"].fillna(0)
        drift = (compared["recovered"] - compared["paid"]).abs()
        bad_drift = drift > PAYMENT_RECONCILE_TOLERANCE
        if int(bad_drift.sum()):
            problems.append(
                f"{int(bad_drift.sum())} accounts have payments that differ from amount_recovered "
                f"by more than ${PAYMENT_RECONCILE_TOLERANCE:.0f}"
            )
        needs_payment = (compared["recovered"] > 5) & (compared["paid"] <= 0)
        if int(needs_payment.sum()):
            problems.append(
                f"{int(needs_payment.sum())} accounts recovered more than $5 but have no payments"
            )
        unexpected = (compared["recovered"] <= 5) & (compared["paid"] > 0)
        if int(unexpected.sum()):
            problems.append(
                f"{int(unexpected.sum())} accounts recovered $5 or less but still have payments"
            )

    blank = transcripts["transcript"].isna() | (transcripts["transcript"].astype(str).str.strip() == "")
    if int(blank.sum()):
        problems.append(f"{int(blank.sum())} transcripts are empty")

    contacts_unique = not contacts["contact_id"].duplicated().any()
    contact_key = contacts.set_index("contact_id")
    known_contact = transcripts["contact_id"].isin(contact_key.index)
    if int((~known_contact).sum()):
        problems.append(
            f"{int((~known_contact).sum())} transcripts.contact_id values are not in contacts"
        )
    elif contacts_unique:
        linked_account = contact_key.loc[transcripts["contact_id"], "account_id"].to_numpy()
        wrong_account = transcripts["account_id"].to_numpy() != linked_account
        if int(wrong_account.sum()):
            problems.append(
                f"{int(wrong_account.sum())} transcripts are attached to the wrong account_id"
            )
        call = contact_key.loc[transcripts["contact_id"], "channel"].to_numpy() == "call"
        was_engaged = _as_bool(contact_key.loc[transcripts["contact_id"], "engaged"]).to_numpy()
        not_a_conversation = ~(call & was_engaged)
        if int(not_a_conversation.sum()):
            problems.append(
                f"{int(not_a_conversation.sum())} transcripts are not tied to an engaged call"
            )

    if engaged.notna().all():
        engaged_calls = contacts[(contacts["channel"] == "call") & engaged.fillna(False)]
        missing = ~engaged_calls["contact_id"].isin(transcripts["contact_id"])
        if int(missing.sum()):
            problems.append(f"{int(missing.sum())} engaged calls have no transcript")

    return problems


def validate_kpis(path, accounts, contacts):
    problems = []
    try:
        payload = load_strict_json(path)
    except (ValueError, json.JSONDecodeError) as exc:
        return [str(exc)]
    try:
        expected = build_kpis(accounts, contacts)
    except ValueError as exc:
        return [str(exc)]

    for key in ("n_accounts", "recovery_rate", "balance_at_risk", "recovered"):
        if key not in payload:
            problems.append(f"kpis.json is missing {key}")
            continue
        if abs(float(payload[key]) - float(expected[key])) > 1e-6:
            problems.append(
                f"kpis.json {key} is {payload[key]} but the tables give {expected[key]}"
            )

    for key in ("recovery_by_bucket", "channel_engagement"):
        got = payload.get(key)
        exp = expected[key]
        if not isinstance(got, dict):
            problems.append(f"kpis.json {key} is missing")
            continue
        if set(got) != set(exp):
            problems.append(f"kpis.json {key} keys {sorted(got)} do not match {sorted(exp)}")
            continue
        for name, value in exp.items():
            if abs(float(got[name]) - float(value)) > 1e-6:
                problems.append(
                    f"kpis.json {key}.{name} is {got[name]} but the tables give {value}"
                )
    return problems


def validate_directory(data_dir):
    data_dir = Path(data_dir)
    frames = {}
    problems = []
    specs = {
        "customers": CUSTOMER_COLUMNS,
        "accounts": ACCOUNT_COLUMNS,
        "contacts": CONTACT_COLUMNS,
        "payments": PAYMENT_COLUMNS,
        "transcripts": TRANSCRIPT_COLUMNS,
    }
    for name in specs:
        path = data_dir / f"{name}.csv"
        if not path.exists():
            problems.append(f"missing file {path}")
            continue
        frames[name] = pd.read_csv(path)
    if problems:
        return problems

    problems.extend(validate_frames(
        frames["customers"], frames["accounts"], frames["contacts"],
        frames["payments"], frames["transcripts"],
    ))
    kpi_path = data_dir / "kpis.json"
    if kpi_path.exists():
        problems.extend(validate_kpis(kpi_path, frames["accounts"], frames["contacts"]))
    return problems


def main(argv=None):
    parser = argparse.ArgumentParser(description="Check the collections input tables.")
    parser.add_argument(
        "--data-dir",
        default=str(Path(__file__).resolve().parents[1] / "data"),
        help="directory with the CSVs (default: data/)",
    )
    args = parser.parse_args(argv)
    problems = validate_directory(args.data_dir)
    if problems:
        print(DataValidationError(problems), file=sys.stderr)
        return 1
    print(f"OK: {args.data_dir} passed input checks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
