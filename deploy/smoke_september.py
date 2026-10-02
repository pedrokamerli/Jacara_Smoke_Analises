"""QA de interface em processo isolado; não cria sessão ou muda dados de produção."""
import json,time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import streamlit as st
from streamlit.testing.v1 import AppTest

manifest=json.loads(Path('/app/data/current_run.json').read_text())
assert manifest['source_end']=='2026-09-30' and manifest['quality']['all_passed']
email=st.secrets['access']['allowed_emails'][0]
now=time.time()
claims={'iss':'https://accounts.google.com','sub':'qa-only-rendering','email':email,'email_verified':True,'iat':now-1,'exp':now+1800}
with patch('streamlit.user',SimpleNamespace(is_logged_in=True,to_dict=lambda:claims)):
    app=AppTest.from_file('/app/app/streamlit_app.py',default_timeout=60).run()
    assert not app.exception and not app.error
    initial=next(x.value for x in app.metric if x.label=='Pedidos pagos')
    app.selectbox(key='sales_preset').set_value('Mês específico').run()
    assert app.selectbox(key='sales_month').value=='2026-09'
    assert not app.exception and next(x.value for x in app.metric if x.label=='Pedidos pagos')!=initial
    for page in app.sidebar.radio[0].options:
        app.sidebar.radio[0].set_value(page).run()
        assert not app.exception and not app.error,'Falha na página '+page
        if page=='Clientes':
            frame=next(x.value for x in app.dataframe if 'Cliente' in x.value.columns)
            assert not frame.empty and not any('key' in str(x).lower() or 'telefone' in str(x).lower() for x in frame.columns)
            app.selectbox(key='named_customer_rank').set_value('Quantidade de compras').run()
            frame=next(x.value for x in app.dataframe if 'Cliente' in x.value.columns)
            assert frame['Compras no recorte'].is_monotonic_decreasing
            app.checkbox(key='named_recurring_only').check().run()
            frame=next(x.value for x in app.dataframe if 'Cliente' in x.value.columns)
            assert (frame['Compras no recorte']>=2).all()
            app.text_input(key='named_customer_search').set_value('nome-inexistente-teste').run()
            frame=next(x.value for x in app.dataframe if 'Cliente' in x.value.columns)
            assert frame.empty
        if page=='Machine Learning':
            assert any(x.label=='Erro percentual ponderado (WAPE)' for x in app.metric)
            app.selectbox(key='frozen_forecast_target').set_value('total_received_brl').run()
            assert not app.exception and any(x.label=='Viés do total previsto' for x in app.metric)
        if page=='Atualizar dados':
            assert app.get('file_uploader')
            assert next(x for x in app.button if x.label=='Enviar e processar atualização').disabled
        print('Página validada: '+page)
with patch('streamlit.user',SimpleNamespace(is_logged_in=True,to_dict=lambda:{})),patch('duckdb.connect',side_effect=AssertionError('Acesso sem autorização')):
    app=AppTest.from_file('/app/app/streamlit_app.py',default_timeout=60).run()
    assert app.error and not app.metric and not app.dataframe and not app.sidebar.radio
print('Setembro, filtros, rankings privados, ML e negação de acesso conferidos; nenhum nome ou resultado comercial impresso.')
