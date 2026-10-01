# Login Google e implantação privada

## Situação atual

O bloqueio foi implementado antes da leitura do manifesto, SQL, ML e downloads. Demo continua pública e isolada em `analisejacare.pedromerli.com`. Acesso real usa OIDC em `jacare.pedromerli.com`, sem liberar dados quando faltam credenciais. Em 01/10/2026, o usuário confirmou entrada com a conta permitida e bloqueio de outra conta. A implantação utiliza Docker e Nginx. Evidências e limitações estão em `12_login_privado_homologacao.md`.

O lançador local aceita `-AuthMode Local` (padrão, apenas endereço loopback) e `-AuthMode Oidc`. Não usar Local atrás de proxy público. Para testar login: `scripts/run_project.ps1 -Mode Real -AuthMode Oidc -Port 8501`.

## O que precisamos de você

- Domínio/subdomínio para demo e área privada; VPS com Docker já confirmada.
- Qual proxy você usa: Nginx, Traefik, Caddy ou painel com proxy gerenciado.
- Acesso ao Google Cloud Console para registrar um cliente OAuth do tipo Web.
- Contas Google autorizadas, configuradas somente no arquivo privado da VPS.

Não enviar senha Google, senha da VPS, token, client_secret ou chave SSH pelo chat. O client secret identifica a aplicação e não é a senha pessoal do Google.

## Configuração Google, passo a passo

1. Criar um projeto no Google Cloud Console para o login da aplicação.
2. Configurar Google Auth Platform: nome, suporte, audiência e escopos mínimos de identidade (openid, email, profile). Não solicitar acesso a Gmail, Drive ou arquivos.
3. Se a aplicação estiver em teste, cadastrar você e o proprietário como usuários de teste. Isso não substitui a allowlist do aplicativo.
4. Criar cliente OAuth do tipo aplicação Web.
5. Cadastrar callback local exato: `http://localhost:8501/oauth2callback`. Abrir o teste em localhost, não trocar para 127.0.0.1 sem cadastrar outro callback.
6. Depois de escolher o domínio, cadastrar `https://cliente.seudominio.com/oauth2callback` (substituir pelo domínio real). A URL deve coincidir com o redirect_uri do servidor, inclusive protocolo, porta e caminho.
7. Copiar `config/secrets.example.toml` para `.streamlit/secrets.toml` local e preencher credenciais. Gerar cookie_secret aleatório: `python -c "import secrets; print(secrets.token_hex(32))"`. Não registrar a saída em commits/logs compartilhados.
8. Preencher `access.allowed_emails` com contas específicas. Não permitir um domínio inteiro nem cadastro público.
9. Instalar dependências atualizadas e abrir o modo Oidc. Testar uma conta permitida e uma não permitida.

## Política implementada

Streamlit/Authlib valida o fluxo OIDC; o aplicativo não aceita identidade enviada por formulário. A autorização exige emissor Google, identidade sub presente, email_verified verdadeiro, e-mail na lista e timestamps válidos. O token deve estar dentro de exp e de até uma hora desde iat. Claims ausentes bloqueiam, em vez de ampliar acesso. Caso a configuração real do provedor não forneça essas claims, revisar a integração com evidência; não desabilitar a regra para liberar acesso.

Não usamos o cookie de longa duração do Streamlit como autorização ilimitada. Cada execução da página reavalia a conta e a validade. Logout encerra a sessão atual; outras abas previamente autenticadas precisam ser testadas e não são prometidas como revogadas instantaneamente. Expiração não remove downloads já feitos nem controla pixels já vistos. Antes de produção, homologar abas abertas, caches, expiração e revogação, e avaliar checagem periódica.

## VPS com Docker

Mantemos dois serviços: público (somente demo) e privado (snapshot analítico real). Nunca montar fontes reais no contêiner público. A área privada recebe um volume somente leitura com a geração analítica e um secrets.toml somente leitura, com permissões restritas e fora da imagem/Git. Nesta primeira versão remota, atualização/upload estão desabilitados: processar os arquivos localmente, validar e transferir apenas a geração necessária, preservando backups. O segredo HMAC e os originais não precisam estar no serviço de apresentação.

Não executar o modo privado simplesmente com compose.yaml público: ele foi feito para demo, sem volumes reais. O serviço privado usa `deploy/compose.private.yaml`, com domínio, proxy e volumes definidos. Na VPS usar JACARE_PUBLIC_MODE=false e JACARE_AUTH_MODE=oidc; nunca local. Não publicar portas diretas dos serviços. Nginx atende HTTPS e redireciona HTTP, mantendo a rota de emissão de certificados. Backups, firewall, revisão/fixação de dependências e demais critérios de homologação continuam sendo responsabilidades operacionais.

## Critérios para liberar produção

- Sem credenciais: bloqueia antes de ler qualquer artefato real.
- Sem login: somente entrada; sem métricas, importação ou downloads.
- Conta Google não autorizada: bloqueia todos os dados.
- Conta permitida: abre somente a instância privada.
- Token vencido, emissão futura ou claims ausentes: bloqueia.
- Logout e múltiplas abas: comportamento documentado e verificado.
- Sem acesso direto às portas; certificados e callback corretos.
- Público permanece funcional mesmo sem montar nenhum arquivo privado.
- Reinício, atualização, backup e restauração testados.

## Própria senha ou Google?

Google não entrega a senha ao projeto; autentica a pessoa. Nosso código decide sua autorização. Login próprio exige hashes de senha fortes, recuperação segura, limitação de tentativas, gestão de contas e eventualmente MFA. Para duas contas autorizadas, Google reduz o trabalho de manter credenciais. Não elimina riscos de servidor, sessão ou autorização.

Referências: [Streamlit/OIDC](https://docs.streamlit.io/develop/concepts/connections/authentication), [st.login](https://docs.streamlit.io/develop/api-reference/user/st.login), [Google OpenID Connect](https://developers.google.com/identity/openid-connect/openid-connect).
