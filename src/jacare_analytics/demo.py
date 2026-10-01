"""Demo independente: não lê planilhas, estatísticas, modelos ou segredos reais.

Gerador v1, semente fixa 731. A mesma pipeline SQL/dbt/ML processa estes dados.
"""
from __future__ import annotations

import hashlib
import json
import random
import shutil
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]


def prepare_demo(output: Path) -> dict:
    rng = random.Random(731)
    orders, items = [], []
    dates = pd.date_range("2025-01-02", "2025-08-26")
    products = [("Burger Demo A", 24.0), ("Burger Demo B", 32.0), ("Batata Demo", 12.0), ("Bebida Demo", 7.0)]
    for day in dates:
        if day.weekday() == 0:
            continue
        volume = max(8, int(18 + day.dayofyear / 25 + (8 if day.weekday() >= 4 else 0) + rng.randint(-5, 5)))
        for _ in range(volume):
            key = len(orders) + 1
            opened = day.to_pydatetime().replace(hour=18, minute=30) + timedelta(minutes=rng.randrange(260))
            channel = rng.choice(["ifood", "menudino_app_site", "desktop", "comanda_mobile"])
            delivery = "delivery" if channel in {"ifood", "menudino_app_site"} else "retirada"
            amount = 0.0
            for product, price in rng.sample(products, rng.randint(1, 3)):
                quantity = rng.randint(1, 2)
                amount += quantity * price
                items.append(dict(order_key=key, sold_at=opened, quantity=quantity, unit_price_brl=price, line_total_brl=price*quantity, item_type="produto", product_name=product, product_type="demo", product_category="Categoria Demo", order_type="demo", order_status="paid"))
            fee = 5.0 if delivery == "delivery" else 0.0
            # Prefixo é somente o contrato de formato; não existe telefone na demo.
            customer = "phone_pos_" + hashlib.sha256(f"synthetic-customer-{rng.randrange(500)}".encode()).hexdigest()
            orders.append(dict(order_key=key, opened_at=opened, closed_at=opened+timedelta(minutes=25), order_status="paid", order_type="demo", source_channel=channel, delivery_type=delivery, items_amount_brl=amount, service_fee_brl=0.0, delivery_fee_brl=fee, order_total_brl=amount+fee, amount_received_brl=amount+fee, customer_key=customer))
    order_frame = pd.DataFrame(orders)
    order_frame["date"] = order_frame.opened_at.dt.date
    daily = order_frame.groupby("date").agg(paid_orders=("order_key", "size"), total_received_brl=("amount_received_brl", "sum"))
    series = pd.DataFrame(index=pd.Index(dates.date, name="date")).join(daily)
    series["has_source_records"] = series.paid_orders.notna()
    delivery_rows, ifood_rows, food_rows, social, ads = [], [], [], [], []
    for day, group in order_frame.groupby("date"):
        for channel, target in [("menudino_app_site", delivery_rows), ("ifood", ifood_rows)]:
            selected = group[group.source_channel == channel]
            target.append(dict(order_date=day, delivery_type="delivery", order_status="entregue" if channel != "ifood" else "concluido", orders=len(selected), items_value_brl=float(selected.items_amount_brl.sum()), customer_paid_brl=float(selected.amount_received_brl.sum()), delivery_fee_brl=float(selected.delivery_fee_brl.sum())))
        n = rng.randint(5, 15)
        revenue = float(n * 35)
        food_rows.append(dict(order_date=day, orders=n, orders_with_completion_timestamp=n, orders_with_cancellation_timestamp=0, orders_with_both_timestamps=0, late_preparation_orders=1, items_count=n*2, sales_revenue_brl=revenue, shop_revenue_brl=revenue*.8, offer_expenses_brl=0., commission_expense_brl=revenue*.2, payment_channel_fee_brl=0., platform_rewards_brl=0., original_delivery_fee_brl=n*5., new_customer_delivery_fee_brl=0., refund_brl=0., free_delivery_net_cost_brl=0., logistics_cost_brl=0., rating_count=n, rating_sum=n*4.5, prep_minutes_sum=n*20., prep_minutes_count=n, acceptance_seconds_sum=n*30., acceptance_seconds_count=n, finalization_seconds_sum=n*900., finalization_seconds_count=n, delivery_seconds_sum=n*600., delivery_seconds_count=n))
        for metric in ["reach", "views", "content_interactions", "profile_visits", "link_clicks", "followers"]:
            social.append(dict(metric_date=day, metric_key=metric, source_label="Gerador sintético v1", metric_value=float(rng.randint(50, 500))))
        ads.append(dict(metric_date=day, spend_brl=float(rng.randint(5, 20)), impressions=rng.randint(500, 2000), link_clicks=rng.randint(5, 50), link_clicks_observed_rows=1, link_clicks_missing_rows=0))
    frames = {"orders": order_frame.drop(columns="date"), "items": pd.DataFrame(items), "appdelivery_daily": pd.DataFrame(delivery_rows).drop(columns="customer_paid_brl"), "food99_daily": pd.DataFrame(food_rows), "instagram_daily": pd.DataFrame(social), "meta_ads_daily": pd.DataFrame(ads), "ifood_daily": pd.DataFrame(ifood_rows).drop(columns="delivery_type"), "ifood_products": pd.DataFrame([dict(product_name=p, visits=400., orders=100., units_sold=120., reported_value_brl=120*price) for p, price in products])}
    output.mkdir(parents=True, exist_ok=True)
    for name, frame in frames.items():
        frame.to_parquet(output / f"{name}.parquet", index=False)
    series.to_csv(output / "daily_sales_ml.csv")
    report = dict(dataset_kind="synthetic", generator="v1/seed731", source_start=str(dates[0].date()), source_end=str(dates[-1].date()), sources={}, expected_paid_orders=len(orders), expected_received_brl=float(order_frame.amount_received_brl.sum()), raw_paid_rows=len(orders), raw_received_brl=float(order_frame.amount_received_brl.sum()), calendar_days_without_records=int(series.paid_orders.isna().sum()), marketing={"available": True, "spend_reconciled": True})
    (output / "source_manifest.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def build_demo(root: Path = ROOT) -> Path:
    from .pipeline import run_pipeline
    from .export_public import export_public_snapshot
    # Copia somente contratos e SQL. Não copia dados, modelos nem manifestos reais.
    workspace = root / "data/demo/workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    for folder in ("warehouse", "sql", "config"):
        shutil.copytree(root / folder, workspace / folder, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("target", "logs", "dbt_packages", "profiles.yml", ".user.yml", "__pycache__"))
    run_pipeline({}, project_root=workspace, demo=True, progress=print)
    # Nova versão isolada, sem sobrescrever pacote anterior.
    manifest = json.loads((workspace / "data/current_run.json").read_text(encoding="utf-8"))
    destination = root / "demo" / manifest["run_id"]
    export_public_snapshot(destination, project_root=workspace, business_approval=True)
    public = root / "demo/public"
    if not public.exists():
        shutil.copytree(destination, public)
    else:
        print("Pacote padrão existente preservado; revise a nova versão antes de substituí-lo.")
    return destination


if __name__ == "__main__":
    print(f"DEMO SINTÉTICA gerada: {build_demo()}")
