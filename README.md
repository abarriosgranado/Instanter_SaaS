# INSTANTER SAAS | The SaaS Strategic Investment Decision Tool

A fictional portfolio Streamlit app that compares multiple strategic investment options.
Every project is evaluated as its own January-acquired customer cohort — there is no
shared "existing customer base" that gets subtracted or added between projects:

- **Project A: Retention Boost** acquires its own new January cohort with churn reduced
  by a configurable relative amount (renewal improvement), applied directly to that
  cohort's retention.
- **Project B: Content Expansion** acquires a separate new January cohort using baseline
  churn (no retention improvement).
- **Project C+** can be added dynamically and compared using the same financial KPIs.

An optional "Current customers" input lets you plot a separate, independent "Current
Scenario" reference line (e.g. an existing book of business you already have) — it is
purely informational and is never combined with any project's numbers.

The app includes editable assumptions, comparative KPIs across all projects, revenue, net value, ROI, payback, an automatic recommendation, customer and revenue charts, scenario storage with Neon/Postgres, and downloadable PDF reports for each generated scenario.

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

If port `8501` is busy, run:

```bash
streamlit run app.py --server.port 8502
```

## Neon Postgres scenario storage

The app can save and reload investment scenarios in Neon/Postgres.

1. Install the updated requirements.
2. Create `.streamlit/secrets.toml`.
3. Add your Neon connection URL:

```toml
[connections.neon]
url = "postgresql://USER:PASSWORD@HOST/neondb?sslmode=require&channel_binding=require"
```

4. Restart Streamlit on port `8502`.
5. Open the `Database / Neon` section in the left panel.
6. Add an optional analysis name, then click `Run Analysis` to generate the scenario and PDF report.

The app creates this table automatically when the first connection succeeds:

```sql
CREATE TABLE IF NOT EXISTS investment_scenarios (
    id BIGSERIAL PRIMARY KEY,
    scenario_number INTEGER,
    scenario_name TEXT NOT NULL,
    payload JSONB NOT NULL,
    pdf_file BYTEA,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

## Default assumptions

- Project A (Retention Boost) January cohort: 20,000 new customers
- Project B (Content Expansion) January cohort: 3,000 new customers
- Mix: 50% monthly / 50% yearly
- Monthly price: 10 USD
- Yearly price: 60 USD
- Monthly churn: 5%
- Yearly churn: 35% in Y1, 20% in Y2, 12% in Y3, 12% in Y4
- Project A churn reduction: 20% relative reduction, applied to its own cohort
- Current customers (optional existing-book reference): 0
- Analysis horizon: 4 years

## Project structure

```text
app.py
requirements.txt
README.md
.streamlit/
  secrets.example.toml
instanter_tool/
  __init__.py
  finance_model.py
  storage.py
```

The financial model is isolated in `instanter_tool/finance_model.py`; `app.py` handles the Streamlit interface and visualization layer.
