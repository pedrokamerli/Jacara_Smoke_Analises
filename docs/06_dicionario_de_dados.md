# Contratos e dicionário de dados

## Fontes atuais aceitas

| Fonte lógica | Arquivo / seleção | Obrigatória |
|---|---|---|
| orders | `01_Todos_os_pedidos_01-01_a_20-08-2026.xlsx` | Sim |
| items | `02_Historico_Itens_Vendidos_01-01_a_20-08-2026.xlsx` | Sim |
| appdelivery | `Pedidos_AppDelivery_01-01_a_04-08-2026.xlsx` | Sim |
| food99 | `_Dados do pedido(01-07-2026_31-07-2026).xlsx` | Sim |
| instagram_* | CSVs com `insta` e prefixos de alcance, visualizações, interações, visitas, cliques no link e seguidores | Seis séries |
| meta_ads | `04_Relatorio_Meta_Atualizado_ate_19-08-2026.xlsx`, somente `Raw Data Report` | Opcional |
| ifood_report | `01_Analise_Jacare_Tratada.xlsx`, somente `iFood_App` | Opcional |

Nomes selecionam as fontes canônicas fornecidas para esta versão; cabeçalhos são validados pelos parsers. Layouts ou nomes novos exigem atualizar o contrato, não adivinhar campos. Arquivos idênticos repetidos em ZIPs são reconhecidos pelo hash; versões diferentes para a mesma fonte são rejeitadas. Uploads têm limite conjunto de 200 MiB e não são extraídos em disco.

## Preparação e granularidade

| Parquet / staging | Grão | Campos principais |
|---|---|---|
| orders | Pedido válido único, até o corte | `order_key`: chave substituta local; `opened_at`, `closed_at`; status/tipo/origem; valores de itens, serviço, entrega, pedido e recebimento; `customer_key`: HMAC local opcional na biblioteca e habilitado no pipeline principal |
| items | Linha de item com pedido relacionado | `order_key`, `sold_at`, quantidade, preços e valor da linha; produto, categoria e tipo; nenhuma informação de cliente |
| appdelivery_daily | Data × status × modalidade | Contagem e valores agregados de itens/entrega |
| food99_daily | Data | Contagens, receitas e deduções reportadas; somas/denominadores operacionais e de avaliações privados |
| ifood_daily | Data × status no recorte adicional | Contagem, valor de itens, total pago e entrega; sem ID individual |
| ifood_products | Produto no relatório adicional | Visitas, pedidos, unidades e valor reportados; janela própria não informada |
| instagram_daily | Data × métrica | Valor exportado e rótulo da fonte; nenhuma informação de perfil/público |
| meta_ads_daily | Data com detalhamento de anúncios | Gasto, impressões, subtotal de cliques conhecidos e contagens `link_clicks_observed_rows`/`link_clicks_missing_rows`; sem nome de anúncio ou público |

Datas Excel e textos de data são normalizados; valores monetários são numéricos e no dbt usam `decimal`. Código original e contato são usados somente em memória para associação/pseudonimização. A chave substituta é local à geração e não identifica o pedido original fora dela.

O corte também se aplica aos agregados de AppDelivery e 99Food. Valores necessários ausentes nessas fontes interrompem a preparação, em vez de serem tratados como zero. No Meta, cliques ausentes permanecem desconhecidos, com cobertura explícita e razões CPC/CTR condicionadas a cobertura completa.

## Marts

- `fct_daily_sales`: calendário, alvos observados e `has_source_records`. Datas sem fonte mantêm valores nulos.
- `fct_weekly_sales`: totais registrados, sete datas de calendário ou bordas parciais, dias observados/ausentes.
- `fct_channel_sales`: métricas por origem, sem inferir modalidade a partir de Desktop.
- `fct_sales_by_hour`: métricas por data e hora de abertura.
- `fct_product_performance`: produto/categoria/tipo, unidades, pedidos distintos e valor de itens.
- `fct_customer_recurrence`: recorrência agregada, sem chaves na saída.
- `fct_customer_activity_monthly`: primeira observação e retorno no histórico disponível.
- `fct_appdelivery_reconciliation` e `fct_ifood_reconciliation`: comparação entre fontes, sem combinar pedidos.
- `fct_food99_summary`: resumo do recorte; médias e soma de avaliações condicionadas a volume mínimo.
- `fct_instagram_daily`: valores preservados por data/métrica.
- `fct_marketing_daily`: métricas aditivas, CPC/CTR e vendas por data; associação descritiva.

## Rastreabilidade

`source_manifest.json` guarda nomes e SHA-256 das fontes, corte, cobertura, descartes e totais esperados. `quality_report.json` registra reconciliação com a fonte e verificações de schema. O manifesto ativo aponta para os artefatos da mesma geração. Valores brutos pessoais e segredos não entram nesses relatórios.
