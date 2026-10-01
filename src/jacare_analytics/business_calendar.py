"""Calendário informado pelo usuário; não cria observações históricas."""

import json
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

DEFAULT_PATH = Path(__file__).resolve().parents[2] / "config/business_calendar.json"


def load_calendar(project_root: Path | None = None) -> dict:
    candidate = project_root / "config/business_calendar.json" if project_root else DEFAULT_PATH
    path = candidate if candidate.exists() else DEFAULT_PATH
    calendar = json.loads(path.read_text(encoding="utf-8"))
    days = calendar["open_weekdays"]
    if not days or len(days) != len(set(days)) or any(type(day) is not int or day not in range(7) for day in days):
        raise ValueError("Calendário com dias de funcionamento inválidos.")
    ZoneInfo(calendar["timezone"])
    opens = datetime.strptime(calendar["opens_at"], "%H:%M").time()
    closes = datetime.strptime(calendar["closes_at"], "%H:%M").time()
    if opens >= closes:
        raise ValueError("O contrato atual exige abertura e fechamento no mesmo dia.")
    if type(calendar.get("historical_exceptions_validated", False)) is not bool:
        raise ValueError("A validação das exceções históricas precisa ser verdadeira ou falsa.")
    return calendar


def is_open(day: date, calendar: dict) -> bool:
    return day.weekday() in calendar["open_weekdays"]


def freshness(source_end: date, calendar: dict, as_of: date | None = None) -> dict:
    today = as_of or datetime.now(ZoneInfo(calendar["timezone"])).date()
    expected = today - timedelta(days=1)
    while not is_open(expected, calendar):
        expected -= timedelta(days=1)
    return {"as_of_date":today.isoformat(), "last_expected_complete_open_day":expected.isoformat(), "days_since_source_end":(today-source_end).days, "supports_current_week":expected<=source_end<=today, "source_date_in_future":source_end>today}
