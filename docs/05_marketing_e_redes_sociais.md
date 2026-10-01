# Marketing e redes sociais

## Instagram

O importador seleciona os seis CSVs de séries: alcance, visualizações, interações, visitas, cliques no link e seguidores. Lê UTF-16, a linha `sep=,`, o título e o cabeçalho `Data,Primary`. Mantém uma observação por data e métrica, rejeitando datas repetidas. O corte completo também se aplica às séries.

Os valores são preservados como exportados e não são somados. A definição de fluxo diário ou estoque/acumulado precisa ser confirmada para cada indicador. Exportações de público e conteúdo com identificadores, legendas e links não entram no pipeline atual.

## Meta Ads

Fonte canônica: `04_Relatorio_Meta_Atualizado_ate_19-08-2026.xlsx`, aba `Raw Data Report`.

O arquivo contém uma linha total, resumos de campanhas, conjuntos e anúncios e o detalhamento diário. Somar todas as linhas repetiria o gasto. O parser acompanha o nível da hierarquia e seleciona apenas datas válidas no nível de anúncio. Exclui as linhas `All`, os resumos e os relatórios antigos sobrepostos.

Gasto e impressões são agregados por data. Cliques somam somente valores reportados; ausências não viram zero. CPC e CTR ficam nulos quando falta cobertura. Razões completas usam totais, não média simples de razões. Contagens e resultados reais são privados.

O alcance não é somado porque a mesma pessoa pode aparecer em anúncios e datas diferentes. O gasto do detalhamento da fonte inteira precisa bater com a linha total antes de publicar a geração atual; o corte seleciona apenas as datas que serão analisadas. Assim, um corte anterior não é comparado indevidamente ao total geral de um período maior.

## Relação com vendas

Os dados são ligados às vendas pela data, mantendo desconhecidas as vendas de datas sem registro. Uma correlação descritiva é apresentada somente em pelo menos dez datas coincidentes com grupos de venda elegíveis. Não representa atribuição causal.

Não se infere CAC, lucro ou ROAS incremental. Métricas de compra ou valores atribuídos presentes em relatórios antigos não são misturados ao layout atual para criar uma série supostamente comparável.
