# Dashboard privado: layout e filtros

## Objetivo

Transformar a área privada em um painel executivo legível, com navegação azul-escura,
cartões de indicadores, gráficos em painéis e explicações junto aos resultados.
A referência visual enviada pelo proprietário orientou o layout. O exemplo de
[análise de varejo da Microsoft](https://learn.microsoft.com/en-us/power-bi/create-reports/sample-retail-analysis)
orientou a hierarquia entre período, indicadores, tendência e comparação.
Isso não significa que este dashboard seja um relatório Power BI: a interface usa
Streamlit e Altair; os dados são consultados em DuckDB com SQL.

## Um contrato de filtros, não vários cálculos independentes

`SalesFilter` define período, origem do pedido no PDV, tipo de pedido e dia da semana.
As consultas usam uma CTE `selected_orders`, sempre com pedidos pagos e SQL
parametrizado. Indicadores, gráficos e tabelas de vendas partem dessa mesma seleção.
O cache inclui a geração ativa e todas as dimensões; não existem views mutáveis
globais compartilhadas entre sessões de usuários.

| Página | Escopo dos filtros |
| --- | --- |
| Visão geral | Período, canal do PDV, tipo de pedido e dia da semana |
| Produtos | Mesmos filtros de vendas, mais tipo de item, categoria e ordenação |
| Clientes | Mesmos filtros de vendas; recorrência calculada dentro do recorte |
| Delivery e Marketing | Período aplicado a cada fonte; sem canal do PDV para fontes sem vínculo comprovado |
| 15 perguntas e respostas | Evidências salvas da geração completa; escopo explícito na página |
| Machine Learning | Modelos e previsões da geração completa; filtrar vendas não retreina modelos |

### Como usar

1. Escolher histórico completo, mês específico, últimos 30 dias da base ou datas personalizadas.
2. Nas páginas de vendas, restringir canais, tipos e dias desejados.
3. Conferir o recorte ativo e os valores recalculados. Uma seleção vazia significa
   nenhum registro, não todos os registros.
4. Usar **Limpar filtros** para restaurar o histórico completo e todas as dimensões.

“Últimos 30 dias” termina na última data do arquivo, não na data do relógio.
Um mês parcial permanece parcial. Períodos sem registros não são tratados como
faturamento zero, pois a ausência de arquivo pode ser uma lacuna de cobertura.

## Leitura dos indicadores e gráficos

- Valor recebido é o valor realizado em pedidos pagos; não é lucro.
- Ticket médio é valor recebido dividido por pedidos pagos, não por clientes.
- Dias com pedidos são dias presentes no recorte, não prova de todos os dias abertos.
- Variações comparam o intervalo anterior de igual duração e mesmos filtros, apenas
  quando o histórico anterior existe e o grupo é elegível.
- Evolução mensal é uma linha com marcadores. Um único ponto permanece visível.
- Dias da semana mostram soma do recorte, não média de uma semana típica.
- Horários mostram abertura do pedido no sistema, não tempo de preparo.
- Origens registradas no PDV não garantem a separação de todas as plataformas externas.
- Quantidade de componente de combo não é quantidade de combos completos.
- Rankings inferiores excluem itens sem dados/grupos pequenos; não comprovam que um
  produto jamais foi vendido ou que deva sair do cardápio.
- Valor de itens não é margem nem necessariamente o valor recebido do pedido.
- Recorrência e recência respeitam o recorte. Primeira aparição usa o histórico geral
  disponível, não prova da primeira compra da vida do cliente.

## Confidencialidade e validação

O módulo novo é carregado somente depois da autorização privada. Não foram alteradas
as contas autorizadas, o login Google, a separação real/demo nem a imagem pública.
O painel não apresenta nomes, telefones ou códigos individuais. Grupos pequenos
continuam omitidos; os limites de exibição são regras de minimização, não certificação
de anonimização ou comprovação integral de conformidade legal.

Foram executados 57 testes locais, incluindo reconciliação com a geração real,
partição por canal/tipo/dia, seleção vazia, SQL parametrizado, atualização de widgets,
payload dos gráficos, limpeza dos filtros e marcadores em um único dia.
Na VPS, a imagem candidata passou por teste isolado das oito páginas, filtros e
bloqueio de identidade inválida antes de sua promoção.

A implantação usa `jacare-analytics-private:dashboard-v1`. O snapshot real continua
em volume somente leitura e fora da imagem. O contexto de build admite somente os
arquivos de código necessários. A configuração anterior foi preservada no servidor
em `compose.analytics-v1.rollback.yaml`. Nenhum faturamento, dado pessoal, segredo
ou captura real deve ser incluído nesta documentação pública ou no Git.
