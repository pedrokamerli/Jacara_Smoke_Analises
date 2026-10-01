# Dashboard analítico

Execute na raiz do projeto, após preparar os Parquet e as tabelas dbt:

```powershell
$env:JACARE_PUBLIC_MODE = 'false'
python -m streamlit run app/streamlit_app.py --server.address 127.0.0.1 --server.port 8501
```

No modo privado, o painel abre DuckDB em modo somente leitura, consulta os dados minimizados e apresenta agregados. Não mostra contatos ou IDs. A importação refaz o mesmo pipeline da CLI e só ativa resultados validados.

No modo público (padrão), o painel lê exclusivamente demo/public, com dados sintéticos e ML independente. Pacotes reais são bloqueados. Tem oito telas, sem upload e sem filtros livres. Execute scripts/run_project.ps1 -Mode Demo -Port 8502. Modo real exige -Mode Real; para testar Google acrescentar -AuthMode Oidc e configurar credenciais privadas. O login remoto está sujeito à homologação. Veja [login/VPS](../docs/10_login_e_vps.md).

A tela de ML compara quatro algoritmos e duas referências, separa seleção de teste final e explica os horizontes de 7/14 dias. As estimativas começam após o fim dos arquivos reais; não são deslocadas para a data atual. As 15 perguntas têm narrativas, interpretações e tabelas conferíveis.
