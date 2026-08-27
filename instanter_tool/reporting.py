from __future__ import annotations

from io import BytesIO
from typing import Any

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


def usd(value: float) -> str:
    return f"${value:,.0f}"


def pct(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{value:.1%}"


def payback_label(month: int | None) -> str:
    if month is None or pd.isna(month):
        return "n/a"
    return f"{month / 12:.1f} years"


def build_analysis_report_pdf(
    scenario_name: str,
    subtitle: str,
    assumptions: dict[str, Any],
    insights: list[dict[str, str]],
    comparison: pd.DataFrame,
    yearly_plot: pd.DataFrame,
) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=0.55 * inch,
        leftMargin=0.55 * inch,
        topMargin=0.55 * inch,
        bottomMargin=0.55 * inch,
    )
    styles = _styles()
    story: list[Any] = []

    story.append(Paragraph("INSTANTER SAAS", styles["brand"]))
    story.append(Paragraph("The SaaS Strategic Investment Decision Tool", styles["title"]))
    story.append(Paragraph(scenario_name, styles["scenario"]))
    story.append(Paragraph(subtitle, styles["body"]))
    story.append(Spacer(1, 0.22 * inch))

    story.append(Paragraph("Actual Assumptions", styles["section"]))
    story.append(_actual_assumptions_table(assumptions))
    story.append(Spacer(1, 0.16 * inch))

    story.append(Paragraph("Sensitivity Analysis Inputs", styles["section"]))
    story.extend(_sensitivity_inputs_cards(assumptions, styles))
    story.append(PageBreak())

    story.append(Paragraph("Summary Findings & Insights", styles["section"]))
    story.extend(_insight_table(insights, styles))
    story.append(Spacer(1, 0.2 * inch))

    story.append(Paragraph("Comparative KPIs", styles["section"]))
    story.append(_comparison_table(comparison, yearly_plot))

    story.append(PageBreak())
    story.append(Paragraph("Customer and Revenue Evolution", styles["section"]))
    story.append(_yearly_table(yearly_plot))
    story.append(Spacer(1, 0.18 * inch))
    story.append(Paragraph("Net Value, ROI and Payback", styles["section"]))
    story.append(_financial_chart_table(comparison))

    doc.build(story)
    return buffer.getvalue()


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "brand": ParagraphStyle(
            "brand",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=14,
            textColor=colors.HexColor("#0f766e"),
            spaceAfter=8,
        ),
        "title": ParagraphStyle(
            "title",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=23,
            leading=28,
            textColor=colors.HexColor("#17202a"),
            alignment=TA_LEFT,
            spaceAfter=6,
        ),
        "scenario": ParagraphStyle(
            "scenario",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=15,
            textColor=colors.HexColor("#17202a"),
            spaceAfter=8,
        ),
        "section": ParagraphStyle(
            "section",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=16,
            textColor=colors.HexColor("#17202a"),
            spaceBefore=8,
            spaceAfter=8,
        ),
        "card_title": ParagraphStyle(
            "card_title",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=14,
            textColor=colors.HexColor("#17202a"),
        ),
        "card_metric": ParagraphStyle(
            "card_metric",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=15,
            leading=18,
            textColor=colors.HexColor("#0f766e"),
        ),
        "body": ParagraphStyle(
            "body",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=13,
            textColor=colors.HexColor("#5f6f7a"),
        ),
    }


def _insight_table(insights: list[dict[str, str]], styles: dict[str, ParagraphStyle]) -> list[Any]:
    cells = []
    for insight in insights:
        cells.append(
            [
                Paragraph(insight["title"], styles["card_title"]),
                Paragraph(insight["metric"], styles["card_metric"]),
                Paragraph(insight["body"], styles["body"]),
            ]
        )
    table = Table([cells], colWidths=[2.35 * inch, 2.35 * inch, 2.35 * inch])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, 0), colors.HexColor("#eef8f7")),
                ("BOX", (0, 0), (-1, -1), 0.75, colors.HexColor("#d8e1e7")),
                ("INNERGRID", (0, 0), (-1, -1), 0.75, colors.HexColor("#d8e1e7")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )
    return [table]


def _actual_assumptions_table(assumptions: dict[str, Any]) -> Table:
    project_a = assumptions.get("projects", {}).get("Project A", {}) if isinstance(assumptions.get("projects"), dict) else {}
    rows = [
        ["Area", "Variable", "Value"],
        ["Time Horizon", "Time Horizon (Years)", f"{assumptions.get('horizon_years', 'n/a')} years"],
        ["Current Customers", "Current customers", f"{float(assumptions.get('current_customers', 0)):,.0f}"],
        ["Acquisition", "% Monthly newly acquired customers", f"{float(assumptions.get('monthly_newly_acquired_pct', 0)):.1f}%"],
        ["Acquisition", "% Annual newly acquired customers", f"{float(assumptions.get('annual_newly_acquired_pct', 0)):.1f}%"],
        ["Price", "Monthly plan price", usd(float(assumptions.get("monthly_price", 0)))],
        ["Price", "Annual plan price", usd(float(assumptions.get("yearly_price", 0)))],
        ["Retention", "Monthly churn", f"{float(assumptions.get('monthly_churn_pct', 0)):.1f}%"],
        ["Retention", "Annual churn - Year 1", f"{float(assumptions.get('yearly_churn_y1_pct', 0)):.1f}%"],
        ["Retention", "Annual churn - Year 2", f"{float(assumptions.get('yearly_churn_y2_pct', 0)):.1f}%"],
        ["Retention", "Annual churn - Year 3", f"{float(assumptions.get('yearly_churn_y3_pct', 0)):.1f}%"],
        ["Retention", "Annual churn - Year 4", f"{float(assumptions.get('yearly_churn_y4_pct', 0)):.1f}%"],
    ]
    if isinstance(project_a, dict) and project_a.get("retention_improvement") is not None:
        rows.append(
            [
                "Renewal Improvement",
                "Churn reduction applied to Project A's cohort",
                f"{float(project_a.get('retention_improvement', 0)):.1f}%",
            ]
        )
    table = Table(rows, colWidths=[1.35 * inch, 3.2 * inch, 1.35 * inch])
    table.setStyle(_table_style(font_size=8.4))
    return table


def _sensitivity_inputs_cards(assumptions: dict[str, Any], styles: dict[str, ParagraphStyle]) -> list[Any]:
    cards: list[Any] = []
    projects = assumptions.get("projects", {})
    if isinstance(projects, dict):
        for project_key, values in projects.items():
            if not isinstance(values, dict):
                continue
            project_title = f"{project_key}: {values.get('display_name') or '-'}"
            rows = [
                [Paragraph(project_title, styles["card_title"]), ""],
                [
                    "New customers acquired",
                    f"{float(values.get('new_customers', 0)):,.0f}",
                ],
                [
                    "Plan mix",
                    (
                        f"{float(values.get('monthly_plan_pct', 0)):.0f}% monthly | "
                        f"{float(values.get('annual_plan_pct', 0)):.0f}% annual"
                    ),
                ],
                [
                    "Price change",
                    (
                        f"{float(values.get('monthly_price_change', 0)):+.0f}% monthly plans | "
                        f"{float(values.get('annual_price_change', 0)):+.0f}% annual plans"
                    ),
                ],
                ["Investment cost", usd(float(values.get("cost", 0)))],
            ]
            if values.get("monthly_churn_variation") is not None or values.get("annual_churn_variation") is not None:
                rows.insert(
                    -1,
                    [
                        "Churn rate variation",
                        (
                            f"{float(values.get('monthly_churn_variation') or 0):+.0f}% monthly plans | "
                            f"{float(values.get('annual_churn_variation') or 0):+.0f}% annual plans"
                        ),
                    ],
                )
            if values.get("retention_improvement") is not None:
                rows.insert(
                    1,
                    [
                        "Renewal improvement (churn reduction for this cohort)",
                        f"{float(values.get('retention_improvement', 0)):.0f}%",
                    ],
                )
            table = Table(rows, colWidths=[2.1 * inch, 4.1 * inch])
            table.setStyle(
                TableStyle(
                    [
                        ("SPAN", (0, 0), (-1, 0)),
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef8f7")),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#17202a")),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
                        ("FONTNAME", (1, 1), (1, -1), "Helvetica"),
                        ("FONTSIZE", (0, 0), (-1, -1), 8.6),
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d8e1e7")),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 7),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                        ("TOPPADDING", (0, 0), (-1, -1), 6),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ]
                )
            )
            cards.extend([table, Spacer(1, 0.10 * inch)])
    return cards


def _comparison_table(comparison: pd.DataFrame, yearly_plot: pd.DataFrame) -> Table:
    headers = ["Project", "Revenue", "Cost", "Net Value", "ROI", "Payback", "Customer Impact"]
    rows = [headers]
    current_rows = yearly_plot[yearly_plot["scenario"] == "Current Scenario"].sort_values("year")
    if not current_rows.empty:
        current_revenue = float(current_rows["total_revenue"].sum())
        current_customers = float(current_rows["total_customers"].iloc[-1])
        rows.append(
            [
                "Current Scenario",
                usd(current_revenue),
                usd(0),
                usd(current_revenue),
                "n/a",
                "n/a",
                f"{current_customers:,.0f}",
            ]
        )
    for _, row in comparison.iterrows():
        rows.append(
            [
                row["project"],
                usd(float(row["incremental_revenue"])),
                usd(float(row["cost"])),
                usd(float(row["net_value"])),
                pct(row["roi"]),
                payback_label(row["payback_month"]),
                f"{float(row['customer_impact']):,.0f}",
            ]
        )
    table = Table(rows, colWidths=[1.85 * inch, 0.9 * inch, 0.8 * inch, 0.9 * inch, 0.55 * inch, 0.75 * inch, 0.85 * inch])
    table.setStyle(_table_style())
    return table


def _yearly_table(yearly_plot: pd.DataFrame) -> Table:
    scenarios = ["Current Scenario"] + [
        scenario for scenario in sorted(yearly_plot["scenario"].unique()) if scenario != "Current Scenario"
    ]
    rows = [["Year", "Scenario", "Ending Customers", "Annual Revenue"]]
    for year in sorted(yearly_plot["year"].unique()):
        year_rows = yearly_plot[yearly_plot["year"] == year].set_index("scenario")
        for scenario in scenarios:
            rows.append(
                [
                    f"Year {int(year)}",
                    scenario,
                    _yearly_value(year_rows, "total_customers", scenario, number=True),
                    _yearly_value(year_rows, "total_revenue", scenario, currency=True),
                ]
            )
    table = Table(rows, colWidths=[0.9 * inch, 2.0 * inch, 1.4 * inch, 1.4 * inch])
    table.setStyle(_table_style(font_size=8.0))
    return table


def _financial_chart_table(comparison: pd.DataFrame) -> Table:
    max_net = max(abs(float(value)) for value in comparison["net_value"]) or 1.0
    rows = [["Project", "Net Value", "ROI", "Payback"]]
    for _, row in comparison.iterrows():
        net_value = float(row["net_value"])
        bar_width = max(4, int(abs(net_value) / max_net * 120))
        bar_color = "#0f766e" if net_value >= 0 else "#c2410c"
        rows.append(
            [
                row["project"],
                Paragraph(f'<font color="{bar_color}">{"■" * max(1, bar_width // 8)}</font> {usd(net_value)}', _mini_style()),
                pct(row["roi"]),
                payback_label(row["payback_month"]),
            ]
        )
    table = Table(rows, colWidths=[2.3 * inch, 2.2 * inch, 1.0 * inch, 1.0 * inch])
    table.setStyle(_table_style())
    return table


def _yearly_value(
    year_rows: pd.DataFrame,
    metric: str,
    scenario: str,
    currency: bool = False,
    number: bool = False,
) -> str:
    try:
        value = year_rows.loc[scenario, metric]
    except (KeyError, ValueError):
        value = 0
    if pd.isna(value):
        value = 0
    if currency:
        return usd(float(value))
    if number:
        return f"{float(value):,.0f}"
    return str(value)


def _table_style(font_size: float = 8.2) -> TableStyle:
    return TableStyle(
        [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f3f6f8")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#17202a")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), font_size),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d8e1e7")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]
    )


def _mini_style() -> ParagraphStyle:
    return ParagraphStyle("mini", fontName="Helvetica", fontSize=8.2, leading=10)
