# Experimento de previsão de demanda

## Decisão e alvos

Avaliar pedidos pagos e valor recebido diário como apoio potencial ao planejamento da operação. A fonte são os pedidos reais consolidados do PDV, com status pago e data de abertura. Nenhum dado pessoal é usado como feature. O experimento compara previsões de sete dias e oferece uma extensão recursiva exploratória até 14 dias.

## Tratamento do calendário

O calendário histórico mantém uma linha por data entre a primeira e a última data da fonte selecionada. Datas sem nenhum registro têm alvo nulo. Uma data com pedidos na fonte, mas sem pedidos pagos, pode ter contagem paga zero. Essa regra não determina se a loja estava aberta nem se a captura foi completa.

O responsável informou funcionamento de terça a domingo, das **18h30 às 23h**, no fuso de São Paulo. Esse calendário está em [business_calendar.json](../config/business_calendar.json). Em previsões, uma segunda-feira recebe zero por fechamento planejado; esse zero é uma hipótese operacional explícita, não um dado de venda observado. A mesma restrição é aplicada a todos os candidatos no backtest, como avaliação sob o calendário de referência atual.

As exceções históricas ainda precisam ser confirmadas: o histórico contém pedidos em uma segunda-feira. Horários de abertura do pedido também não comprovam o horário de atendimento. Nenhum pedido fora do horário é removido e nenhuma lacuna histórica vira zero. A auditoria do calendário aparece separadamente no dashboard.

Alvos ausentes nunca são preenchidos para treino ou pontuação. Os quatro algoritmos e os dois baselines usam exatamente as mesmas datas observadas comparáveis. Datas sem alvo ou sem previsão de algum baseline são excluídas da comparação, com quantidade registrada.

## Modelagem

Os parâmetros são fixados antes da avaliação, sem busca orientada pelo teste final:

- Random Forest: 120 árvores, profundidade máxima 6, mínimo de 5 observações por folha, até 80% das features em cada divisão e semente 42.
- Extra Trees: 160 árvores, profundidade máxima 6, mínimo de 5 observações por folha, até 80% das features e semente 42; usa divisões mais aleatórias entre as árvores.
- Hist Gradient Boosting: até 120 iterações, taxa de aprendizagem 0,05, até 15 folhas por árvore, mínimo de 10 observações por folha e regularização L2 igual a 1. Não usa parada antecipada com divisão aleatória de validação.
- Regressão Ridge: modelo linear com regularização `alpha=10` e padronização ajustada somente no treino; é uma alternativa mais simples às árvores.
- Baseline sazonal: valor observado no mesmo dia da semana anterior, exceto o fechamento planejado.
- Baseline médio: média dos valores conhecidos nos sete dias anteriores à origem, exceto o fechamento planejado.

Features: dia da semana, dia/mês, lags de 1/7/14/28 dias, médias observadas de 7/28 dias e quantidade de dias conhecidos nessas janelas. Features ausentes recebem mediana aprendida somente no treino, com indicadores de ausência. Isso não cria observações de venda.

A previsão é recursiva: cada passo usa apenas o histórico disponível e, após a origem, as próprias estimativas anteriores. Nenhum valor realizado da janela prevista entra como feature. O fechamento planejado também entra como estimativa na recursão, sem alterar o histórico real. As contagens de valores disponíveis nessas janelas passam a incluir as estimativas anteriores; elas não significam novas observações de venda.

## Seleção e avaliação final

`TimeSeriesSplit` define oito origens cronológicas, com sete dias de calendário por janela. Em cada origem, treino e features precedem o teste. Imputação, padronização quando aplicável e ajuste do modelo são refeitos somente no treino daquela origem.

Nas **seis primeiras janelas**, o algoritmo ML com menor MAE agregado é escolhido separadamente para cada alvo. A escolha fica congelada antes das **duas janelas finais**, que somam até 14 datas de calendário. O teste final não é usado para trocar o algoritmo ou ajustar parâmetros. No segundo teste final o modelo pode ser retreinado com os dados que já seriam conhecidos naquela nova origem: é uma avaliação de atualização semanal, não uma previsão única de 14 passos.

MAE é o erro absoluto médio na unidade do alvo: pedidos/dia ou R$/dia. WAPE divide a soma dos erros absolutos pela soma dos valores absolutos observados; fica ausente quando o denominador é zero. Os resultados de seleção, teste final e conjunto completo são apresentados separadamente. O agregado geral inclui as janelas de escolha e deve ser lido como diagnóstico, não como evidência independente de generalização.

O critério estatístico combinado exige, contra cada baseline, redução geral de MAE de pelo menos 10%, vitória em pelo menos 75% das oito janelas e no mínimo 28 dias comparáveis. Além disso, o escolhido precisa ter MAE menor que ambos os baselines no teste final agregado, com pelo menos dez dias comparáveis. Esse critério não comprova significância estatística nem autoriza uso operacional. O teste final é pequeno; sucesso ou falha em um alvo não é transferido ao outro.

## Artefatos e dashboard

Cada geração guarda métricas, relatório, modelos finais escolhidos e os quatro candidatos treinados em `ml/`. O hash da série entra nas métricas, no arquivo de modelos e no manifesto. As métricas versão 4 registram algoritmo escolhido, limites temporais de seleção/holdout, placar de todos os candidatos e calendário de referência. Os modelos finais são retreinados somente depois da avaliação, com todo o histórico conhecido, para gerar as estimativas experimentais.

As estimativas começam no dia seguinte à última data real da fonte. Com arquivos até **19/08/2026**, a janela de 14 dias é **20/08/2026 a 02/09/2026**, não os dias atuais de setembro/outubro. O dashboard deve destacar a desatualização e não deslocar as datas artificialmente.

As faixas mostradas adicionam à estimativa os percentis 10 e 90 dos poucos resíduos dos testes finais. São exploratórias, não intervalos calibrados e não garantem cobertura futura. O horizonte de sete dias é o efetivamente comparado no backtest; os dias 8 a 14 e suas faixas não passaram por avaliação própria de 14 passos. Erros podem se acumular.

## Projeção mensal e evolução

Além da janela de 14 dias, o modelo escolhido projeta o primeiro mês completo após a última data real. Com origem em **19/08/2026**, esse mês é **setembro de 2026**. A recursão percorre primeiro **12 dias de ponte (20 a 31 de agosto)** e depois os **30 dias de setembro**: o horizonte total até 30/09 é de **42 dias**, com **26 dias de abertura planejada** em setembro. A ponte não é pulada; suas estimativas alimentam os lags e médias usados nas previsões do mês.

O total mensal é a soma dessas estimativas diárias, não vendas observadas. O modelo permanece ancorado no histórico até agosto: consultar o painel em 30/09 não muda a origem nem transforma setembro em um mês realizado. A linha de evolução precisa distinguir meses observados, meses parciais e o mês projetado; uma diferença projetada em relação a um mês incompleto não demonstra crescimento real.

O artefato `monthly_projection` registra mês, origem, intervalo, dias de ponte, horizonte total, previsão por dia e total projetado. Não recebe bandas ou intervalos mensais sem calibração. O backtest de sete dias não valida os 42 dias de recursão: essa extensão é exploratória, pode acumular erro e não recebe aprovação operacional. Ao importar relatórios mais recentes, o primeiro mês completo seguinte é calculado dinamicamente a partir da nova origem.

## Limitações e critérios de uso

O histórico não cobre um ciclo anual completo. Não há histórico adequado de estoque, clima, promoções e eventos; as exceções ao calendário de funcionamento atual não estão validadas. Importâncias de árvores e coeficientes padronizados da Ridge descrevem associações do modelo, não causalidade. O Hist Gradient Boosting não recebe uma importância de feature inventada quando o estimador não a fornece.

A aprovação operacional permanece desativada. Exige relatórios recentes, validação de captura/calendário e acompanhamento prospectivo dos erros. O projeto não recomenda compras de estoque automaticamente, não garante faturamento e não estima lucro sem dados de custos.
