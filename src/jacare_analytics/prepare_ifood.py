"""Minimiza exclusivamente a aba iFood_App do relatório fornecido."""

from __future__ import annotations

import io
from collections import defaultdict
from datetime import date
from typing import Any

import pandas as pd
from openpyxl import load_workbook

from .prepare_delivery_sources import _as_datetime, _safe_category
from .profile_sales import _as_number, _normalize_header


def prepare_ifood(payload: bytes, cutoff: date) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    workbook = load_workbook(io.BytesIO(payload), read_only=True, data_only=True)
    daily = defaultdict(lambda: {"orders": 0, "items_value_brl": 0.0, "customer_paid_brl": 0.0, "delivery_fee_brl": 0.0})
    products = []
    try:
        if "iFood_App" not in workbook.sheetnames:
            raise ValueError("O relatório iFood precisa da aba iFood_App.")
        rows = workbook["iFood_App"].iter_rows(values_only=True)
        headers = None
        required = {"data e hora do pedido", "status final do pedido", "total pago pelo cliente (r$)", "valor dos itens (r$)", "taxa de entrega paga pelo cliente (r$)", "nome do item", "visitas", "pedidos", "vendas total (quantidade)", "valor total"}
        for row in rows:
            candidate = {_normalize_header(value): index for index, value in enumerate(row)}
            if required.issubset(candidate):
                headers = candidate
                break
        if headers is None:
            raise ValueError("O cabeçalho da aba iFood_App não corresponde ao contrato de dados.")
        for row in rows:
            def get(field: str):
                index = headers[field]
                return row[index] if index < len(row) else None
            opened = _as_datetime(get("data e hora do pedido"))
            if opened and opened.date() <= cutoff:
                status = _safe_category(get("status final do pedido")) or "unknown"
                bucket = daily[(opened.date(), status)]
                bucket["orders"] += 1
                for target, source in {"items_value_brl": "valor dos itens (r$)", "customer_paid_brl": "total pago pelo cliente (r$)", "delivery_fee_brl": "taxa de entrega paga pelo cliente (r$)"}.items():
                    value = _as_number(get(source))
                    if value is None:
                        raise ValueError("Um pedido do recorte iFood não possui o valor necessário.")
                    bucket[target] += value
            product = get("nome do item")
            units = _as_number(get("vendas total (quantidade)"))
            if product and units is not None:
                products.append({"product_name": str(product).strip(), "visits": _as_number(get("visitas")), "orders": _as_number(get("pedidos")), "units_sold": units, "reported_value_brl": _as_number(get("valor total"))})
    finally:
        workbook.close()
    frame = pd.DataFrame.from_records([{"order_date": day, "order_status": status, **values} for (day,status),values in sorted(daily.items())], columns=["order_date", "order_status", "orders", "items_value_brl", "customer_paid_brl", "delivery_fee_brl"])
    product_frame = pd.DataFrame.from_records(products, columns=["product_name", "visits", "orders", "units_sold", "reported_value_brl"])
    if product_frame["product_name"].duplicated().any():
        raise ValueError("Há produtos repetidos no recorte iFood; revisar antes de somar.")
    return frame, product_frame, {"available": True, "order_rows": int(frame["orders"].sum()), "product_rows": len(product_frame), "order_first_date": str(frame["order_date"].min()), "order_last_date": str(frame["order_date"].max()), "product_period": "não informado na tabela de produtos", "deduplication_limit": "A aba fornecida não traz ID de pedido; repetição exata de data/valor não foi interpretada como duplicidade."}
