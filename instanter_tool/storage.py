from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


try:
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import Engine
except ImportError:  # pragma: no cover - handled in the Streamlit UI
    create_engine = None
    text = None
    Engine = Any


CREATE_SCENARIOS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS investment_scenarios (
    id BIGSERIAL PRIMARY KEY,
    scenario_number INTEGER,
    scenario_name TEXT NOT NULL,
    payload JSONB NOT NULL,
    pdf_file BYTEA,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""


ALTER_SCENARIOS_TABLE_SQL = [
    "ALTER TABLE investment_scenarios ADD COLUMN IF NOT EXISTS scenario_number INTEGER;",
    "ALTER TABLE investment_scenarios ADD COLUMN IF NOT EXISTS pdf_file BYTEA;",
]


def dependencies_available() -> bool:
    return create_engine is not None and text is not None


def engine_from_url(database_url: str) -> Engine:
    if not dependencies_available():
        raise RuntimeError("Database dependencies are not installed.")
    return create_engine(database_url, pool_pre_ping=True)


def ensure_schema(engine: Engine) -> None:
    with engine.begin() as conn:
        conn.execute(text(CREATE_SCENARIOS_TABLE_SQL))
        for statement in ALTER_SCENARIOS_TABLE_SQL:
            conn.execute(text(statement))


def next_scenario_number(engine: Engine) -> int:
    ensure_schema(engine)
    with engine.begin() as conn:
        value = conn.execute(text("SELECT COALESCE(MAX(scenario_number), 0) + 1 FROM investment_scenarios")).scalar()
    return int(value or 1)


def save_scenario(
    engine: Engine,
    scenario_name: str,
    payload: dict[str, Any],
    scenario_number: int | None = None,
    pdf_file: bytes | None = None,
) -> int:
    ensure_schema(engine)
    if scenario_number is None:
        scenario_number = next_scenario_number(engine)
    payload = dict(payload)
    payload["saved_at"] = datetime.now(timezone.utc).isoformat()
    with engine.begin() as conn:
        scenario_id = conn.execute(
            text(
                """
                INSERT INTO investment_scenarios (scenario_number, scenario_name, payload, pdf_file)
                VALUES (:scenario_number, :scenario_name, CAST(:payload AS JSONB), :pdf_file)
                RETURNING id
                """
            ),
            {
                "scenario_number": scenario_number,
                "scenario_name": scenario_name,
                "payload": payload_to_json(payload),
                "pdf_file": pdf_file,
            },
        ).scalar_one()
    return int(scenario_id)


def list_scenarios(engine: Engine, limit: int = 25) -> list[dict[str, Any]]:
    ensure_schema(engine)
    with engine.begin() as conn:
        rows = conn.execute(
            text(
                """
                SELECT id, scenario_number, scenario_name, created_at, pdf_file IS NOT NULL AS has_pdf
                FROM investment_scenarios
                ORDER BY created_at DESC
                LIMIT :limit
                """
            ),
            {"limit": limit},
        ).mappings()
        return [dict(row) for row in rows]


def load_scenario(engine: Engine, scenario_id: int) -> dict[str, Any] | None:
    ensure_schema(engine)
    with engine.begin() as conn:
        row = conn.execute(
            text(
                """
                SELECT payload
                FROM investment_scenarios
                WHERE id = :scenario_id
                """
            ),
            {"scenario_id": scenario_id},
        ).mappings().first()
    return None if row is None else dict(row["payload"])


def load_scenario_pdf(engine: Engine, scenario_id: int) -> bytes | None:
    ensure_schema(engine)
    with engine.begin() as conn:
        row = conn.execute(
            text(
                """
                SELECT pdf_file
                FROM investment_scenarios
                WHERE id = :scenario_id
                """
            ),
            {"scenario_id": scenario_id},
        ).mappings().first()
    if row is None or row["pdf_file"] is None:
        return None
    return bytes(row["pdf_file"])


def payload_to_json(payload: dict[str, Any]) -> str:
    import json

    return json.dumps(payload, default=str)
