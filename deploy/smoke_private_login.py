"""Teste de sessão anônima no serviço privado; não imprime identidade/segredos."""
from unittest.mock import patch
from pathlib import Path
from streamlit.testing.v1 import AppTest
import urllib.request
from urllib.parse import urlparse, parse_qs
import httpx
from authlib.integrations import starlette_client
from streamlit.auth_util import encode_provider_token

# Após homologação humana, repetir este bloqueio mesmo com o volume real montado.
with patch("duckdb.connect", side_effect=AssertionError("Anônimo não pode abrir o banco")):
    app = AppTest.from_file("/app/app/streamlit_app.py", default_timeout=60).run()
    assert not app.exception, "Falha na tela privada"
    assert not app.error, "Configuração de login incompleta"
    assert any(button.label == "Entrar com Google" for button in app.button)
    assert not app.metric and not app.sidebar.radio
    assert not app.get("download_button") and not app.get("file_uploader")
with urllib.request.urlopen("https://accounts.google.com/.well-known/openid-configuration", timeout=15) as response:
    assert response.status == 200
print("Sessão anônima bloqueada: apenas botão Google, sem banco, métricas, downloads ou upload. Provedor acessível.")
with httpx.Client(follow_redirects=False, timeout=20) as client:
    response = client.get("https://jacare.pedromerli.com/auth/login", params={"provider":encode_provider_token("default")})
    assert response.status_code in (302, 303, 307), f"Rota de login retornou {response.status_code}"
    location = urlparse(response.headers.get("location", ""))
    assert location.scheme == "https" and location.hostname == "accounts.google.com"
    query = parse_qs(location.query)
    assert query.get("redirect_uri") == ["https://jacare.pedromerli.com/oauth2callback"]
    assert query.get("state") and query.get("nonce")
print("Rota de login validada: redireciona ao Google com callback, state e nonce corretos. Sem imprimir tokens ou credenciais.")
