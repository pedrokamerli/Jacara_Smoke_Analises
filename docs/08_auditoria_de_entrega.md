# Auditoria técnica e confidencialidade

A auditoria detalhada do negócio foi preservada em data/private/audit_records, fora do material público. Este documento não divulga faturamento, volume, campanhas, resultados de modelos reais ou projeções do cliente.

A validação usa testes dbt, reconciliação com as fontes, backtest temporal e testes de interface. O modo real mantém suas gerações originais; a demo gera outra base e reexecuta SQL/dbt/ML em workspace separado.

Antes de qualquer publicação: executar a suíte, conferir demo/public, revisar código/documentos e histórico do repositório. Os testes locais com dados reais são ignorados quando as fontes privadas não existem. Sem commit, push ou implantação nesta etapa.
