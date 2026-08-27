from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st
from html import escape

from instanter_tool.finance_model import ModelInputs, ProjectAssumption, build_projects_model
from instanter_tool.reporting import build_analysis_report_pdf
from instanter_tool.storage import (
    dependencies_available,
    engine_from_url,
    list_scenarios,
    load_scenario,
    load_scenario_pdf,
    next_scenario_number,
    save_scenario,
)

SCENARIO_COLORS = [
    "#4b5563",
    "#0f766e",
    "#c2410c",
    "#2563eb",
    "#9333ea",
    "#ca8a04",
    "#be123c",
    "#0891b2",
    "#7c3aed",
]


st.set_page_config(
    page_title="INSTANTER SAAS | The Strategic Investment Decision Tool",
    layout="wide",
)


CUSTOM_CSS = """
<style>
:root {
  --primary: #155e75;
  --accent: #0f766e;
  --ink: #17202a;
  --muted: #5f6f7a;
  --surface: #ffffff;
  --line: #d8e1e7;
}
.main .block-container {
  padding-top: 2rem;
  padding-bottom: 3rem;
  max-width: 1280px;
}
section[data-testid="stSidebar"] {
  width: 420px !important;
}
section[data-testid="stSidebar"] > div:first-child {
  width: 420px !important;
}
div[data-testid="stMetric"] {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 1rem 1rem 0.85rem;
  box-shadow: 0 1px 2px rgba(20, 40, 55, 0.06);
}
h1, h2, h3 {
  color: var(--ink);
  letter-spacing: 0;
}
.hero {
  position: relative;
  border-bottom: 1px solid var(--line);
  padding-bottom: 1rem;
  margin-bottom: 1.2rem;
  padding-right: 8rem;
}
.hero-title {
  font-size: 2.2rem;
  font-weight: 760;
  color: var(--ink);
}
.hero-subtitle {
  max-width: 820px;
  color: var(--muted);
  font-size: 1rem;
  line-height: 1.5;
}
.brand-mark {
  position: absolute;
  top: 0.1rem;
  right: 0;
  display: flex;
  align-items: center;
  gap: 0.65rem;
  color: #0f766e;
  font-weight: 800;
  letter-spacing: .04em;
  font-size: 1.55rem;
}
.brand-mark svg {
  width: 4.4rem;
  height: 4.4rem;
}
@media (max-width: 700px) {
  .hero {
    padding-right: 0;
    padding-top: 3rem;
  }
  .brand-mark {
    left: 0;
    right: auto;
  }
}
.recommendation {
  background: #eef8f7;
  border: 1px solid #a8d8d2;
  border-radius: 8px;
  padding: 1.1rem;
  min-height: 220px;
}
.recommendation strong {
  color: #0f5f59;
}
.insight-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 1rem;
  margin: 1.25rem 0 1.5rem;
}
.insight-card {
  min-height: 220px;
  background: #ffffff;
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 1.1rem;
  box-shadow: 0 2px 8px rgba(20, 40, 55, 0.07);
}
.insight-kicker {
  color: #0f766e;
  font-size: 0.78rem;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: .06em;
  margin-bottom: .65rem;
}
.insight-title {
  color: var(--ink);
  font-size: 1.2rem;
  font-weight: 800;
  line-height: 1.2;
  margin-bottom: .75rem;
}
.insight-metric {
  color: #0f766e;
  font-size: 1.75rem;
  font-weight: 820;
  line-height: 1.1;
  margin-bottom: .8rem;
}
.insight-body {
  color: var(--muted);
  font-size: 0.96rem;
  line-height: 1.42;
}
@media (max-width: 1000px) {
  .insight-grid {
    grid-template-columns: 1fr;
  }
}
.section-label {
  color: var(--muted);
  font-size: 0.83rem;
  text-transform: uppercase;
  letter-spacing: .06em;
  font-weight: 700;
  margin-bottom: .25rem;
}
.sidebar-main-title {
  color: var(--ink);
  font-size: 1.85rem;
  font-weight: 800;
  line-height: 1.15;
  margin: 0.25rem 0 1.2rem;
}
section[data-testid="stSidebar"] details > summary p {
  font-size: 1.45rem;
  font-weight: 800;
  color: var(--ink);
}
</style>
"""


def usd(value: float) -> str:
    return f"${value:,.0f}"


def pct(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{value:.1%}"


def payback_label(month: int | None) -> str:
    if month is None:
        return "Not reached"
    if month == 0:
        return "Immediate"
    return f"Month {month}"


def signed_usd(value: float) -> str:
    sign = "+" if value >= 0 else "-"
    return f"{sign}${abs(value):,.0f}"


def scenario_file_name(scenario_name: str) -> str:
    clean = "".join(char.lower() if char.isalnum() else "_" for char in scenario_name)
    clean = "_".join(part for part in clean.split("_") if part)
    return f"{clean or 'scenario'}_investment_report.pdf"


def scenario_display_name(scenario_number: int | None, scenario_name: str) -> str:
    if scenario_number is None:
        return scenario_name
    default_name = f"Scenario {scenario_number}"
    if scenario_name.strip() == default_name:
        return default_name
    return f"{default_name}: {scenario_name}"


def insight_cards(comparison: pd.DataFrame, recommendation: dict[str, str | float]) -> list[dict[str, str]]:
    winner = str(recommendation["winner"])
    runner_up = str(recommendation.get("runner_up", "n/a"))
    best = comparison.iloc[0]
    revenue_delta = float(recommendation.get("break_even_cost_differential", 0.0))
    net_delta = float(recommendation.get("net_value_gap", 0.0))
    roi_rows = comparison.dropna(subset=["roi"]).sort_values("roi", ascending=False)

    if roi_rows.empty:
        roi_line = "Add project costs to calculate ROI and compare capital efficiency."
        roi_metric = "ROI pending"
    else:
        roi_leader = str(roi_rows.iloc[0]["project"]).split(":")[0]
        roi_line = f"{roi_leader} shows the stronger ROI based on the current cost assumptions."
        roi_metric = f"{roi_leader} leads"

    return [
        {
            "title": "Investment Recommendation",
            "metric": winner,
            "body": (
                f"The model recommends {winner} because it delivers the highest net value "
                f"across {len(comparison)} projects over the selected horizon."
            ),
        },
        {
            "title": "Financial Impact",
            "metric": signed_usd(net_delta),
            "body": (
                f"Net value gap is shown versus {runner_up}. "
                f"The pre-cost revenue gap versus the next best project is {signed_usd(revenue_delta)}."
            ),
        },
        {
            "title": "ROI and Risk Drivers",
            "metric": roi_metric,
            "body": (
                f"{roi_line} The key decision drivers are new customer acquisition, plan mix, "
                "price changes, churn variation, and project cost."
            ),
        },
    ]


def project_label(index: int) -> str:
    return f"Project {chr(ord('A') + index)}"


def normalize_mix(monthly_pct: float, annual_pct: float) -> tuple[float, float]:
    total = monthly_pct + annual_pct
    if total <= 0:
        return 0.50, 0.50
    return monthly_pct / total, annual_pct / total


def database_url_from_secrets() -> str | None:
    try:
        connections = st.secrets.get("connections", {})
        neon = connections.get("neon", {})
        return neon.get("url")
    except Exception:
        return None


@st.cache_resource(show_spinner=False)
def cached_database_engine(database_url: str):
    return engine_from_url(database_url)


def current_scenario_payload() -> dict[str, object]:
    project_count = int(st.session_state.get("project_count", 2))
    project_names = [project_label(index) for index in range(project_count)]
    return {
        "horizon_years": st.session_state.get("horizon_years", 4),
        "current_customers": st.session_state.get("current_customers", 0),
        "monthly_newly_acquired_pct": st.session_state.get("monthly_newly_acquired_pct", 50.0),
        "annual_newly_acquired_pct": st.session_state.get("annual_newly_acquired_pct", 50.0),
        "monthly_price": st.session_state.get("monthly_price", 10.0),
        "yearly_price": st.session_state.get("yearly_price", 60.0),
        "monthly_churn_pct": st.session_state.get("monthly_churn_pct", 5.0),
        "yearly_churn_y1_pct": st.session_state.get("yearly_churn_y1_pct", 35.0),
        "yearly_churn_y2_pct": st.session_state.get("yearly_churn_y2_pct", 20.0),
        "yearly_churn_y3_pct": st.session_state.get("yearly_churn_y3_pct", 12.0),
        "yearly_churn_y4_pct": st.session_state.get("yearly_churn_y4_pct", 12.0),
        "project_count": project_count,
        "projects": {
            project_name: {
                "display_name": st.session_state.get(
                    f"{project_name}_display_name",
                    "Retention Boost" if project_name == "Project A" else "Content Expansion" if project_name == "Project B" else "",
                ),
                "new_customers": st.session_state.get(f"{project_name}_new_customers", 0),
                "monthly_plan_pct": st.session_state.get(f"{project_name}_monthly_plan_pct", 50.0),
                "annual_plan_pct": st.session_state.get(f"{project_name}_annual_plan_pct", 50.0),
                "monthly_price_change": st.session_state.get(f"{project_name}_monthly_price_change", 0.0),
                "annual_price_change": st.session_state.get(f"{project_name}_annual_price_change", 0.0),
                "monthly_churn_variation": None
                if project_name == "Project A"
                else st.session_state.get(f"{project_name}_monthly_churn_variation", 0.0),
                "annual_churn_variation": None
                if project_name == "Project A"
                else st.session_state.get(f"{project_name}_annual_churn_variation", 0.0),
                "retention_improvement": st.session_state.get(
                    f"{project_name}_retention_improvement",
                    20.0 if project_name == "Project A" else 0.0,
                ),
                "cost": st.session_state.get(f"{project_name}_cost", 0.0),
            }
            for project_name in project_names
        },
    }


def apply_scenario_payload(payload: dict[str, object]) -> None:
    for key in [
        "horizon_years",
        "current_customers",
        "monthly_newly_acquired_pct",
        "annual_newly_acquired_pct",
        "monthly_price",
        "yearly_price",
        "monthly_churn_pct",
        "yearly_churn_y1_pct",
        "yearly_churn_y2_pct",
        "yearly_churn_y3_pct",
        "yearly_churn_y4_pct",
        "project_count",
    ]:
        if key in payload:
            st.session_state[key] = payload[key]

    projects = payload.get("projects", {})
    if isinstance(projects, dict):
        for project_name, values in projects.items():
            if not isinstance(values, dict):
                continue
            mapping = {
                "display_name": f"{project_name}_display_name",
                "new_customers": f"{project_name}_new_customers",
                "monthly_plan_pct": f"{project_name}_monthly_plan_pct",
                "annual_plan_pct": f"{project_name}_annual_plan_pct",
                "monthly_price_change": f"{project_name}_monthly_price_change",
                "annual_price_change": f"{project_name}_annual_price_change",
                "monthly_churn_variation": f"{project_name}_monthly_churn_variation",
                "annual_churn_variation": f"{project_name}_annual_churn_variation",
                "retention_improvement": f"{project_name}_retention_improvement",
                "cost": f"{project_name}_cost",
            }
            for source_key, state_key in mapping.items():
                if source_key in values:
                    if source_key == "retention_improvement" and values[source_key] is None:
                        continue
                    st.session_state[state_key] = values[source_key]


def chart_line(df: pd.DataFrame, y: str, title: str, value_title: str) -> alt.Chart:
    scenario_order = ["Current Scenario"] + [
        scenario for scenario in sorted(df["scenario"].dropna().unique()) if scenario != "Current Scenario"
    ]
    return (
        alt.Chart(df)
        .mark_line(point=True, strokeWidth=3)
        .encode(
            x=alt.X(
                "year_label:N",
                title=None,
                sort=alt.SortField("year", order="ascending"),
            ),
            y=alt.Y(f"{y}:Q", title=value_title),
            color=alt.Color(
                "scenario:N",
                title="Scenario",
                scale=alt.Scale(
                    domain=scenario_order,
                    range=SCENARIO_COLORS[: len(scenario_order)],
                ),
            ),
            tooltip=[
                alt.Tooltip("scenario:N", title="Scenario"),
                alt.Tooltip("year_label:N", title="Year"),
                alt.Tooltip(f"{y}:Q", title=value_title, format=",.0f"),
            ],
        )
        .properties(height=320, title=title)
    )


def kpi_bar_chart(df: pd.DataFrame, metric: str, title: str, value_title: str, fmt: str) -> alt.Chart:
    return (
        alt.Chart(df)
        .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
        .encode(
            x=alt.X("project_short:N", title=None, sort=None),
            y=alt.Y(f"{metric}:Q", title=value_title),
            color=alt.Color(
                "project_short:N",
                legend=None,
                scale=alt.Scale(scheme="tableau10"),
            ),
            tooltip=[
                alt.Tooltip("project:N", title="Project"),
                alt.Tooltip(f"{metric}:Q", title=value_title, format=fmt),
            ],
        )
        .properties(height=300, title=title)
    )


st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

if "pending_scenario_payload" in st.session_state:
    pending_payload = st.session_state.pop("pending_scenario_payload")
    if isinstance(pending_payload, dict):
        apply_scenario_payload(pending_payload)

with st.sidebar:
    with st.expander("Actual Assumptions", expanded=True):
        st.subheader("Time Horizon (Years)")
        horizon_years = st.slider(
            "Investment horizon",
            1,
            20,
            4,
            1,
            format="%d years",
            key="horizon_years",
        )

        st.divider()
        st.subheader("Current Customers")
        current_customers = st.number_input("Current customers", 0, 5_000_000, 0, 500, key="current_customers")
        st.caption(
            "Optional existing book of business, shown only as a separate 'Current Scenario' "
            "reference line. It is independent of every project below: no project adds to it "
            "or subtracts from it. Leave at 0 if you are only comparing newly acquired cohorts."
        )

        st.divider()
        st.subheader("Acquisition")
        monthly_newly_acquired_pct = st.number_input(
            "% Monthly newly acquired customers",
            0.0,
            100.0,
            50.0,
            1.0,
            key="monthly_newly_acquired_pct",
        )
        annual_newly_acquired_pct = st.number_input(
            "% Annual newly acquired customers",
            0.0,
            100.0,
            50.0,
            1.0,
            key="annual_newly_acquired_pct",
        )
        monthly_mix, yearly_mix = normalize_mix(monthly_newly_acquired_pct, annual_newly_acquired_pct)

        st.divider()
        st.subheader("Price")
        monthly_price = st.number_input("Monthly plan price", 0.0, 250.0, 10.0, 1.0, key="monthly_price")
        yearly_price = st.number_input("Annual plan price", 0.0, 1_000.0, 60.0, 5.0, key="yearly_price")

        st.divider()
        st.subheader("Retention")
        monthly_churn_pct = st.slider(
            "Monthly churn",
            0.0,
            30.0,
            5.0,
            0.5,
            format="%.1f%%",
            key="monthly_churn_pct",
        )
        st.caption("Annual churn")
        yearly_churn_y1_pct = st.slider("Year 1", 0.0, 80.0, 35.0, 1.0, format="%.0f%%", key="yearly_churn_y1_pct")
        yearly_churn_y2_pct = st.slider("Year 2", 0.0, 80.0, 20.0, 1.0, format="%.0f%%", key="yearly_churn_y2_pct")
        yearly_churn_y3_pct = st.slider("Year 3", 0.0, 80.0, 12.0, 1.0, format="%.0f%%", key="yearly_churn_y3_pct")
        yearly_churn_y4_pct = st.slider("Year 4", 0.0, 80.0, 12.0, 1.0, format="%.0f%%", key="yearly_churn_y4_pct")

    st.divider()
    with st.expander("Sensitivity Analysis", expanded=True):
        st.subheader("How many projects?")
        project_count = st.number_input("Projects being analyzed", 2, 8, 2, 1, key="project_count")
        project_names = [project_label(index) for index in range(int(project_count))]
        project_descriptions = {
            "Project A": "Retention Boost",
            "Project B": "Content Expansion",
        }
        project_new_customers = {}
        project_monthly_price_changes = {}
        project_yearly_price_changes = {}
        project_monthly_churn_variations = {}
        project_yearly_churn_variations = {}
        project_retention_improvements = {}
        project_plan_mixes = {}
        project_display_names = {}
        for project_name in project_names:
            default_display_name = project_descriptions.get(project_name, "")
            display_name_key = f"{project_name}_display_name"
            display_name = st.session_state.get(display_name_key, default_display_name)
            section_title = f"{project_name}: {display_name}" if display_name else project_name
            with st.container(border=True):
                st.markdown(f"**{section_title}**")
                project_display_names[project_name] = st.text_input(
                    "Project name",
                    value=default_display_name,
                    key=display_name_key,
                    placeholder="Write project name",
                )
                default_new_customers = 20_000 if project_name == "Project A" else 3_000 if project_name == "Project B" else 0
                new_customers_label = "How many new customers acquired?"
                project_new_customers[project_name] = st.number_input(
                    new_customers_label,
                    0,
                    1_000_000,
                    default_new_customers,
                    100,
                    key=f"{project_name}_new_customers",
                )
                plan_col_a, plan_col_b = st.columns(2)
                with plan_col_a:
                    monthly_plan_pct = st.number_input(
                        "% Monthly plan",
                        0.0,
                        100.0,
                        float(round(monthly_mix * 100)),
                        1.0,
                        key=f"{project_name}_monthly_plan_pct",
                    )
                with plan_col_b:
                    annual_plan_pct = st.number_input(
                        "% Annual plan",
                        0.0,
                        100.0,
                        float(round(yearly_mix * 100)),
                        1.0,
                        key=f"{project_name}_annual_plan_pct",
                    )
                normalized_monthly_mix, normalized_annual_mix = normalize_mix(monthly_plan_pct, annual_plan_pct)
                project_plan_mixes[project_name] = (normalized_monthly_mix, normalized_annual_mix)
                st.caption(
                    f"Plan mix used: {normalized_monthly_mix:.0%} monthly / {normalized_annual_mix:.0%} annual"
                )
                st.caption("Price change")
                price_col_a, price_col_b = st.columns(2)
                with price_col_a:
                    project_monthly_price_changes[project_name] = st.slider(
                        "Price change monthly plans",
                        -50.0,
                        100.0,
                        0.0,
                        1.0,
                        format="%.0f%%",
                        key=f"{project_name}_monthly_price_change",
                    )
                with price_col_b:
                    project_yearly_price_changes[project_name] = st.slider(
                        "Price change annual plans",
                        -50.0,
                        100.0,
                        0.0,
                        1.0,
                        format="%.0f%%",
                        key=f"{project_name}_annual_price_change",
                    )
                if project_name == "Project A":
                    project_monthly_churn_variations[project_name] = 0.0
                    project_yearly_churn_variations[project_name] = 0.0
                else:
                    st.caption("Churn Rate Variation")
                    churn_col_a, churn_col_b = st.columns(2)
                    with churn_col_a:
                        project_monthly_churn_variations[project_name] = st.slider(
                            "Monthly plan churn rate",
                            -50.0,
                            100.0,
                            0.0,
                            1.0,
                            format="%.0f%%",
                            key=f"{project_name}_monthly_churn_variation",
                        )
                    with churn_col_b:
                        project_yearly_churn_variations[project_name] = st.slider(
                            "Annual plan churn rate",
                            -50.0,
                            100.0,
                            0.0,
                            1.0,
                            format="%.0f%%",
                            key=f"{project_name}_annual_churn_variation",
                        )
                project_retention_improvements[project_name] = st.slider(
                    "Renewal improvement: churn reduction for this cohort",
                    0.0,
                    80.0,
                    20.0 if project_name == "Project A" else 0.0,
                    1.0,
                    format="%.0f%%",
                    key=f"{project_name}_retention_improvement",
                )
                if project_name == "Project A":
                    st.caption("Assumptions: newly acquired cohort with renewal improvement applied.")
                elif project_name == "Project B":
                    st.caption("Assumptions: newly acquired cohort using project-specific retention settings.")
                else:
                    st.caption("Assumptions to be defined.")

        st.divider()
        st.subheader("Investment Cost")
        project_costs = {
            project_name: st.number_input(
                f"{project_name} cost (USD)",
                0.0,
                10_000_000.0,
                0.0,
                10_000.0,
                key=f"{project_name}_cost",
            )
            for project_name in project_names
        }
        if st.button("Run Analysis", type="primary", width="stretch"):
            st.session_state["run_analysis_requested"] = True

    st.divider()
    with st.expander("Database / Neon", expanded=False):
        st.caption("Store generated Run Analysis scenarios and PDF reports in Postgres.")
        database_url = database_url_from_secrets()
        if not dependencies_available():
            st.warning("Database packages are missing. Install the updated requirements and restart Streamlit.")
        elif not database_url:
            st.warning("Neon is not configured yet. Add your database URL to `.streamlit/secrets.toml`.")
        else:
            try:
                engine = cached_database_engine(database_url)
                scenarios = list_scenarios(engine)
                st.success("Connected to Neon Postgres.")

                if scenarios:
                    scenario_options = {
                        f"{row['scenario_name']} - {row['created_at'].strftime('%Y-%m-%d %H:%M')}": row["id"]
                        for row in scenarios
                    }
                    selected_scenario = st.selectbox(
                        "Load saved scenario",
                        list(scenario_options.keys()),
                        key="selected_scenario",
                    )
                    if st.button("Load selected scenario", width="stretch"):
                        payload = load_scenario(engine, int(scenario_options[selected_scenario]))
                        if payload:
                            st.session_state["pending_scenario_payload"] = payload
                            st.success("Scenario loaded.")
                            st.rerun()
                else:
                    st.info("No saved scenarios yet.")
            except Exception as exc:
                st.error(f"Could not connect to Neon: {exc}")

    project_assumptions = []
    for project_name in project_names:
        project_monthly_mix, project_yearly_mix = project_plan_mixes.get(project_name, (monthly_mix, yearly_mix))
        project_assumptions.append(
            ProjectAssumption(
                key=project_name,
                name=project_display_names.get(project_name, "") or project_name,
                new_customers=int(project_new_customers.get(project_name, 0)),
                cost=float(project_costs.get(project_name, 0.0)),
                monthly_price_change=float(project_monthly_price_changes.get(project_name, 0.0)) / 100.0,
                yearly_price_change=float(project_yearly_price_changes.get(project_name, 0.0)) / 100.0,
                monthly_churn_variation=float(project_monthly_churn_variations.get(project_name, 0.0)) / 100.0,
                yearly_churn_variation=float(project_yearly_churn_variations.get(project_name, 0.0)) / 100.0,
                churn_improvement=float(project_retention_improvements.get(project_name, 0.0)) / 100.0,
                monthly_mix=float(project_monthly_mix),
                yearly_mix=float(project_yearly_mix),
            )
        )


st.markdown(
    f"""
<div class="hero">
  <div class="brand-mark" aria-label="Instanter logo">
    <svg viewBox="0 0 64 64" role="img" aria-hidden="true" focusable="false">
      <g transform="rotate(180 32 32)">
        <path d="M24 3 48 24 38 24 48 61 16 32 28 32 24 3Z" fill="#10b981"/>
        <path d="M31 9 37 29 28 29 39 53" fill="none" stroke="#ffffff" stroke-width="4.2" stroke-linecap="square" stroke-linejoin="miter"/>
      </g>
    </svg>
    <span>INSTANTER SAAS</span>
  </div>
  <div class="hero-title">INSTANTER SAAS<br>The Strategic Investment Decision Tool</div>
  <div class="hero-subtitle">
    A flexible decision simulator for comparing SaaS investment projects over time.
  </div>
</div>
""",
    unsafe_allow_html=True,
)


inputs = ModelInputs(
    existing_customers=int(current_customers),
    monthly_mix=float(monthly_mix),
    yearly_mix=float(yearly_mix),
    monthly_price=float(monthly_price),
    yearly_price=float(yearly_price),
    monthly_churn=float(monthly_churn_pct) / 100.0,
    yearly_churn_y1=float(yearly_churn_y1_pct) / 100.0,
    yearly_churn_y2=float(yearly_churn_y2_pct) / 100.0,
    yearly_churn_y3=float(yearly_churn_y3_pct) / 100.0,
    yearly_churn_y4=float(yearly_churn_y4_pct) / 100.0,
    horizon_years=int(horizon_years),
)

model = build_projects_model(inputs, project_assumptions)
comparison = model["comparison"].copy()
recommendation = model["recommendation"]

insights = insight_cards(comparison, recommendation)

# Each project's line is that project's own acquired cohort (already an absolute total,
# not a delta). 'Current Scenario' is the optional, independent existing-book reference
# from 'Current customers' — it is not added to any project's numbers.
baseline_plot = model["baseline_existing"].assign(scenario="Current Scenario")
project_plots = [
    incremental_df.assign(scenario=project_key)
    for project_key, incremental_df in model["project_incrementals"].items()
]
plot_df = pd.concat([baseline_plot, *project_plots], ignore_index=True)
plot_df = (
    plot_df.groupby(["scenario", "year"], as_index=False)
    .agg(
        total_customers=("total_customers", "last"),
        total_revenue=("total_revenue", "sum"),
    )
)
plot_df["year_label"] = "Year " + plot_df["year"].astype(str)

chart_metrics = comparison.copy()
chart_metrics["project_short"] = chart_metrics["project"].str.extract(r"^(Project [A-Z])")
chart_metrics["roi_percent"] = pd.to_numeric(chart_metrics["roi"], errors="coerce").fillna(0.0) * 100
chart_metrics["payback_years"] = chart_metrics["payback_month"].apply(
    lambda value: None if pd.isna(value) else value / 12
)
payback_chart_metrics = chart_metrics.dropna(subset=["payback_years"])

if "generated_scenarios" not in st.session_state:
    st.session_state["generated_scenarios"] = []

if st.session_state.pop("run_analysis_requested", False):
    database_url = database_url_from_secrets()
    engine = None
    if database_url and dependencies_available():
        try:
            engine = cached_database_engine(database_url)
        except Exception:
            engine = None
    try:
        scenario_number = next_scenario_number(engine) if engine is not None else len(st.session_state["generated_scenarios"]) + 1
    except Exception:
        engine = None
        scenario_number = len(st.session_state["generated_scenarios"]) + 1
    scenario_name = f"Scenario {scenario_number}"
    payload = current_scenario_payload()
    payload["scenario_number"] = scenario_number
    payload["scenario_name"] = scenario_name
    pdf_bytes = build_analysis_report_pdf(
        scenario_name=scenario_name,
        subtitle="A flexible decision simulator for comparing SaaS investment projects over time.",
        assumptions=payload,
        insights=insights,
        comparison=comparison,
        yearly_plot=plot_df,
    )
    if engine is not None:
        try:
            save_scenario(engine, scenario_name, payload, scenario_number=scenario_number, pdf_file=pdf_bytes)
            st.toast(f"{scenario_name} saved to Neon with PDF.")
        except Exception:
            st.warning(f"{scenario_name} was generated, but Neon could not save it. The PDF is still available below.")
    else:
        st.toast(f"{scenario_name} created. Configure Neon to persist it in Postgres.")
    st.session_state["generated_scenarios"].insert(
        0,
        {
            "scenario_number": scenario_number,
            "scenario_name": scenario_name,
            "pdf_file": pdf_bytes,
        },
    )

top_metrics = comparison.head(4)
metric_columns = st.columns(len(top_metrics))
for column, (_, row) in zip(metric_columns, top_metrics.iterrows()):
    project_short = str(row["project"]).split(":")[0]
    with column:
        st.metric(f"{project_short} net value", usd(float(row["net_value"])))

st.subheader("Summary Findings & Insights")
insight_columns = st.columns(3)
with insight_columns[0]:
    card = insights[0]
    st.markdown(
        f"""
<div class="recommendation">
  <div class="insight-title">{escape(card["title"])}</div>
  <div class="insight-metric">{escape(card["metric"])}</div>
  <div class="insight-body">{escape(card["body"])}</div>
</div>
""",
        unsafe_allow_html=True,
    )
for column, card in zip(insight_columns[1:], insights[1:]):
    with column:
        with st.container(border=True):
            st.markdown(f"### {card['title']}")
            st.markdown(f"## {card['metric']}")
            st.write(card["body"])

st.subheader("Comparative KPIs")
kpi_table = comparison.copy()
kpi_table["incremental_revenue"] = kpi_table["incremental_revenue"].map(usd)
kpi_table["cost"] = kpi_table["cost"].map(usd)
kpi_table["net_value"] = kpi_table["net_value"].map(usd)
kpi_table["roi"] = kpi_table["roi"].map(pct)
kpi_table["payback_month"] = comparison.apply(
    lambda row: "n/a" if row["cost"] <= 0 else payback_label(row["payback_month"]),
    axis=1,
)
kpi_table["customer_impact"] = kpi_table["customer_impact"].map(lambda x: f"{x:,.0f}")
kpi_table = kpi_table.rename(
    columns={
        "project": "Project",
        "incremental_revenue": "Revenue",
        "cost": "Project cost",
        "net_value": "Net value",
        "roi": "ROI",
        "payback_month": "Payback",
        "customer_impact": "Customer impact",
    }
)
kpi_table = kpi_table[
    ["Project", "Revenue", "Project cost", "Net value", "ROI", "Payback", "Customer impact"]
]
current_scenario_row = pd.DataFrame(
    [
        {
            "Project": "Current Scenario",
            "Revenue": usd(float(model["baseline_existing"]["total_revenue"].sum())),
            "Project cost": usd(0),
            "Net value": usd(float(model["baseline_existing"]["total_revenue"].sum())),
            "ROI": "n/a",
            "Payback": "n/a",
            "Customer impact": f"{float(model['baseline_existing']['total_customers'].iloc[-1]):,.0f}",
        }
    ]
)
kpi_table = pd.concat([current_scenario_row, kpi_table], ignore_index=True)
st.dataframe(kpi_table, width="stretch", hide_index=True)

tab_customers, tab_revenue, tab_net_value, tab_roi, tab_payback = st.tabs(
    ["Customer Evolution", "Revenue Evolution", "Net Value", "ROI", "Payback"]
)

with tab_customers:
    st.altair_chart(
        chart_line(plot_df, "total_customers", "Customers by Scenario", "Customers"),
        use_container_width=True,
    )

with tab_revenue:
    st.altair_chart(
        chart_line(plot_df, "total_revenue", "Annual Revenue by Scenario", "Revenue"),
        use_container_width=True,
    )

with tab_net_value:
    st.altair_chart(
        kpi_bar_chart(chart_metrics, "net_value", "Net Value by Project", "Net Value", "$,.0f"),
        use_container_width=True,
    )

with tab_roi:
    if chart_metrics["roi"].notna().any():
        st.altair_chart(
            kpi_bar_chart(chart_metrics, "roi_percent", "ROI by Project", "ROI", ",.1f"),
            use_container_width=True,
        )
    else:
        st.info("Add project costs to calculate ROI.")

with tab_payback:
    st.caption("Payback uses gross incremental cash inflows. Annual plans are treated as paid upfront in the first month of each year.")
    if not payback_chart_metrics.empty:
        st.altair_chart(
            kpi_bar_chart(payback_chart_metrics, "payback_years", "Payback by Project", "Payback Years", ",.1f"),
            use_container_width=True,
        )
    else:
        st.info("Add project costs to calculate payback.")

st.subheader("Run Analysis History")
database_url = database_url_from_secrets()
db_scenarios = []
db_engine = None
if database_url and dependencies_available():
    try:
        db_engine = cached_database_engine(database_url)
        db_scenarios = list_scenarios(db_engine, limit=100)
    except Exception:
        db_scenarios = []

if db_scenarios:
    st.caption("All generated scenarios saved in Neon/Postgres")
    for row in db_scenarios:
        scenario_number = row.get("scenario_number")
        if scenario_number is None:
            scenario_number = row["id"]
        label = scenario_display_name(int(scenario_number), str(row["scenario_name"]))
        created_at = row["created_at"].strftime("%Y-%m-%d %H:%M")
        cols = st.columns([1.6, 1.1, 1])
        with cols[0]:
            st.write(f"**{label}**")
        with cols[1]:
            st.caption(created_at)
        with cols[2]:
            try:
                pdf_bytes = load_scenario_pdf(db_engine, int(row["id"])) if db_engine and row.get("has_pdf") else None
            except Exception:
                pdf_bytes = None
            if pdf_bytes:
                st.download_button(
                    "Download PDF",
                    data=pdf_bytes,
                    file_name=scenario_file_name(str(row["scenario_name"])),
                    mime="application/pdf",
                    key=f"download_db_{row['id']}",
                    width="stretch",
                )
            else:
                st.caption("No PDF")
elif st.session_state["generated_scenarios"]:
    st.caption("Generated in this session. Configure Neon to keep the full history after restart.")
    for scenario in st.session_state["generated_scenarios"]:
        cols = st.columns([1.6, 1.1, 1])
        with cols[0]:
            st.write(
                f"**{scenario_display_name(int(scenario['scenario_number']), str(scenario['scenario_name']))}**"
            )
        with cols[1]:
            st.caption("Current session")
        with cols[2]:
            st.download_button(
                "Download PDF",
                data=scenario["pdf_file"],
                file_name=scenario_file_name(str(scenario["scenario_name"])),
                mime="application/pdf",
                key=f"download_local_{scenario['scenario_number']}",
                width="stretch",
            )
else:
    st.info("Run an analysis to create Scenario 1 and generate the first PDF report.")
