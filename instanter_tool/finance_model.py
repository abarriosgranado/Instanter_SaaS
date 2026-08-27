from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


MONTHS_IN_YEAR = 12


@dataclass(frozen=True)
class ModelInputs:
    existing_customers: int = 0
    monthly_mix: float = 0.50
    yearly_mix: float = 0.50
    monthly_price: float = 10.0
    yearly_price: float = 60.0
    monthly_churn: float = 0.05
    yearly_churn_y1: float = 0.35
    yearly_churn_y2: float = 0.20
    yearly_churn_y3: float = 0.12
    yearly_churn_y4: float = 0.12
    horizon_years: int = 4

    @property
    def horizon_months(self) -> int:
        return max(1, self.horizon_years) * MONTHS_IN_YEAR

    @property
    def yearly_churn_rates(self) -> list[float]:
        rates = [
            self.yearly_churn_y1,
            self.yearly_churn_y2,
            self.yearly_churn_y3,
            self.yearly_churn_y4,
        ]
        if self.horizon_years > len(rates):
            rates.extend([rates[-1]] * (self.horizon_years - len(rates)))
        return rates[: self.horizon_years]


@dataclass(frozen=True)
class ProjectAssumption:
    key: str
    name: str
    new_customers: int = 0
    cost: float = 0.0
    monthly_price_change: float = 0.0
    yearly_price_change: float = 0.0
    monthly_churn_variation: float = 0.0
    yearly_churn_variation: float = 0.0
    churn_improvement: float = 0.0
    monthly_mix: float | None = None
    yearly_mix: float | None = None


def apply_churn_improvement(churn_rate: float, improvement: float) -> float:
    return max(0.0, min(1.0, churn_rate * (1.0 - improvement)))


def apply_churn_variation(churn_rate: float, variation: float) -> float:
    return max(0.0, min(1.0, churn_rate * (1.0 + variation)))


def simulate_cohort(
    customers: int,
    inputs: ModelInputs,
    monthly_churn: float | None = None,
    yearly_churn_rates: list[float] | None = None,
    monthly_price_change: float = 0.0,
    yearly_price_change: float = 0.0,
    monthly_mix: float | None = None,
    yearly_mix: float | None = None,
) -> pd.DataFrame:
    """Simulate a January-acquired customer cohort over the selected horizon."""
    monthly_churn = inputs.monthly_churn if monthly_churn is None else monthly_churn
    yearly_churn_rates = inputs.yearly_churn_rates if yearly_churn_rates is None else yearly_churn_rates
    monthly_price = inputs.monthly_price * (1.0 + monthly_price_change)
    yearly_price = inputs.yearly_price * (1.0 + yearly_price_change)
    monthly_mix = inputs.monthly_mix if monthly_mix is None else monthly_mix
    yearly_mix = inputs.yearly_mix if yearly_mix is None else yearly_mix

    monthly_start = customers * monthly_mix
    yearly_start = customers * yearly_mix
    monthly_active = monthly_start
    yearly_active_by_year = {1: yearly_start}

    rows: list[dict[str, float | int]] = []
    for month in range(1, inputs.horizon_months + 1):
        year = int(np.ceil(month / MONTHS_IN_YEAR))
        month_in_year = ((month - 1) % MONTHS_IN_YEAR) + 1
        yearly_active = yearly_active_by_year.get(year, 0.0)

        monthly_revenue = monthly_active * monthly_price
        yearly_revenue = yearly_active * yearly_price if month_in_year == 1 else 0.0

        rows.append(
            {
                "month": month,
                "year": year,
                "monthly_customers": monthly_active,
                "yearly_customers": yearly_active,
                "total_customers": monthly_active + yearly_active,
                "monthly_revenue": monthly_revenue,
                "yearly_revenue": yearly_revenue,
                "total_revenue": monthly_revenue + yearly_revenue,
            }
        )

        monthly_active *= 1.0 - monthly_churn

        if month_in_year == MONTHS_IN_YEAR and year < inputs.horizon_years:
            churn_rate = yearly_churn_rates[min(year - 1, len(yearly_churn_rates) - 1)]
            yearly_active_by_year[year + 1] = yearly_active * (1.0 - churn_rate)

    return pd.DataFrame(rows)


def payback_month(cash_flows: pd.Series, investment: float) -> int | None:
    if investment <= 0:
        return None
    cumulative = cash_flows.cumsum()
    recovered = cumulative[cumulative >= investment]
    if recovered.empty:
        return None
    return int(recovered.index[0]) + 1


def project_metrics(
    project_name: str,
    incremental_df: pd.DataFrame,
    cost: float,
) -> dict[str, float | int | str | None]:
    incremental_revenue = float(incremental_df["total_revenue"].sum())
    net_value = incremental_revenue - cost
    roi = None if cost <= 0 else net_value / cost
    payback = payback_month(incremental_df["total_revenue"], cost)
    customer_impact = float(incremental_df["total_customers"].iloc[-1])

    return {
        "project": project_name,
        "incremental_revenue": incremental_revenue,
        "cost": cost,
        "net_value": net_value,
        "roi": roi,
        "payback_month": payback,
        "customer_impact": customer_impact,
    }


def project_incremental_dataframe(
    inputs: ModelInputs,
    project: ProjectAssumption,
) -> pd.DataFrame:
    """Simulate the cohort of customers this project acquires (its own January intake),
    applying the project's retention and pricing assumptions to that cohort directly.

    There is no subtraction against a separate "existing customers" baseline: each
    project is evaluated as its own acquired cohort, consistent with a brief where every
    project is a distinct group of customers acquired in the same month, some with
    improved retention and some with baseline retention.
    """
    monthly_churn = inputs.monthly_churn
    yearly_churn_rates = list(inputs.yearly_churn_rates)

    monthly_churn = apply_churn_improvement(monthly_churn, project.churn_improvement)
    yearly_churn_rates = [apply_churn_improvement(rate, project.churn_improvement) for rate in yearly_churn_rates]

    monthly_churn = apply_churn_variation(monthly_churn, project.monthly_churn_variation)
    yearly_churn_rates = [apply_churn_variation(rate, project.yearly_churn_variation) for rate in yearly_churn_rates]

    return simulate_cohort(
        project.new_customers,
        inputs,
        monthly_churn=monthly_churn,
        yearly_churn_rates=yearly_churn_rates,
        monthly_price_change=project.monthly_price_change,
        yearly_price_change=project.yearly_price_change,
        monthly_mix=project.monthly_mix,
        yearly_mix=project.yearly_mix,
    )


def build_projects_model(
    inputs: ModelInputs,
    projects: list[ProjectAssumption],
) -> dict[str, pd.DataFrame | dict[str, float | int | str | None] | dict[str, pd.DataFrame]]:
    # 'baseline_existing' is an optional, independent reference line (e.g. an existing
    # book of business you already have, separate from any project). It is never added
    # to or subtracted from a project's own cohort math below.
    baseline_existing = simulate_cohort(inputs.existing_customers, inputs)
    project_incrementals: dict[str, pd.DataFrame] = {}
    metrics = []

    for project in projects:
        incremental = project_incremental_dataframe(inputs, project)
        project_incrementals[project.key] = incremental
        metrics.append(
            project_metrics(
                f"{project.key}: {project.name}" if project.name else project.key,
                incremental,
                project.cost,
            )
        )

    comparison = pd.DataFrame(metrics).sort_values("net_value", ascending=False).reset_index(drop=True)
    recommendation = recommend_projects(comparison)
    return {
        "baseline_existing": baseline_existing,
        "project_incrementals": project_incrementals,
        "comparison": comparison,
        "recommendation": recommendation,
    }


def recommend_projects(comparison: pd.DataFrame) -> dict[str, str | float]:
    if comparison.empty:
        return {
            "winner": "n/a",
            "runner_up": "n/a",
            "reason": "no projects to compare",
            "net_value_gap": 0.0,
            "break_even_cost_differential": 0.0,
        }

    winner = comparison.iloc[0]
    runner_up = comparison.iloc[1] if len(comparison) > 1 else None
    has_project_costs = bool((comparison["cost"].astype(float) > 0).any())
    reason = "higher net value after project cost" if has_project_costs else "higher incremental revenue before project cost"
    net_gap = 0.0 if runner_up is None else float(winner["net_value"]) - float(runner_up["net_value"])
    revenue_gap = 0.0 if runner_up is None else float(winner["incremental_revenue"]) - float(runner_up["incremental_revenue"])

    return {
        "winner": str(winner["project"]),
        "runner_up": "n/a" if runner_up is None else str(runner_up["project"]),
        "reason": reason,
        "net_value_gap": net_gap,
        "break_even_cost_differential": revenue_gap,
    }
