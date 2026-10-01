"""QA privado: renderização autorizada simulada; não substitui login humano."""
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import duckdb
from streamlit.testing.v1 import AppTest

root = Path("/app")
manifest = json.loads((root / "data/current_run.json").read_text())
assert manifest["dataset_kind"] == "real_confidential"
assert manifest["quality"]["all_passed"] is True
with duckdb.connect(str(root / manifest["warehouse"]), read_only=True) as db:
    assert db.execute("select count(*) from information_schema.tables where table_schema='analytics' and table_type='VIEW'").fetchone()[0] == 0
    assert db.execute("select count(*) from analytics.stg_orders where order_status='paid'").fetchone()[0] == manifest["quality"]["paid_orders"]
# Identidade propositalmente inválida: não pode alcançar banco/manifesto/menus.
denied = SimpleNamespace(is_logged_in=True, to_dict=lambda: {})
with patch("streamlit.user", denied), patch("duckdb.connect", side_effect=AssertionError("Conta negada abriu banco")):
    app = AppTest.from_file(str(root / "app/streamlit_app.py"), default_timeout=60).run()
    assert not app.exception and app.error
    assert not app.metric and not app.sidebar.radio and not app.get("download_button")
print("Identidade inválida bloqueada antes de carregar análises, mesmo com dados instalados.")
# Mock restrito a este processo de testes: aplicação publicada conserva autenticação real.
with patch("jacare_analytics.authentication.enforce_private_access"):
    app = AppTest.from_file(str(root / "app/streamlit_app.py"), default_timeout=60).run()
    assert not app.exception and not app.error, "Erro na visão geral"
    initial_orders=next(x.value for x in app.metric if x.label=="Pedidos pagos")
    initial_charts=[x.proto.SerializeToString() for x in app.get("vega_lite_chart")]
    assert initial_charts
    app.selectbox(key="sales_preset").set_value("Mês específico").run()
    assert not app.exception and not app.error
    assert [x.proto.SerializeToString() for x in app.get("vega_lite_chart")]!=initial_charts
    app.multiselect(key="sales_channels").set_value([]).run()
    assert not app.exception and not app.metric and not app.get("vega_lite_chart")
    next(x for x in app.button if x.label=="Limpar filtros").click().run()
    assert not app.exception
    assert next(x.value for x in app.metric if x.label=="Pedidos pagos")==initial_orders
    print("Filtros de mês, seleção vazia e restauração validados em produção isolada.")
    pages = list(app.sidebar.radio[0].options)
    assert "Atualizar dados" not in pages
    for page in pages:
        app.sidebar.radio[0].set_value(page).run()
        assert not app.exception and not app.error, "Falha em " + page
        assert not app.get("file_uploader")
        print("Página validada: " + page)
print("Dashboard privado validado com snapshot real em somente leitura, sem imprimir resultados.")
