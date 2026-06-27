# BI Tools & Data Warehouse Guide

This project ships the analysis in Python + an HTML dashboard, but the role asks
for **BI tools (Power BI / Tableau / Metabase)** and **data warehouses (BigQuery /
Snowflake)**. This guide shows how to rebuild the dashboard in those tools using
the CSVs already in `data/`. Doing even the Power BI version gives you a second
screenshot for your portfolio and lets you say "I built this in Power BI."

---

## Part 1 — Power BI (recommended; free on Windows)

### 1. Install
Download **Power BI Desktop** free from the Microsoft Store (or
https://powerbi.microsoft.com/desktop). Windows only.

### 2. Load the data
1. **Home → Get data → Text/CSV**.
2. Import these four files from the `data/` folder:
   `accounts.csv`, `contacts.csv`, `customers.csv`, `payments.csv`.
   (You can also import `outputs/model_scores.csv` for the model visual.)
3. For each, click **Transform Data** once to check column types, then **Close & Apply**.

### 3. Build the model (relationships)
Go to **Model view** and create these relationships (drag field to field):
- `accounts[account_id]` → `contacts[account_id]`  (one-to-many)
- `accounts[customer_id]` → `customers[customer_id]` (one-to-many)
- `accounts[account_id]` → `payments[account_id]`  (one-to-many)
- `accounts[account_id]` → `model_scores[account_id]` (one-to-one, if imported)

### 4. Create measures (DAX)
**Modeling → New measure** for each. Paste exactly:

```DAX
Accounts = COUNTROWS(accounts)

Recovery Rate = AVERAGE(accounts[recovered_60d])

Balance at Risk = SUM(accounts[outstanding_balance])

Recovered $ = SUM(accounts[amount_recovered])

Dollar Recovery Rate = DIVIDE([Recovered $], [Balance at Risk])

Engagement Rate =
DIVIDE(
    CALCULATE(COUNTROWS(contacts), contacts[engaged] = TRUE()),
    COUNTROWS(contacts)
)

PTP Rate =
DIVIDE(
    CALCULATE(COUNTROWS(contacts), contacts[outcome] = "promise_to_pay"),
    COUNTROWS(contacts)
)
```

Set **Recovery Rate**, **Engagement Rate**, **Dollar Recovery Rate**, **PTP Rate**
to **% format** (Measure tools → Format → Percentage). Set the two $ measures to
**Currency**.

Add one calculated **column** on the `accounts` table
(**Modeling → New column**) for the contact-intensity chart:

```DAX
Engaged Band =
SWITCH(
    TRUE(),
    accounts[n_engaged] = 0, "0",
    accounts[n_engaged] = 1, "1",
    accounts[n_engaged] <= 3, "2-3",
    "4+"
)
```

### 5. Build the visuals (to match the HTML dashboard)
Use the **Report view**. Each bullet = one visual from the **Visualizations** pane.

| Visual | Type | Fields |
|---|---|---|
| KPI cards | **Card** ×4 | `Accounts`, `Recovery Rate`, `Balance at Risk`, `Recovered $` |
| Recovery by delinquency | **Clustered column** | Axis: `delinquency_bucket` · Values: `Recovery Rate` |
| Channel effectiveness | **Clustered column** | Axis: `channel` · Values: `Engagement Rate`, `PTP Rate` |
| Contact-timing heatmap | **Matrix** | Rows: `weekday` · Columns: `contact_hour` · Values: `Engagement Rate` → turn on **Conditional formatting → Background color** |
| Conversations vs recovery | **Line/column** | Axis: `Engaged Band` (sort 0,1,2-3,4+) · Values: `Recovery Rate` |
| Model score deciles | **Column** | Axis: `model_scores[decile]` · Values: `Recovery Rate` |

Tips:
- To order `delinquency_bucket` correctly, select the column → **Column tools →
  Sort by column → `dpd_at_entry`**.
- Add a **Slicer** on `region` or `product` so the report is interactive.
- Match the colors (teal `#1f9e89`, coral `#e8743b`) under **Format → Colors**.

### 6. Show it off
- **Save** as `collections_dashboard.pbix` (put it in a new `powerbi/` folder).
- **Publish** (Home → Publish) to the free **Power BI Service** to get a
  shareable link, *or* take a screenshot of the report.
- Add the screenshot to your README so recruiters see a real Power BI report.
- Commit it:
  ```powershell
  git add . ; git commit -m "Add Power BI dashboard" ; git push
  ```
  (Note: `.pbix` files can be large — that's fine for a portfolio.)

---

## Part 2 — Tableau (alternative, free via Tableau Public)
1. Install **Tableau Public** (free) from https://public.tableau.com.
2. **Connect → Text file** → `accounts.csv`; add `contacts.csv` and relate on
   `account_id` in the data-source canvas.
3. Drag `delinquency_bucket` to Columns and `recovered_60d` (set aggregation to
   **Average**) to Rows for the recovery chart; repeat for the others.
4. Combine sheets into a **Dashboard**, then **Publish to Tableau Public** — it
   gives you a public URL you can link from your CV. (Tableau Public makes
   workbooks public, which is perfect for a portfolio.)

---

## Part 3 — Metabase (alternative, open-source, DB-backed)
Metabase queries a database, not CSVs, so pair it with Part 4:
1. Run Metabase locally with Docker:
   `docker run -d -p 3000:3000 --name metabase metabase/metabase`
2. Open http://localhost:3000, connect it to your warehouse (or a local Postgres).
3. Paste the queries from `sql/collections_analysis.sql` into **+ New → SQL query**,
   then **Save** each as a question and pin them to a **Dashboard**.

---

## Part 4 — Data warehouse (BigQuery or Snowflake)

This proves the "data warehouse" + "SQL on large datasets" requirement, and lets
Power BI/Tableau/Metabase connect to a real warehouse instead of CSVs.

### Option A — Google BigQuery (free sandbox, no credit card)
1. Go to https://console.cloud.google.com/bigquery and create a project.
2. Create a dataset, e.g. `collections`.
3. For each CSV: dataset → **Create table → Source: Upload** → pick the file →
   set **Schema: Auto-detect** → name the table (`accounts`, `contacts`, …).
4. Run the queries from `sql/collections_analysis.sql` in the BigQuery editor
   (they're written in BigQuery-standard SQL).
5. Connect Power BI: **Get data → Google BigQuery** → sign in → pick the tables.

### Option B — Snowflake (30-day free trial)
1. Sign up at https://signup.snowflake.com.
2. Create a database `COLLECTIONS` and schema `PUBLIC`.
3. Load each CSV via **Data → Load Data** (the web UI wizard auto-creates the table).
4. Run the SQL in a worksheet (note: Snowflake supports `QUALIFY` natively, used
   in query #7).
5. Connect Power BI: **Get data → Snowflake** → enter your account URL + warehouse.

> The SQL in `sql/collections_analysis.sql` runs on both with little/no change —
> that file is your "SQL on a warehouse" evidence even before you connect a BI tool.

---

## What to claim on your CV after this
- *"Built an interactive collections dashboard in Power BI (DAX measures, drill-down
  by region/product) on a 35k-row contact dataset."*
- *"Loaded the portfolio into BigQuery/Snowflake and authored SQL for recovery-rate,
  channel and behavioural-signal analysis."*

Do **one** BI tool + **one** warehouse and you've credibly covered the entire
tech-stack section of the job ad.
