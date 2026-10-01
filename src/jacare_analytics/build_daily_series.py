"""Gera uma série temporal diária sem identificadores de clientes ou pedidos."""

from __future__ import annotations

import argparse
import csv
import zipfile
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from .profile_sales import (
    DEFAULT_ARCHIVE,
    ORDERS_MEMBER,
    _as_date,
    _as_number,
    _find_member,
    _get,
    _normalize_order_key,
    _required,
    _workbook_rows,
)


def build_daily_series(archive_path: Path, cutoff: date) -> tuple[list[dict[str, Any]], dict[str, int]]:
    with zipfile.ZipFile(archive_path) as archive:
        member = _find_member(archive, ORDERS_MEMBER)
        payload = archive.read(member)

    workbook, rows, columns = _workbook_rows(payload)
    wanted = _required(columns, "Código", "Data Abertura", "Status", "Total Recebido")
    daily: dict[date, dict[str, float]] = defaultdict(
        lambda: {"paid_orders": 0, "total_received_brl": 0.0}
    )
    seen_order_keys: set[str] = set()
    dates: list[date] = []
    duplicate_rows = missing_date_paid_rows = excluded_after_cutoff = 0
    try:
        for row in rows:
            opened = _as_date(_get(row, wanted, "Data Abertura"))
            if opened is None:
                if str(_get(row, wanted, "Status") or "").strip().casefold() == "finalizado - pago":
                    missing_date_paid_rows += 1
                continue
            if opened <= cutoff:
                dates.append(opened)
            else:
                excluded_after_cutoff += 1

            status = " ".join(str(_get(row, wanted, "Status") or "").split()).casefold()
            if status != "finalizado - pago" or opened > cutoff:
                continue

            order_key = _normalize_order_key(_get(row, wanted, "Código"))
            if order_key is not None and order_key in seen_order_keys:
                duplicate_rows += 1
                continue
            if order_key is not None:
                seen_order_keys.add(order_key)

            daily[opened]["paid_orders"] += 1
            amount = _as_number(_get(row, wanted, "Total Recebido"))
            if amount is not None:
                daily[opened]["total_received_brl"] += amount
    finally:
        workbook.close()

    if not dates:
        raise RuntimeError("Não encontrei datas válidas antes do corte informado.")

    first_day = min(dates)
    result: list[dict[str, Any]] = []
    current = first_day
    zero_order_days = 0
    while current <= min(cutoff, max(dates)):
        values = daily[current]
        if values["paid_orders"] == 0:
            zero_order_days += 1
        result.append(
            {
                "date": current.isoformat(),
                "paid_orders": int(values["paid_orders"]) if current in dates else None,
                "total_received_brl": round(values["total_received_brl"], 2) if current in dates else None,
            }
        )
        current += timedelta(days=1)

    metadata = {
        "rows": len(result),
        "zero_order_days": zero_order_days,
        "duplicate_rows_skipped": duplicate_rows,
        "missing_date_paid_rows": missing_date_paid_rows,
        "source_rows_after_cutoff": excluded_after_cutoff,
    }
    return result, metadata


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Cria uma série diária agregada de pedidos pagos para análise local."
    )
    parser.add_argument("archive", nargs="?", type=Path, default=DEFAULT_ARCHIVE)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/daily_sales_ml.csv"),
    )
    parser.add_argument(
        "--cutoff",
        type=date.fromisoformat,
        default=date(2026, 8, 19),
        help="Última data completa no formato AAAA-MM-DD (padrão: 2026-08-19).",
    )
    args = parser.parse_args()
    series, metadata = build_daily_series(args.archive, args.cutoff)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=["date", "paid_orders", "total_received_brl"],
        )
        writer.writeheader()
        writer.writerows(series)
    print(
        f"Série agregada salva em {args.output}: {metadata['rows']} dias; "
        f"{metadata['zero_order_days']} dias sem pedidos pagos registrados."
    )


if __name__ == "__main__":
    main()
