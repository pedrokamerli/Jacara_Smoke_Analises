"""Leitura guiada do experimento; não altera dados, modelos ou previsões salvas."""
from datetime import date
import json
import pandas as pd
import streamlit as st
from .business_calendar import freshness
from .forecast_archive import render_comparison


def render_ml_story(runtime, manifest, money, table, monthly, audit):
    metrics = json.loads(runtime.resolve_artifact(manifest['forecast_metrics']).read_text(encoding='utf-8'))
    if metrics.get('schema_version') != 4 or metrics.get('series_sha256') != manifest.get('series_sha256'):
        st.error('O experimento não corresponde à geração ativa. Atualize os dados.')
        return
    st.write('**A pergunta do negócio:** quanto movimento podemos esperar, e quanto confiar nessa estimativa?')
    st.caption('Leia nesta ordem: conferir a previsão preservada → entender o erro → explorar o futuro. O modelo não compra estoque nem toma decisões sozinho.')
    target = st.selectbox('O que prever', ['paid_orders', 'total_received_brl'], key='ml_target', format_func=lambda x: {'paid_orders':'Pedidos pagos por dia', 'total_received_brl':'Valor recebido por dia (R$)'}[x])
    result = metrics['targets'][target]
    model = result['selected_model']
    label = metrics['model_labels'][model]
    fmt = money if target == 'total_received_brl' else lambda x: f'{x:.2f}'.replace('.', ',')+' pedidos'
    st.info(f"Dados para aprender: {pd.Timestamp(metrics['source_start']):%d/%m/%Y} a {pd.Timestamp(metrics['source_end']):%d/%m/%Y}. {metrics['observed_target_days']} dias observados; {metrics['missing_target_days']} datas sem alvo. Não inventamos vendas nessas lacunas.")
    past, evaluation, future, technical = st.tabs(['1 · Previsão × realidade', '2 · O modelo foi útil?', '3 · Próximos dias e mês', '4 · Como foi construído'])
    with past:
        st.subheader('Primeiro, confira o que a previsão preservada estimou')
        if runtime.public_mode:
            st.info('Esta demo usa dados sintéticos. A comparação com os novos arquivos do cliente existe somente no ambiente privado; resultados fictícios não demonstram desempenho no negócio real.')
        else:
            render_comparison(runtime, manifest)
            st.caption('Se não houver uma previsão arquivada, envie uma atualização posterior à origem atual para criar uma comparação. Nunca recalculamos uma previsão antiga com dados novos para fazê-la parecer melhor.')
        st.write('**Como interpretar:** uma previsão pode acertar o total e errar muito os dias. Por isso mostramos tanto os desvios diários quanto a diferença acumulada. Esses resultados não explicam a causa de uma alta ou queda.')
    with evaluation:
        st.subheader(f'{label}: como se saiu nas semanas reservadas?')
        final = result['candidate_models'][model]['holdout']
        cols = st.columns(3)
        cols[0].metric('Erro médio diário — teste final', fmt(final['mae']), help='MAE: distância média do realizado; menor é melhor. Não é o erro máximo.')
        cols[1].metric('WAPE — teste final', f"{final['wape']:.1%}" if final['wape'] is not None else 'Não calculável', help='Soma dos erros absolutos dividida pelo realizado. Não é taxa de acerto.')
        cols[2].metric('Dias comparáveis — teste final', result['holdout_comparable_days'])
        baselines = ['seasonal_naive', 'moving_average_7d']
        beaten = sum(final['mae'] < result['candidate_models'][b]['holdout']['mae'] for b in baselines)
        st.write(f"**O que aprendemos:** o algoritmo escolhido teve menos erro que {beaten} das duas regras simples no teste final. Em média, ficou {fmt(final['mae'])} distante do realizado por dia; pode errar para cima ou para baixo.")
        st.caption(f"Escolha feita nas {result['selection_folds']} primeiras janelas e congelada antes de {result['holdout_start']}. As duas janelas finais avaliam a escolha; não usamos seu ranking para trocar de algoritmo.")
        labels = {**metrics['model_labels'], 'seasonal_naive':'Semana anterior', 'moving_average_7d':'Média recente'}
        scores = pd.DataFrame([{'Método':labels[name], 'Erro médio diário':entry['holdout']['mae'], 'Papel':'Escolhido antes do teste' if name == model else 'Referência' if name in baselines else 'Candidato'} for name, entry in result['candidate_models'].items()]).sort_values('Erro médio diário')
        st.bar_chart(scores.set_index('Método')[['Erro médio diário']], horizontal=True, color='#1674d1')
        st.caption('Barras menores = menor erro. A unidade é a do indicador escolhido, não um percentual. Um candidato melhor aqui não substitui retroativamente o modelo escolhido.')
        scope = st.radio('Quais semanas comparar no gráfico?', ['Teste final reservado', 'Todas as janelas (inclui seleção)'], horizontal=True, key='story_backtest_scope')
        rows = pd.DataFrame(result['backtest_predictions'])
        rows = rows.loc[rows.stage.eq('holdout')] if scope == 'Teste final reservado' else rows
        rows.loc[~rows.comparable, ['actual', model, 'seasonal_naive']] = float('nan')
        chart = rows.set_index(pd.to_datetime(rows.date))[['actual', model, 'seasonal_naive']].rename(columns={'actual':'Realizado', model:'Estimativa escolhida', 'seasonal_naive':'Semana anterior'})
        st.line_chart(chart, color=['#159c94', '#1674d1', '#d58b32'])
        st.caption('Verde = realizado; azul = estimativa; laranja = regra simples. Compare as linhas na mesma data. Lacunas não representam zero. Todos os métodos são pontuados nos mesmos dias conhecidos.')
        st.warning('Uso experimental, não aprovado para decisões automáticas. Mesmo um critério estatístico atingido não elimina falhas de captura, eventos inesperados ou a necessidade de validação com o proprietário.')
        with st.expander('Conferir o ranking e o significado de MAE e WAPE'):
            table(scores)
            st.write('MAE mede o tamanho médio do erro diário. WAPE soma o erro absoluto diário e divide pelo total realizado. Viés mede a tendência de estimar acima ou abaixo. Nenhum deles equivale a uma porcentagem de “acerto”.')
    with future:
        st.subheader('O futuro é uma hipótese, não uma venda registrada')
        current = freshness(date.fromisoformat(metrics['source_end']), metrics['calendar'])
        if not current['supports_current_week']:
            st.warning('O histórico está desatualizado para a semana atual. As estimativas abaixo começam depois da última data da fonte, não depois de hoje.')
        horizon = st.radio('Horizonte da estimativa', [7, 14], key='ml_horizon', format_func=lambda x: f'{x} dias', horizontal=True)
        rows = pd.DataFrame(result['experimental_forecast'][:horizon])
        chart = rows.set_index(pd.to_datetime(rows.date))[['prediction', 'residual_band_low', 'residual_band_high']].rename(columns={'prediction':'Estimativa', 'residual_band_low':'Faixa exploratória inferior', 'residual_band_high':'Faixa exploratória superior'})
        st.line_chart(chart)
        st.caption(f"Estimativas após {metrics['source_end']}. O teste valida sete dias; a segunda semana não tem validação própria. Faixas baseadas em apenas {result['residual_band_sample_size']} erros finais: não são intervalos calibrados nem garantia de cobertura.")
        st.caption('Terça a domingo, 18h30–23h. Segunda futura recebe zero por fechamento planejado; isso não preenche lacunas históricas. Pedidos fracionários são expectativas médias.')
        with st.expander('Consultar e baixar estimativas diárias'):
            display=rows.rename(columns={'date':'Data', 'prediction':'Estimativa do modelo', 'residual_band_low':'Faixa exploratória: de', 'residual_band_high':'Faixa exploratória: até'})
            display['Situação']=display['scheduled_open'].map({True:'Funcionamento previsto',False:'Fechamento planejado'})
            display=display.drop(columns=['scheduled_open','prediction_origin'])
            table(display, currency_fields=('Estimativa do modelo','Faixa exploratória: de','Faixa exploratória: até') if target=='total_received_brl' else ())
            st.download_button('Baixar estimativas agregadas (CSV)', display.to_csv(index=False).encode('utf-8-sig'), file_name=f'jacare_estimativas_{target}_{horizon}d.csv', mime='text/csv')
        monthly(metrics, target)
    with technical:
        st.subheader('Da pergunta à entrega: CRISP-DM')
        st.write('Negócio: antecipar demanda. Dados: conferir cobertura e definições. Preparação: construir a série sem inventar alvos. Modelagem: testar algoritmos e regras simples. Avaliação: simular semanas posteriores ao treino. Implantação: salvar a geração validada e preservar previsões antigas.')
        st.write('O modelo recebe calendário, vendas anteriores e médias recentes. Não recebe nomes, telefones ou endereços. Não conhece promoções, clima ou eventos que não estejam nas fontes; associação não demonstra causa.')
        study = metrics.get('development_study')
        if study:
            st.subheader('Pesquisa de melhoria: novos sinais de calendário')
            st.write(study['policy'])
            table(pd.DataFrame(study['targets'][target]['summary']))
            st.caption(study['targets'][target]['conclusion'])
        with st.expander('Auditoria completa: candidatos, semanas, critérios e sinais'):
            audit(manifest, target=target)
