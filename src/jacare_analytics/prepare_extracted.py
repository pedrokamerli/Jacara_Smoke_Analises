"""Prepara fontes reais oficiais com contratos explícitos e rastreabilidade."""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from .prepare_delivery_sources import _prepare_99food, _prepare_appdelivery
from .prepare_marketing import prepare_meta_ads
from .prepare_ifood import prepare_ifood
from .prepare_social_sources import METRIC_PREFIXES, _read_metric
from .prepare_sources import _build_items, _build_orders
from .privacy import local_secret
from .profile_sales import _read_orders
from .source_files import SourceFile, collect_local

CUTOFF = date(2026, 8, 19)


def prepare_bundle(bundle: dict[str, SourceFile], output_dir: Path, private_dir: Path, cutoff: date = CUTOFF) -> dict[str, Any]:
    required = {"orders", "items"}
    missing = required - bundle.keys()
    if missing:
        raise ValueError("Fontes necessárias ausentes: " + ", ".join(sorted(missing)))
    secret = local_secret(private_dir)
    orders, order_metadata, order_map = _build_orders(bundle["orders"].payload, cutoff, secret)
    items, item_metadata = _build_items(bundle["items"].payload, order_map, cutoff)
    if orders.empty or items.empty:
        raise ValueError("A fonte oficial de pedidos ou de itens está vazia após o corte.")
    paid = orders.loc[orders["order_status"].eq("paid")].copy()
    if paid.empty or paid["amount_received_brl"].isna().any():
        raise ValueError("Há pedidos pagos sem valor recebido ou nenhum pedido pago disponível.")
    if 'appdelivery' in bundle:
        appdelivery, app_metadata = _prepare_appdelivery(bundle['appdelivery'].payload)
    else:
        appdelivery=pd.DataFrame(columns=['order_date','delivery_type','order_status','orders','items_value_brl','delivery_fee_brl'])
        app_metadata={'appdelivery_available':False}
    if 'food99' in bundle:
        food99, food_metadata = _prepare_99food(bundle['food99'].payload)
    else:
        counts=['orders','orders_with_completion_timestamp','orders_with_cancellation_timestamp','orders_with_both_timestamps','late_preparation_orders','items_count','rating_count','rating_sum']
        amounts=['sales_revenue','shop_revenue','offer_expenses','commission_expense','payment_channel_fee','platform_rewards','original_delivery_fee','new_customer_delivery_fee','refund','free_delivery_net_cost','logistics_cost']
        durations=[field+'_'+suffix for field in ['prep_minutes','acceptance_seconds','finalization_seconds','delivery_seconds'] for suffix in ['sum','count']]
        food99=pd.DataFrame(columns=['order_date']+counts+[field+'_brl' for field in amounts]+durations)
        food_metadata={'99food_available':False}
    app_metadata["appdelivery_records_after_cutoff"] = int(appdelivery.loc[appdelivery["order_date"] > cutoff, "orders"].sum())
    food_metadata["99food_records_after_cutoff"] = int(food99.loc[food99["order_date"] > cutoff, "orders"].sum())
    appdelivery = appdelivery.loc[appdelivery["order_date"] <= cutoff]
    food99 = food99.loc[food99["order_date"] <= cutoff]
    records = []
    for metric in METRIC_PREFIXES:
        source = bundle.get(f"instagram_{metric}")
        if source: records.extend(_read_metric(source.payload, source.name, metric))
    instagram = pd.DataFrame.from_records(records,columns=['metric_date','metric_key','source_label','metric_value'])
    instagram = instagram.loc[instagram["metric_date"] <= cutoff]
    marketing_report: dict[str, Any] = {"available": "meta_ads" in bundle}
    if "meta_ads" in bundle:
        meta_ads, metadata = prepare_meta_ads(bundle["meta_ads"].payload, cutoff)
        marketing_report.update(metadata)
    else:
        meta_ads = pd.DataFrame({"metric_date": pd.Series(dtype="datetime64[ns]"), "spend_brl": pd.Series(dtype=float), "impressions": pd.Series(dtype=float), "link_clicks": pd.Series(dtype=float), "link_clicks_observed_rows":pd.Series(dtype=int), "link_clicks_missing_rows":pd.Series(dtype=int)})
    if "ifood_report" in bundle:
        ifood, ifood_products, ifood_report = prepare_ifood(bundle["ifood_report"].payload, cutoff)
    else:
        ifood = pd.DataFrame({"order_date": pd.Series(dtype="datetime64[ns]"), "order_status": pd.Series(dtype=str), "orders": pd.Series(dtype=int), "items_value_brl": pd.Series(dtype=float), "customer_paid_brl": pd.Series(dtype=float), "delivery_fee_brl": pd.Series(dtype=float)})
        ifood_products = pd.DataFrame({"product_name": pd.Series(dtype=str), "visits": pd.Series(dtype=float), "orders": pd.Series(dtype=float), "units_sold": pd.Series(dtype=float), "reported_value_brl": pd.Series(dtype=float)})
        ifood_report = {"available": False}
    paid["date"] = pd.to_datetime(paid["opened_at"]).dt.date
    daily = paid.groupby("date").agg(paid_orders=("order_key", "nunique"), total_received_brl=("amount_received_brl", "sum"))
    first = pd.to_datetime(orders["opened_at"]).min().date()
    last = pd.to_datetime(orders["opened_at"]).max().date()
    calendar = pd.DataFrame({"date": pd.date_range(first, last).date}).set_index("date")
    daily = calendar.join(daily)
    captured_dates = set(pd.to_datetime(orders["opened_at"]).dt.date)
    daily["has_source_records"] = [day in captured_dates for day in daily.index]
    # Dias sem qualquer registro ficam ausentes; não se inventa venda zero.
    observed_without_paid = daily["has_source_records"] & daily["paid_orders"].isna()
    daily.loc[observed_without_paid, ["paid_orders", "total_received_brl"]] = 0
    daily["total_received_brl"] = daily["total_received_brl"].round(2)
    output_dir.mkdir(parents=True, exist_ok=True)
    customer_report={'available':False}
    if 'customers' in bundle:
        from .customer_directory import prepare_customer_directory
        directory,customer_report=prepare_customer_directory(bundle['customers'].payload,secret)
        directory.to_parquet(output_dir/'customer_directory.parquet',index=False)
    for name, frame in {
        "orders": orders, "items": items, "appdelivery_daily": appdelivery,
        "food99_daily": food99, "instagram_daily": instagram, "meta_ads_daily": meta_ads,
        "ifood_daily": ifood, "ifood_products": ifood_products,
    }.items():
        frame.to_parquet(output_dir / f"{name}.parquet", index=False)
    daily.to_csv(output_dir / "daily_sales_ml.csv", index_label="date")
    raw_profile = _read_orders(bundle["orders"].payload, cutoff)
    report = {
        "cutoff": cutoff.isoformat(), "source_start": first.isoformat(), "source_end": last.isoformat(),
        "sources": {key: {"file": source.name, "sha256": source.sha256} for key, source in bundle.items()},
        "customer_pseudonymization_enabled": True,
        "expected_paid_orders": int(paid["order_key"].nunique()),
        "expected_received_brl": round(float(paid["amount_received_brl"].sum()), 2),
        "raw_paid_rows": raw_profile["paid_rows_through_cutoff"],
        "raw_received_brl": round(raw_profile["paid_total_received_through_cutoff"], 2),
        "calendar_days_without_records": int((~daily["has_source_records"]).sum()),
        "missing_fields": {
            "orders": {key: int(value) for key,value in orders.isna().sum().items()},
            "items": {key: int(value) for key,value in items.isna().sum().items()},
        },
        "marketing": marketing_report,
        "customers":customer_report,
        "source_availability":{key:key in bundle for key in ['orders','items','appdelivery','food99','ifood_report','meta_ads',*[f'instagram_{metric}' for metric in METRIC_PREFIXES],'customers']},
        "ifood": ifood_report,
        **order_metadata, **item_metadata, **app_metadata, **food_metadata,
    }
    (output_dir / "source_manifest.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def prepare_extracted(root: Path, output_dir: Path = Path("data/processed")) -> dict[str, Any]:
    return prepare_bundle(collect_local(root), output_dir, Path("data/private"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepara fontes reais extraídas sem expor identificadores.")
    parser.add_argument("root", nargs="?", type=Path, default=Path.cwd())
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed"))
    args = parser.parse_args()
    report = prepare_extracted(args.root, args.output_dir)
    print(f"Fontes reais preparadas: {report['orders_written']} pedidos, {report['items_written']} itens. Datas sem registro preservadas como ausentes.")


if __name__ == "__main__":
    main()
