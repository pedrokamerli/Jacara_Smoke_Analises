# Publicação segura: real e demo

Separei a análise do cliente da demonstração do portfólio. A demo foi publicada em 01/10/2026; o ambiente real continua bloqueado. Registro em [Demo publicada](11_demo_publicada.md).

## Implementado

- Modo padrão: demo sintética, somente leitura, sem upload nem acesso ao warehouse real.
- Base fictícia independente, sem reescalar faturamento ou reutilizar previsões reais. Gerador v1, semente 731, período de exemplo em 2025.
- A mesma pipeline Python → Parquet → SQL/DuckDB/dbt → 15 perguntas → ML calcula os resultados da demo.
- Pacote demo/public: manifesto, respostas JSON, narrativa Markdown e métricas/previsões JSON. Sem bancos, modelos serializados, originais ou identificadores individuais.
- Validação de classificação sintética, hashes e lista de arquivos. Pacotes reais são recusados mesmo com o antigo sinalizador de aprovação.
- Modo real explícito, apenas local, sem autenticação remota ainda.
- Dados, segredos, ZIPs, planilhas, bancos, modelos e PBIX excluídos do versionamento. Contexto Docker por allowlist, contendo somente código/configuração e pacote demo.
- Compose público sem montagem de dados reais; porta vinculada ao loopback, usuário sem privilégios, filesystem somente leitura.

Hashes verificam integridade, não provam origem ou anonimização. A separação depende também de revisão dos arquivos e controle de acesso ao servidor.

## Rodar localmente

```powershell
# Demo já incluída
.\scripts\run_project.ps1 -Mode Demo -Port 8502

# Cliente: dados reais locais
.\scripts\run_project.ps1 -Mode Real -Port 8501

# Gerar uma nova versão independente (preserva a demo padrão existente)
python -m jacare_analytics.demo
```

O gerador registra versões separadas em demo/<geracao>; o workspace fica em data/demo. Se já houver demo/public, não a sobrescreve. Revisar a versão nova antes de promover o pacote. Nunca promover uma exportação real.

## Git: roteiro antes de publicar

1. Rodar testes e revisar os quatro arquivos demo/public e todas as capturas.
2. Revisar também README, docs, notebooks, comentários, testes, logs e metadados. Dados comerciais podem aparecer fora da pasta data.
3. Conferir arquivos rastreados e histórico do repositório remoto existente antes de adicionar conteúdo. Não assumir que o repositório fornecido está limpo.
4. Adicionar somente arquivos revisados, evitando adicionar a pasta inteira. Conferir diff staged e executar detecção de segredos antes de commit/push.
5. Se dados já foram enviados, interromper a publicação, avaliar exposição e coordenar remoção do histórico/clones/forks. Segredos expostos exigem rotação.

.gitignore não remove conteúdo anteriormente rastreado ou histórico. [Orientação oficial do GitHub](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository).

## VPS pública: próxima etapa

Confirmar domínio, sistema operacional e proxy. Homologar imagem, fixar dependências/digest, executar análise de vulnerabilidades e configurar HTTPS, WebSocket, firewall e backups. Só depois executar docker compose config/build/up com autorização. Não abrir 8501 diretamente na internet e não desabilitar CORS/XSRF.

O Docker inclui apenas a demo. Não montar data, fontes ou a raiz do projeto na instância pública. [Contexto de build e dockerignore](https://docs.docker.com/build/concepts/context/#dockerignore-files).

## VPS privada com login: controle implementado, configuração pendente

O acesso real precisa de instância/volume separados, HTTPS, autenticação (preferencialmente OIDC), autorização explícita para a conta do proprietário, sessão/expiração, MFA quando disponível e segredos externos ao Git. Autenticar uma pessoa não significa autorizar acesso aos dados. [Autenticação do Streamlit](https://docs.streamlit.io/develop/concepts/connections/authentication).

O controle Google foi incluído antes da leitura dos artefatos reais. Falta configurar cliente OAuth, contas permitidas e homologar o fluxo real. O lançador permite desenvolvimento local explícito; nunca colocar esse modo atrás de proxy público. Antes de implantar: testar usuário não autorizado, logout, múltiplas abas, isolamento de cache/downloads e acesso direto à porta privada. Configuração em [Login e VPS](10_login_e_vps.md).

## Power BI

Permanece uma entrega futura. Versão pública somente com base sintética; PBIX real, dataset e credenciais precisam de distribuição privada e acesso autorizado. Não utilizar publicação anônima para relatórios reais.

Os controles descritos não constituem uma declaração automática de conformidade jurídica. A finalidade, autorização e retenção dos dados reais precisam ser definidas com o responsável pelo negócio.
