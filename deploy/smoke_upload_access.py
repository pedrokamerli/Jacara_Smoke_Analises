"""Valida política e interface em processo de teste; não cria sessões no servidor."""
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import streamlit as st
from streamlit.testing.v1 import AppTest

assert st.secrets["access"]["uploads_for_all_allowed"] is True
assert not Path("/worker-secrets/hmac.key").exists(),"HMAC não pode estar no dashboard"
for email in st.secrets["access"]["allowed_emails"]:
    now=time.time()
    claims={"iss":"https://accounts.google.com","sub":"qa-policy-only","email":email,"email_verified":True,"iat":now-1,"exp":now+1800}
    with patch("streamlit.user",SimpleNamespace(is_logged_in=True,to_dict=lambda:claims)):
        app=AppTest.from_file("/app/app/streamlit_app.py",default_timeout=60).run()
        assert not app.exception and not app.error
        assert "Atualizar dados" in app.sidebar.radio[0].options
        app.sidebar.radio[0].set_value("Atualizar dados").run()
        assert not app.exception and not app.error
        assert app.get("file_uploader") and not app.text_input
        assert next(x for x in app.button if x.label=="Enviar e processar atualização").disabled
now=time.time()
outsider={"iss":"https://accounts.google.com","sub":"qa-outsider","email":"not-authorized@example.invalid","email_verified":True,"iat":now-1,"exp":now+1800}
with patch("streamlit.user",SimpleNamespace(is_logged_in=True,to_dict=lambda:outsider)),patch("duckdb.connect",side_effect=AssertionError("Conta não autorizada abriu banco")):
    app=AppTest.from_file("/app/app/streamlit_app.py",default_timeout=60).run()
    assert not app.exception and app.error and not app.sidebar.radio and not app.get("file_uploader")
print("Política validada para todas as contas permitidas: upload visível, envio sem arquivos bloqueado, pasta do servidor não exposta e conta externa negada. Sem contas/credenciais nos logs.")
