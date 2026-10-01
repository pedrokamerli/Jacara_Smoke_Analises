# Jacaré Smoke House — Analytics

Estou desenvolvendo este projeto com dados reais de uma hamburgueria de Bauru/SP para demonstrar análise de negócios, engenharia analítica e avaliação de machine learning. Uso a metodologia CRISP-DM para ligar cada transformação a uma pergunta e registrar o que os dados permitem concluir.

Separei o ambiente **real e confidencial** da **demo pública**. As fontes originais e o segredo de pseudonimização ficam locais. A área privada na VPS recebe somente um snapshot analítico minimizado, protegido por login Google e lista de contas autorizadas. A demo usa dados sintéticos independentes, gerados com semente fixa e processados pela mesma stack; não representa o desempenho da hamburgueria. Ela inclui respostas, gráficos e ML treinado separadamente.

## Stack e decisões

| Tecnologia | Aplicação |
|---|---|
| Python, pandas, openpyxl | Ingestão de Excel/CSV, validação e minimização |
| Parquet | Dados analíticos com tipos definidos |
| DuckDB | Banco SQL local para consultar e reconciliar os dados |
| dbt Core + dbt-duckdb | Staging, marts, documentação e testes de qualidade |
| scikit-learn | Random Forest, Extra Trees, Hist Gradient Boosting e Ridge; avaliação temporal |
| Streamlit | Dashboard, filtros e importação de fontes reais |
| Docker + Compose + Nginx | Serviços público e privado separados, HTTPS e volumes somente leitura |
| Google OIDC + Streamlit/Authlib | Autenticação e autorização da área confidencial |
| Git + GitHub | Versionamento do código e documentação; dados reais e segredos excluídos |

Escolhi DuckDB porque o volume disponível cabe na máquina local e permite reproduzir o trabalho com poucos serviços. Spark e PostgreSQL não são necessários para este escopo. A escolha de ferramentas acompanha a necessidade do projeto.

## Arquitetura

```text
Pasta extraída ou upload de ZIP / Excel / CSV
    → leitura em memória e contratos de fontes
    → Python: minimização, pseudonimização e Parquet
    → DuckDB + dbt build: staging, marts e testes
    → reconciliação dos totais contra a planilha original
    → 15 consultas SQL + avaliação de Machine Learning
    → publicação da geração validada no dashboard local
```

Cada atualização usa uma pasta própria em `data/runs/`. A aplicação só troca para a nova geração quando preparação, dbt, auditoria e ML terminam. Se uma etapa falhar, a geração anterior continua ativa. `data/current_run.json` registra qual geração está publicada, seus artefatos e as fontes utilizadas.

## CRISP-DM

| Fase | Implementação e evidência |
|---|---|
| 1. Entendimento do negócio | Perguntas, métricas e limites em [docs/01_crisp_dm.md](docs/01_crisp_dm.md) |
| 2. Entendimento dos dados | Inventário de schemas, cobertura, granularidade e sobreposição em [docs/02_entendimento_dos_dados.md](docs/02_entendimento_dos_dados.md) |
| 3. Preparação | Leitura de fontes oficiais e Parquet minimizado em `prepare_extracted.py` |
| 4. Modelagem | Modelos SQL/dbt em `warehouse/`; quatro algoritmos e dois baselines em `forecast_backtest.py` |
| 5. Avaliação | Testes dbt, reconciliação independente com a fonte e backtest cronológico |
| 6. Implantação | CLI e dashboard executam o mesmo pipeline; geração atual registrada em manifesto |

A implementação técnica não encerra todas as validações de negócio. O horário atual foi confirmado: terça a domingo, 18h30–23h, no fuso de São Paulo. Exceções históricas, significado de algumas métricas sociais e identidade de pedidos entre plataformas continuam documentados como pendentes. O projeto consegue analisá-los sem inventar observações.

## Perguntas de negócio

1. Qual foi o valor recebido e quantos pedidos pagos foram registrados?
2. Como valor recebido, pedidos e ticket médio evoluíram ao longo do tempo?
3. Quais foram os dias com maior e menor valor recebido e volume de pedidos?
4. Qual foi a melhor e a menor semana em valor registrado e volume?
5. Quais dias da semana e horários de abertura concentram mais vendas?
6. Qual é o ticket médio e como varia por canal e período?
7. Quais produtos e itens de combo lideram em unidades vendidas?
8. Quais produtos contribuem mais para o valor dos itens vendidos?
9. Quais itens têm menor volume observado?
10. Quais complementos aparecem com maior frequência?
11. Quais grupos de clientes têm maior frequência e valor acumulado, preservando suas identidades?
12. Quantos clientes identificáveis compraram mais de uma vez e qual a recorrência?
13. Como variam primeira observação, retorno mensal e tempo desde a última compra?
14. Como os canais MenuDino, iFood e o recorte do 99Food se apresentam, sem duplicar pedidos?
15. Como evoluem as métricas do Instagram e do Meta Ads e que associações descritivas têm com vendas?

As consultas estão em [sql/business](sql/business). Cada geração produz `analysis/analysis_report.md` e `analysis_results.json` com respostas agregadas e ressalvas. No dashboard, a tela **15 perguntas e respostas** apresenta cada resultado em linguagem simples, explica sua interpretação e permite conferir as tabelas e a consulta SQL. As narrativas são calculadas sobre os resultados da geração ativa, sem números fixos. O relatório pode ser baixado nessa tela e em **Metodologia**. A cobertura de cada pergunta está em [docs/07_perguntas_e_evidencias.md](docs/07_perguntas_e_evidencias.md).

Produtos de menor volume não são classificados como menos rentáveis. Sem CMV e despesas completas, não calculo lucro. Componentes de combos não são interpretados como contagem de combos completos. Clientes são apresentados em grupos, sem nomes ou rankings individuais.

## Fontes utilizadas

- Pedidos e histórico de itens consolidados do PDV.
- MenuDino e iFood como origens registradas no PDV.
- AppDelivery como fonte própria, reconciliada com o canal MenuDino.
- Exportação de pedidos do 99Food.
- Aba `iFood_App` do relatório fornecido: pedidos e indicadores de produtos em recortes próprios.
- Seis séries exportadas do Instagram.
- Relatório atualizado do Meta Ads, usando apenas detalhamento diário de anúncios.

Os snapshots antigos e tabelas derivadas com informações pessoais não são concatenados à base consolidada. O recorte iFood_App e AppDelivery também não são adicionados ao faturamento do PDV. Os contratos atuais de importação, granularidade e campos estão em [docs/06_dicionario_de_dados.md](docs/06_dicionario_de_dados.md).

## Machine Learning

Comparei Random Forest, Extra Trees, Hist Gradient Boosting e Ridge para pedidos pagos e valor recebido. Todos usam calendário, lags e médias passadas, sem dados pessoais. As referências são o mesmo dia da semana anterior e a média recente de sete dias.

Escolho o algoritmo nas seis primeiras janelas cronológicas e congelo a escolha antes das duas semanas finais. Todos os métodos são pontuados nas mesmas datas observadas e comparáveis. Datas sem registros mantêm o alvo ausente; a mediana preenche somente features e é aprendida no treino. Segundas-feiras recebem zero apenas na estimativa de fechamento planejado, nunca no histórico observado.

O painel compara os seis métodos, separa seleção de teste final, explica MAE/WAPE e permite escolher linhas no gráfico e horizonte de 7 ou 14 dias. Também mostra faixas exploratórias, fechamento planejado e download das estimativas. O backtest avalia sete dias; os dias 8–14 são uma extensão recursiva ainda sem validação própria. Com a fonte até 19/08, as estimativas vão de 20/08 a 02/09/2026: não são previsões para a semana atual.

Incluí a projeção experimental de setembro inteiro: o modelo atravessa os 12 dias restantes de agosto antes de estimar 01–30/09, totalizando 42 passos desde a origem. O painel mostra total e linha diária projetados, separados do realizado, sem intervalo mensal de confiança inventado. Esse horizonte não foi validado pelo backtest semanal. Ao atualizar a fonte, o mês projetado muda para o primeiro mês completo seguinte. A evolução mensal das vendas reais usa gráfico de linha, com alerta para meses parciais.

Os resultados de seleção e erro do negócio ficam privados. Na demo, os resultados são recalculados sobre a base sintética e não servem como evidência de desempenho no cliente. Não chamo WAPE de taxa de acerto. Regras em [docs/04_previsao_demanda.md](docs/04_previsao_demanda.md).

Expliquei no dashboard como o modelo aprende, como o teste esconde semanas do passado e como interpretar o erro nas unidades do negócio (pedidos ou reais por dia). WAPE não é chamado de taxa de acerto. As demais telas têm legendas, definições dos indicadores e cuidados com comparações. A metodologia também conta a história do projeto e o papel de cada ferramenta para quem não conhece a stack.

## Executar no PyCharm ou terminal

Use Python 3.11 ou superior. No terminal, com `.venv` ativo:

```powershell
python -m pip install -r requirements.txt
python -m pip install -e .
python -m jacare_analytics.pipeline --source-root .
$env:JACARE_PUBLIC_MODE = 'false'
python -m streamlit run app/streamlit_app.py --server.port 8501 --server.address 127.0.0.1
```

O pipeline cria o perfil local do dbt a partir do exemplo se necessário e desativa a telemetria do dbt na execução. Abra [o dashboard local](http://127.0.0.1:8501/).

Também disponibilizei:

```powershell
.\scripts\run_project.ps1 -Mode Demo -Port 8502
# Para trabalhar com os dados reais locais:
.\scripts\run_project.ps1 -Mode Real -Refresh -Port 8501
```

Para abrir o privado sem reprocessar, use `-Mode Real` sem `-Refresh`. O padrão do lançador é Demo. Sem `JACARE_PUBLIC_MODE=false`, o aplicativo abre somente `demo/public`, nunca a geração real. Para gerar uma nova demo: `python -m jacare_analytics.demo`; a versão padrão existente é preservada para revisão.

## Atualização pelo dashboard

Na VPS privada, na tela **Atualizar dados**, envie ZIPs ou arquivos oficiais com o histórico consolidado completo, informe a última data completa e confirme o envio. Todas as contas Google autorizadas podem importar. Um worker isolado processa a fila, executa SQL/dbt, auditoria e Machine Learning e publica uma nova geração somente após aprovação. Se uma etapa falhar, a base anterior permanece ativa. ZIPs são lidos sem extração indiscriminada. Visitantes da versão pública não têm importação, caminhos locais ou treinamento de modelos.

A importação atual substitui o pacote consolidado validado; não faz merge automático de meses separados. Para atualizar setembro, é necessário enviar janeiro a setembro nos formatos documentados. As previsões anteriores ficam arquivadas para comparação com o realizado. O passo a passo e os limites estão em [docs/14_upload_privado.md](docs/14_upload_privado.md).

O importador atual aceita os exports documentados no dicionário. Versões conflitantes de uma fonte geram erro. Não reutilizo silenciosamente métricas de uma importação anterior para completar uma fonte faltante. Meta Ads e a aba adicional iFood_App são opcionais; o conjunto principal de vendas, delivery e seis séries sociais é necessário nesta versão.

## Qualidade e privacidade

- Unicidade de pedidos e relação de itens com pedidos.
- Presença de valores recebidos em pedidos pagos.
- Igualdade de contagem e soma recebida entre arquivo original, preparação e marts.
- Alvos nulos em datas sem registro, sem preenchimento com venda zero.
- Unicidade das datas das séries sociais e de marketing.
- Validação do formato HMAC e allowlist de campos analíticos.
- Reconciliação do gasto diário de Meta Ads com o total geral da exportação.
- Indicadores por cliente somente agregados; grupos pequenos omitidos nas consultas destinadas à apresentação.

O segredo HMAC é criado localmente em `data/private/hmac.key` ou fornecido por `JACARE_ANALYTICS_HMAC_KEY`. As chaves pseudonimizadas continuam protegidas, não são exibidas e não devem ser publicadas. A política está em [docs/03_privacidade_lgpd.md](docs/03_privacidade_lgpd.md).

Execute `python -m unittest discover -s tests -v`. Integrações reais são ignoradas quando a geração privada não existe. Os testes da demo usam exclusivamente dados sintéticos identificados. A auditoria pública não contém resultados comerciais; originais ficam privados.

## Publicação e operação

Preparei serviços Docker/Compose separados para demo e área privada. A imagem pública não monta dados reais, e o exportador público recusa gerações reais, mesmo com o antigo sinalizador de aprovação. Apenas quatro arquivos sintéticos integram o pacote público, com hashes e allowlists. A imagem privada também não incorpora dados nem credenciais: recebe volumes somente leitura. Seu banco é um snapshot materializado dos modelos dbt, sem views dependentes de caminhos Windows ou arquivos Parquet externos.

A [demo sintética pública](https://analisejacare.pedromerli.com) foi publicada com Docker/Nginx e HTTPS. A [área privada](https://jacare.pedromerli.com) exige login Google e autorização explícita; foram confirmados acesso permitido e negação de outra conta. O servidor de apresentação monta a base somente para leitura e recebe uploads em uma fila privada. Um worker separado, sem acesso à rede, valida e processa as atualizações. Dados reais, credenciais, chaves e PDFs pessoais ficam fora do Git e das imagens Docker. Registros em [docs/11_demo_publicada.md](docs/11_demo_publicada.md), [docs/12_login_privado_homologacao.md](docs/12_login_privado_homologacao.md) e [docs/14_upload_privado.md](docs/14_upload_privado.md). Power BI permanece uma próxima entrega.

## Organização

```text
app/                    aplicação Streamlit
src/jacare_analytics/    ingestão, preparação, auditoria, respostas SQL e ML
warehouse/              modelos, testes e documentação dbt
sql/business/           15 consultas de negócio
docs/                   CRISP-DM, fontes, privacidade e decisões
scripts/                execução local
data/                   gerações e segredos locais, ignorados pelo Git
```

## Autor

Sou Pedro. Estou usando este caso real para praticar Python, SQL, engenharia analítica e machine learning com decisões rastreáveis, resultados verificáveis e limites documentados.
