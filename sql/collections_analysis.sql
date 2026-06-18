-- ============================================================================
--  Collections R&D — Analytical SQL Library
--  Dialect: ANSI / BigQuery-Standard SQL (notes added where Snowflake differs)
--  Tables : customers, accounts, contacts, payments, transcripts
--
--  These are the queries that power the R&D workflow: cohorting accounts,
--  measuring recovery performance, and isolating behavioural signals
--  (contact channel, timing, intensity) that move recovery rates.
-- ============================================================================


-- ----------------------------------------------------------------------------
-- 1. PORTFOLIO SNAPSHOT — recovery rate & $ recovered by delinquency bucket
--    The headline R&D question: where in the delinquency curve do we lose money?
-- ----------------------------------------------------------------------------
SELECT
    delinquency_bucket,
    COUNT(*)                                            AS accounts,
    ROUND(AVG(recovered_60d), 3)                        AS recovery_rate_60d,
    ROUND(SUM(outstanding_balance), 0)                  AS balance_at_risk,
    ROUND(SUM(amount_recovered), 0)                     AS dollars_recovered,
    ROUND(SUM(amount_recovered) / SUM(outstanding_balance), 3) AS dollar_recovery_rate
FROM accounts
GROUP BY delinquency_bucket
ORDER BY MIN(dpd_at_entry);


-- ----------------------------------------------------------------------------
-- 2. CHANNEL EFFECTIVENESS — which outreach channel drives engagement?
--    Joins contacts to outcomes. Engagement rate = answered / attempted.
-- ----------------------------------------------------------------------------
SELECT
    channel,
    COUNT(*)                                              AS attempts,
    ROUND(AVG(CASE WHEN engaged THEN 1 ELSE 0 END), 3)    AS engagement_rate,
    ROUND(AVG(CASE WHEN outcome = 'promise_to_pay' THEN 1 ELSE 0 END), 3) AS ptp_rate
FROM contacts
GROUP BY channel
ORDER BY engagement_rate DESC;


-- ----------------------------------------------------------------------------
-- 3. BEST TIME TO CONTACT — engagement by hour-of-day x weekday
--    Classic R&D output: a contact-timing heatmap to optimise dialer strategy.
-- ----------------------------------------------------------------------------
SELECT
    weekday,                                  -- 0 = Monday
    contact_hour,
    COUNT(*)                                              AS attempts,
    ROUND(AVG(CASE WHEN engaged THEN 1 ELSE 0 END), 3)    AS engagement_rate
FROM contacts
GROUP BY weekday, contact_hour
HAVING COUNT(*) >= 30                          -- suppress thin cells
ORDER BY engagement_rate DESC
LIMIT 20;


-- ----------------------------------------------------------------------------
-- 4. CONTACT INTENSITY vs RECOVERY — is "more calls" actually better,
--    or are there diminishing returns? (hypothesis to validate)
-- ----------------------------------------------------------------------------
WITH per_account AS (
    SELECT
        a.account_id,
        a.recovered_60d,
        COUNT(c.contact_id)                               AS n_contacts,
        SUM(CASE WHEN c.engaged THEN 1 ELSE 0 END)        AS n_engaged
    FROM accounts a
    LEFT JOIN contacts c USING (account_id)
    GROUP BY a.account_id, a.recovered_60d
)
SELECT
    CASE
        WHEN n_engaged = 0 THEN '0 engaged'
        WHEN n_engaged = 1 THEN '1 engaged'
        WHEN n_engaged BETWEEN 2 AND 3 THEN '2-3 engaged'
        ELSE '4+ engaged'
    END                                                    AS engaged_contacts_band,
    COUNT(*)                                               AS accounts,
    ROUND(AVG(recovered_60d), 3)                           AS recovery_rate
FROM per_account
GROUP BY engaged_contacts_band
ORDER BY recovery_rate;


-- ----------------------------------------------------------------------------
-- 5. PROMISE-TO-PAY LIFT — do PTP conversations actually convert to cash?
--    Compares recovery for accounts with >=1 PTP vs none, holding risk roughly
--    constant via credit-score band (a simple stratified comparison).
-- ----------------------------------------------------------------------------
WITH flags AS (
    SELECT
        a.account_id,
        a.recovered_60d,
        CASE WHEN a.credit_score >= 680 THEN 'prime' ELSE 'subprime' END AS risk_band,
        MAX(CASE WHEN c.outcome = 'promise_to_pay' THEN 1 ELSE 0 END)    AS has_ptp
    FROM accounts a
    LEFT JOIN contacts c USING (account_id)
    GROUP BY a.account_id, a.recovered_60d, risk_band
)
SELECT
    risk_band,
    has_ptp,
    COUNT(*)                       AS accounts,
    ROUND(AVG(recovered_60d), 3)   AS recovery_rate
FROM flags
GROUP BY risk_band, has_ptp
ORDER BY risk_band, has_ptp;


-- ----------------------------------------------------------------------------
-- 6. EARLY-INTERVENTION HYPOTHESIS — accounts worked at low DPD recover more.
--    Segments by entry bucket and whether first engaged contact happened early.
-- ----------------------------------------------------------------------------
SELECT
    delinquency_bucket,
    ROUND(AVG(recovered_60d), 3)                          AS recovery_rate,
    ROUND(AVG(outstanding_balance), 0)                    AS avg_balance,
    COUNT(*)                                              AS accounts
FROM accounts
GROUP BY delinquency_bucket
ORDER BY recovery_rate DESC;


-- ----------------------------------------------------------------------------
-- 7. HIGH-VALUE WATCHLIST — large balances unlikely to self-cure.
--    Operational output: prioritised list for senior-agent treatment.
--    (Snowflake: QUALIFY works natively; BigQuery: wrap in subquery if needed.)
-- ----------------------------------------------------------------------------
SELECT
    account_id,
    customer_id,
    product,
    outstanding_balance,
    credit_score,
    delinquency_bucket,
    n_contacts,
    n_engaged
FROM accounts
WHERE recovered_60d = 0
  AND outstanding_balance > 5000
  AND credit_score < 650
ORDER BY outstanding_balance DESC
LIMIT 100;
