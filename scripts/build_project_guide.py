"""Guia público: conteúdo editorial fixo, sem ler qualquer dado do cliente.

Executar com Python + reportlab. Dependência documental, não do dashboard.
"""
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output/pdf/guia_jacare_analytics.pdf"
FONT = Path("C:/Windows/Fonts")
pdfmetrics.registerFont(TTFont("Guide", str(FONT/"segoeui.ttf")))
pdfmetrics.registerFont(TTFont("GuideBold", str(FONT/"segoeuib.ttf")))
GREEN = colors.HexColor("#20745B")
INK = colors.HexColor("#17372D")
body = ParagraphStyle("body", fontName="Guide", fontSize=10.5, leading=15.7, textColor=INK, spaceAfter=10)
heading = ParagraphStyle("heading", fontName="GuideBold", fontSize=24, leading=29, textColor=GREEN, spaceAfter=17)
sub = ParagraphStyle("sub", parent=body, fontName="GuideBold", fontSize=12, leading=16, spaceBefore=6)
small = ParagraphStyle("small", parent=body, fontSize=9, leading=12)

CHAPTERS = [
("01", "O projeto em linguagem simples", [
("O problema", "Uma hamburgueria recebe relatórios de pedidos, produtos, delivery e redes sociais em arquivos separados. Meu trabalho é transformar esses arquivos em informações que ajudem a entender o movimento, o cardápio e a recompra. Antes de escolher ferramentas, defini perguntas e o significado de cada indicador."),
("O que construí", "Preparei uma pipeline: uma sequência reproduzível que lê os arquivos, seleciona campos, valida registros, organiza tabelas, executa consultas e avalia modelos de previsão. O dashboard apresenta resultados com narrativas, tabelas, gráficos e explicações para quem não trabalha com dados."),
("Real e demo não são a mesma coisa", "O projeto analítico real usa exclusivamente os arquivos fornecidos pelo negócio. A demonstração pública usa outra base, inteiramente sintética e independente. Ela não é uma cópia com valores escondidos nem um faturamento real multiplicado por um fator. Seus modelos são treinados novamente com os dados fictícios."),
("Limites deste guia", "Este documento descreve o processo, não divulga resultados comerciais, dados pessoais ou credenciais. Não contém faturamento, volumes, clientes nem previsões reais do proprietário. Configurações, comandos e exemplos usam placeholders ou definições técnicas. Nenhuma implantação pública é afirmada como concluída."),
]),
("02", "Como navegar e aprender", [
("Roteiro de leitura", "Capítulos 3 e 4 explicam a metodologia e a stack. Os capítulos 5 a 8 detalham fontes, tratamento, SQL e perguntas de negócio. Os capítulos 9 e 10 apresentam Machine Learning. Os capítulos 11 a 14 tratam do dashboard, privacidade, login e publicação. O capítulo 15 funciona como manual de operação, e o 16 traz glossário e referências."),
("O que está implementado", "Ingestão com contratos de fontes, Parquet minimizado, warehouse DuckDB, modelos e testes dbt, quinze consultas, comparação temporal de quatro algoritmos e dois baselines, projeções experimentais, dashboard explicativo, importação local e separação de demo. O controle de acesso Google foi incluído antes da leitura dos artefatos privados."),
("O que ainda depende de configuração", "O login completo precisa de cliente OAuth Google, contas autorizadas e teste do callback. A VPS já usa Docker, mas domínio e proxy ainda precisam ser confirmados. HTTPS, firewall, volumes privados, ciclo de sessão e implantação devem ser homologados. Power BI continua uma entrega futura; não existe um PBIX entregue neste guia."),
("Como avaliar a entrega", "Não basta um gráfico bonito ou um modelo treinado. Confira a origem, o significado da métrica, a reconciliação, as limitações e os testes. A demo mostra engenharia e usabilidade, mas seus resultados não provam desempenho comercial ou qualidade de previsão na empresa real."),
]),
("03", "CRISP-DM: da pergunta à entrega", [
("1. Entendimento do negócio", "Defini quinze perguntas sobre vendas, calendário, produtos, clientes, delivery e marketing. Estabeleci quais métricas respondem cada pergunta. Sem custos completos, o projeto não calcula lucro nem classifica produtos como rentáveis."),
("2. Entendimento dos dados", "Inventariei arquivos, formatos, colunas, granularidade, datas e sobreposições. Um registro de pedido não tem o mesmo significado que uma linha de item ou um resumo diário de anúncio. Relatórios parecidos podem representar os mesmos pedidos."),
("3. Preparação", "Python seleciona campos permitidos, interpreta datas e valores, remove identificadores diretos, produz chaves protegidas na camada privada e grava Parquet. Dias sem registro mantêm alvo ausente: não são convertidos automaticamente em vendas zero."),
("4. Modelagem", "SQL/dbt constrói staging e marts. Scikit-learn compara algoritmos para pedidos e valor recebido, usando informação disponível no passado. A demo executa as mesmas transformações com outra base."),
("5. Avaliação", "Testes conferem chaves, relacionamentos, tipos e reconciliações. O backtest cronológico compara o ML com regras simples e reserva semanas finais para avaliar a escolha. Ressalvas de negócio continuam explícitas."),
("6. Implantação", "Uma geração só fica ativa após as etapas passarem. O dashboard lê a geração validada. A implantação remota exige controles adicionais, autenticação e testes de isolamento. CRISP-DM é iterativa: novos problemas devolvem o trabalho às fases anteriores."),
]),
("04", "Stack e arquitetura", [
("Python, pandas e openpyxl", "Python coordena o processo; pandas trabalha com tabelas; openpyxl lê Excel. A ingestão aplica contratos em vez de aceitar qualquer planilha como se tivesse o mesmo significado."),
("Parquet", "É um formato colunar com tipos definidos, útil para guardar tabelas tratadas de maneira eficiente. Não é uma ferramenta de anonimização: seus arquivos privados também precisam de proteção."),
("DuckDB, SQL e dbt", "DuckDB executa SQL localmente. SQL expressa agrupamentos, filtros e reconciliações. dbt organiza dependências, modelos e testes. Escolhi essas ferramentas porque o volume cabe no ambiente local; não adicionei Spark ou PostgreSQL apenas para aumentar a lista de tecnologias."),
("Scikit-learn e Streamlit", "Scikit-learn treina e avalia modelos. Streamlit apresenta análises, controles e narrativas. A importação é uma função do ambiente local, não da demo pública. Docker prepara uma execução reproduzível; não substitui HTTPS, autenticação ou firewall."),
("Fluxo reproduzível", "Fontes autorizadas > Python e validação > Parquet > DuckDB/dbt > auditoria > quinze consultas e ML > manifesto > dashboard. Manifesto é o arquivo que identifica qual geração foi aprovada e onde estão seus artefatos. Uma falha não deve trocar a geração anterior por um resultado parcial."),
]),
("05", "Fontes, granularidade e cobertura", [
("Pedidos e itens", "O PDV consolidado é a referência para pedidos pagos e valor recebido. A tabela de itens informa produto, quantidade e valor por linha. Somar o total do pedido depois de juntar todas as linhas de itens duplicaria valores: um pedido pode conter vários itens."),
("Delivery", "MenuDino e iFood aparecem como origens no sistema de vendas. AppDelivery e o relatório adicional iFood têm recortes próprios e são reconciliados, não adicionados cegamente ao faturamento. O 99Food conserva sua cobertura e suas deduções reportadas. Uma fonte incompleta não permite declarar um vencedor entre plataformas."),
("Instagram e Meta Ads", "As séries do Instagram preservam os valores exportados, sem supor que seguidores sejam novas pessoas por dia. Meta Ads tem totais, resumos e detalhes; o parser escolhe o nível diário de anúncio para evitar somar a mesma informação várias vezes. Falta de cliques não vira zero."),
("Contrato de importação", "A aplicação reconhece fontes documentadas por função e layout. Arquivos conflitantes geram erro. ZIPs são lidos em memória com limites, sem extração livre para o disco. Alguns relatórios adicionais são opcionais; o conjunto principal é necessário para o pipeline atual."),
("Data não é apenas um filtro", "O corte usa a última data completa disponível. A base real fornecida termina em agosto; não inventamos setembro realizado para preencher o painel. Datas ausentes, meses parciais e janelas de cada plataforma precisam acompanhar toda comparação."),
]),
("06", "Preparação, qualidade e privacidade", [
("Seleção antes de publicar", "Os parsers trabalham com listas explícitas de campos. Nomes, telefone, endereço, e-mail, observações e texto livre não entram na apresentação analítica. O telefone pode ser usado em memória para produzir HMAC e contar retornos na camada privada."),
("Pseudônimo não é anonimato", "HMAC gera um código estável a partir de uma entrada e de um segredo local. Não é a mesma coisa que usar um hash simples de telefone. Ainda assim, os códigos são pseudonimizados e continuam privados. O segredo não deve estar no Git, na demo ou em logs."),
("Reconciliação", "Confiro contagem de pedidos e soma do valor recebido entre uma leitura independente da origem, os dados tratados e os marts. Também verifico ligação item-pedido, colunas permitidas e quantidade de datas sem registro. Para anúncios, o detalhe é comparado ao total do relatório."),
("Datas ausentes", "Ausência significa desconhecido, não zero. O ML não recebe essas datas como exemplos de venda zero. Fechamento planejado nas segundas-feiras vale somente para estimativas futuras; registros históricos fora do calendário continuam preservados até confirmação da operação."),
("Limites da proteção", "Ocultar grupos pequenos reduz exposição, mas não garante anonimização. Dados comerciais também são confidenciais. Na apresentação pública, a proteção principal é não disponibilizar qualquer base ou resultado real. A finalidade, retenção, autorização e acesso devem ser acordados com o responsável; este guia não certifica conformidade jurídica."),
]),
("07", "SQL e engenharia analítica", [
("Staging e marts", "Staging padroniza nomes e tipos mantendo o significado da fonte. Marts reorganiza os dados para perguntas de negócio: vendas diárias e semanais, desempenho de produtos, canais, recorrência e marketing. As dependências permitem descobrir o que precisa ser recalculado após uma atualização."),
("Exemplo de raciocínio SQL", "Para vendas por dia: selecionar pedidos pagos; converter a abertura em data; agrupar por essa data; contar pedidos e somar amount_received_brl. Para ticket: dividir a soma recebida pelo número de pedidos, com proteção contra divisão por zero. Não tirar a média simples dos tickets de dias com volumes diferentes."),
("Testes dbt", "Verifico unicidade de pedidos, relação dos itens com pedidos, datas únicas nas séries, valores não negativos onde aplicável, formato das chaves e consistência dos alvos. dbt build executa modelos e testes; teste aprovado não confirma sozinho o significado contábil de uma métrica."),
("Gerações e rastreabilidade", "Cada execução guarda fontes e hashes, relatório de qualidade, resultados dbt, respostas e métricas. O manifesto aponta para a geração ativa. SHA-256 detecta diferenças nos arquivos, mas não prova anonimização, autorização nem correção do negócio."),
("Como reproduzir", "As quinze consultas ficam em sql/business. As regras de transformação estão em warehouse. A pipeline em src/jacare_analytics coordena as etapas. Quem inspeciona o portfólio consegue relacionar uma pergunta à consulta, à tabela intermediária e ao teste, sem precisar acessar os arquivos confidenciais."),
]),
("08", "As quinze perguntas de negócio", [
("Vendas e calendário: 1 a 6", "1. Qual valor recebido e quantos pedidos pagos? 2. Como evoluem valor, pedidos e ticket? 3. Quais melhores e piores dias? 4. Quais melhores e piores semanas? 5. Quais dias da semana e horários concentram vendas? 6. Como o ticket varia por canal e período? Rankings dependem de cobertura e critério explícito. A evolução mensal usa gráfico de linha; mês parcial não é diretamente comparável a um completo."),
("Cardápio: 7 a 10", "7. Quais produtos lideram em unidades? 8. Quais contribuem mais para o valor dos itens? 9. Quais têm menor volume observado? 10. Quais complementos aparecem mais? Componentes de combos não são contagem de combos completos. Baixo volume não significa baixa margem, pouca qualidade ou recomendação automática de retirada."),
("Clientes: 11 a 13", "11. Quais grupos têm maior frequência e valor acumulado? 12. Quantos clientes identificáveis compraram mais de uma vez? 13. Como variam primeira observação, retorno e tempo sem compra? Apresento grupos, não nomes ou rankings pessoais. Recorrência depende da cobertura de identificação e do intervalo analisado; primeira aparição na base não é primeira compra da vida."),
("Canais e marketing: 14 e 15", "14. Como MenuDino, iFood e o recorte 99Food se apresentam sem duplicação? 15. Como evoluem Instagram e Meta Ads e quais associações descritivas aparecem com vendas? Correlação temporal não prova que um anúncio gerou uma venda. Não calculo CAC ou ROAS incremental sem evidência de atribuição."),
("Formato da resposta", "Cada seção combina resposta em palavras, interpretação, ressalvas e tabelas SQL. Quando a fonte não sustenta uma conclusão, o painel mostra a limitação em vez de inventar um resultado. Na demo, as mesmas perguntas são respondidas sobre exemplos sintéticos, não sobre o cliente."),
]),
("09", "Machine Learning explicado", [
("O que tentamos prever", "Os dois alvos são pedidos pagos por dia e valor recebido por dia. São estimativas independentes: dividir um total previsto pelo outro não produz automaticamente um ticket futuro validado. Previsão não é promessa nem venda já realizada."),
("Como o modelo aprende", "Ele recebe exemplos passados, calendário, lags e médias anteriores. Lag é o valor de dias anteriores; média móvel resume uma janela passada. Não usamos informações do futuro para explicar o passado. Não incluímos dados pessoais como features."),
("Quatro algoritmos", "Random Forest combina árvores treinadas com amostras; Extra Trees aumenta a aleatoriedade na construção das árvores; Hist Gradient Boosting combina melhorias sucessivas do erro; Ridge é uma regressão linear regularizada, uma referência mais simples. Mais complexidade não garante melhor desempenho."),
("Duas referências obrigatórias", "Comparo o ML com repetir o mesmo dia da semana anterior e com a média recente de sete dias. Se um modelo não superar essas regras de forma consistente, não há motivo para tratá-lo como uma melhoria operacional apenas por ser Machine Learning."),
("O que ficou fora", "Não há histórico confiável suficiente de estoque, clima, promoções, eventos e ciclos anuais completos para prometer que o modelo antecipará esses efeitos. Incluir novas variáveis exige origem, disponibilidade antes da previsão e testes de benefício, não só novas colunas."),
]),
("10", "Como avaliar e interpretar previsões", [
("Backtest temporal", "Simulo previsões em janelas do passado, sempre treinando antes da data de teste. As primeiras seis janelas escolhem o algoritmo; as duas finais avaliam a escolha congelada. Todos os métodos usam datas comparáveis observadas. Isso é diferente de embaralhar datas e dividir aleatoriamente."),
("MAE e WAPE", "MAE é o erro absoluto médio na unidade do alvo, como pedidos/dia ou reais/dia. Um MAE fictício de 3 pedidos significa erro médio de três pedidos, não limite máximo. WAPE é a soma dos erros absolutos dividida pela soma dos observados; não é taxa de acerto. O exemplo não é uma métrica do cliente."),
("Previsão recursiva", "Para estimar vários dias, a previsão anterior alimenta os lags seguintes. Incerteza pode aumentar. A janela de quatorze dias estende o teste semanal; dias adicionais não têm automaticamente a mesma evidência. A projeção do mês completo atravessa primeiro os dias entre a origem e o começo do mês."),
("Mês futuro e calendário", "O painel projeta o primeiro mês completo seguinte à origem. Com arquivos até agosto, isso permite estudar setembro, mas consultar o painel depois não atualiza a base. Terça a domingo, 18h30-23h, é o calendário informado; zero nas segundas futuras representa fechamento planejado, não observação."),
("Faixas e liberação", "Faixas exploratórias de resíduos não são garantia estatística de cobertura. Não inventamos intervalo mensal calibrado. Aprovar um modelo exige comparar baselines, observar consistência, atualizar dados e validar no horizonte desejado. Resultados reais ficam privados; desempenho da demo não é evidência de generalização para a empresa."),
]),
("11", "Dashboard e narrativa", [
("Oito telas de demonstração", "Visão geral, quinze perguntas, produtos, clientes, delivery, marketing, Machine Learning e metodologia. A área real local acrescenta atualização de dados. A demo não permite upload, caminhos locais ou filtros livres que acionem dados privados."),
("Ler os gráficos", "Na evolução mensal, a linha conecta valores observados de cada mês; isso não transforma meses parciais em completos. No ML, realizado e estimado são séries distintas. Linhas próximas indicam menor erro, não causalidade. Lacunas não significam venda zero. A projeção mensal é identificada como estimativa, com origem e ressalvas."),
("Legendas e indicadores", "Passe o cursor sobre ícones de ajuda e colunas. Valor recebido não é lucro; ticket é valor por pedido, não por pessoa; unidades não são pedidos; CPC é gasto por clique; CTR relaciona cliques e impressões. Indicadores ausentes ou não calculáveis não são preenchidos apenas para melhorar aparência."),
("Downloads", "Na demo, relatórios e previsões são sintéticos. Na área real, downloads continuam confidenciais depois que saem do sistema. Login controla o acesso no servidor, mas não impede o destinatário autorizado de compartilhar o arquivo. É necessário combinar regras de uso e retenção com o proprietário."),
("Atualizar com segurança", "No ambiente local, selecionar fontes oficiais, confirmar corte completo e iniciar a pipeline. Em caso de erro, a geração anterior continua ativa. Para a primeira implantação privada remota, recomendo apresentação somente leitura e atualização fora do servidor público."),
]),
("12", "Real, demo e proteção no Git", [
("Separação física e lógica", "A base real fica em data, com fontes, gerações e artefatos privados. O gerador sintético usa semente fixa e trabalha em data/demo/workspace sem ler estatísticas reais. Seu pacote público contém exatamente quatro arquivos: manifesto, respostas JSON, narrativa Markdown e métricas/previsões JSON."),
("Nenhum modelo real vai para a demo", "As consultas dbt e SQL são reexecutadas sobre dados fictícios, e o ML é treinado separadamente. A demo não recebe banco, Parquet, CSV, chaves, originais ou modelos serializados. A classificação do pacote e os hashes são verificados; arquivos extras bloqueiam a leitura pública."),
("Também revisar documentos", "Dados sensíveis podem aparecer em README, notebooks, comentários, imagens, testes e logs. Preservei auditorias detalhadas localmente e retirei resultados comerciais da documentação pública. Capturas do painel real não são material público apenas porque não mostram nomes."),
("Antes do GitHub", "Revisar arquivos selecionados, diferenças antes do commit e histórico do repositório existente. gitignore ajuda com arquivos não rastreados; não apaga commits antigos. Se um segredo foi exposto, removê-lo da versão atual não é suficiente: avaliar rotação e a exposição no histórico, clones e forks."),
("Portfólio responsável", "Publicar código, decisões, contratos, testes e demo identificada. Não divulgar números do cliente para provar qualidade técnica. A revisão do conjunto exato de arquivos e do histórico remoto ainda é um requisito antes de qualquer push."),
]),
("13", "Login Google versus login próprio", [
("Autenticação e autorização", "Autenticação responde quem é a pessoa. Autorização decide o que ela pode acessar. Google autentica; o aplicativo verifica a lista de contas permitidas. Uma pessoa entrar com Google não significa que ganhou acesso aos dados da hamburgueria."),
("Com Google", "A senha fica no provedor, não no projeto. O fluxo OIDC é tratado por Streamlit/Authlib. O código recebe a identidade validada, exige emissor Google, e-mail verificado, conta autorizada, sub presente e token dentro de prazo. Credenciais de aplicação não são a senha pessoal do proprietário."),
("Com usuário e senha próprios", "Teríamos de gerenciar hashes seguros de senha, criação e remoção de contas, recuperação, limitação de tentativas, sessões e MFA. Não é necessário adicionar PostgreSQL só para mostrar uma tela de login. A complexidade vem de manter um sistema de identidade de forma segura, não de desenhar o formulário."),
("Escolha para este projeto", "Você confirmou o uso de Google. Para poucas contas autorizadas, é uma escolha proporcional e reduz manutenção de senhas. Não elimina a necessidade de HTTPS, autorização, isolamento, backups e segurança da VPS. Contas Google devem ter proteção adequada, idealmente com verificação em duas etapas."),
("Estado da implementação", "O bloqueio do acesso real foi colocado antes da leitura dos dados. O modo remoto padrão exige OIDC; falta de configuração bloqueia. O modo local sem login é explícito e limitado a endereço loopback. Ele jamais deve ser colocado atrás de um proxy público. Login real e comportamento de múltiplas abas precisam de homologação."),
]),
("14", "Configurar Google e publicar na VPS", [
("O que você precisa fornecer", "Você já informou que usa VPS com Docker. Faltam domínio/subdomínio, tipo de proxy e configuração Google. Credenciais e lista de contas devem ser preenchidas privadamente no servidor. Não enviar senha, chave SSH ou client_secret pelo chat nem colocar esses valores no PDF."),
("Cadastro no Google", "Criar projeto no Google Cloud; configurar nome, audiência e escopos mínimos openid/email/profile; cadastrar usuários de teste se aplicável; criar cliente OAuth Web. Registrar callback local exato http://localhost:8501/oauth2callback e depois o HTTPS do domínio privado. Não solicitar acesso ao Gmail ou Drive."),
("Configuração local", "Copiar config/secrets.example.toml para .streamlit/secrets.toml. Preencher client_id, client_secret, redirect_uri e cookie_secret aleatório forte. Definir access.allowed_emails com contas específicas e prazo de sessão. O arquivo real fica fora do Git. Testar permitido, não permitido, expirado e sem credenciais."),
("Dois serviços Docker", "O público contém somente demo. O privado precisará de imagem/volume próprios, secrets externos, gerações analíticas somente leitura e proxy HTTPS. Nunca montar originais ou data inteira no serviço público. O Compose existente prepara a demo; não é uma implantação privada pronta."),
("Antes de liberar acesso externo", "Confirmar DNS/certificado, WebSocket, firewall e portas internas. Não desabilitar CORS/XSRF para corrigir proxy. Homologar expiração, logout, abas, downloads, caches e revogação. Testar reinício e restauração. Não tornar o modo local público para contornar erro de login."),
]),
("15", "Manual de execução e evolução", [
("Demo local", "Com ambiente instalado: scripts/run_project.ps1 -Mode Demo -Port 8502. Abrir localhost:8502. Para gerar outra versão: python -m jacare_analytics.demo. A demo/public existente é preservada; revisar a versão nova antes de promovê-la."),
("Real local e teste de login", "Para análise local: scripts/run_project.ps1 -Mode Real -Port 8501. Para testar Google: acrescentar -AuthMode Oidc e configurar secrets. Para importar fontes: usar a tela Atualizar dados no ambiente local ou a CLI. Não usar Refresh no modo Demo."),
("Qualidade em cada mudança", "Executar python -m unittest discover -s tests -v e python -m pip check. Verificar reconciliações, quinze perguntas, hashes, ausência de identificadores, calendário e reprodução de previsões. Testes dependentes da base real são ignorados quando ela não existe; isso não equivale a validar uma nova fonte em produção."),
("Rotina do proprietário", "Receber exports novos, confirmar última data completa, processar localmente, revisar alertas e comparar com a operação. Depois transferir a geração necessária à instância privada por canal seguro. Manter backup protegido e registrar a atualização, sem divulgar conteúdos privados em logs compartilhados."),
("Evolução do projeto", "Prioridades: homologar login/VPS, aumentar histórico para avaliação temporal mais forte, validar definições sociais e sobreposições, criar a entrega Power BI com bases separadas e automatizar rotinas de qualidade. Mais modelos devem ser adicionados apenas quando melhorarem uma avaliação justa, não para inflar a stack."),
]),
("16", "Glossário, referências e apresentação", [
("Glossário essencial", "Granularidade: o que uma linha representa. Pipeline: sequência reproduzível de etapas. Warehouse: dados organizados para análise. Mart: tabela orientada a um tema. Baseline: regra simples de comparação. Backtest: simulação no passado. Feature: variável de entrada. Alvo: valor previsto. Leakage: informação futura vazando para o treino. OIDC: protocolo de identidade. Allowlist: lista explícita do que é permitido."),
("Como apresentar a recrutadores", "Explique o problema, as quinze perguntas, contratos, decisões de stack, testes e trade-offs. Mostre demo identificada e uma consulta reproduzível. Explique por que não soma plataformas sobrepostas, não transforma lacunas em zero e não aprova ML só porque foi treinado. Não use números reais como evidência pública sem autorização."),
("Documentos do projeto", "README apresenta o caso; docs/01 registra CRISP-DM; docs/02 e 06 descrevem fontes e contratos; docs/03 trata proteção; docs/04 explica previsão; docs/05 trata marketing; docs/07 liga perguntas a SQL; docs/08 é auditoria técnica pública; docs/09 é roteiro de publicação; docs/10 detalha login e VPS."),
("Referências oficiais", "Streamlit: https://docs.streamlit.io/develop/concepts/connections/authentication ; API st.login: https://docs.streamlit.io/develop/api-reference/user/st.login ; Google OIDC: https://developers.google.com/identity/openid-connect/openid-connect ; Docker: https://docs.docker.com/build/concepts/context/ ; GitHub: https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository . Consultadas em 30/09/2026."),
("Compromisso de transparência", "Este guia foi preparado para explicar o projeto sem revelar dados do cliente. Configuração Google, teste de identidade real, VPS privada e Power BI continuam sujeitos às etapas indicadas. Uma demonstração sintética é uma forma de compartilhar o trabalho técnico com responsabilidade, não uma alegação de resultados reais."),
]),
]


def paragraph(text, style=body):
    return Paragraph(escape(text), style)


def footer(canvas, doc):
    canvas.setStrokeColor(GREEN)
    canvas.line(44, 40, A4[0]-44, 40)
    canvas.setFont("Guide", 8)
    canvas.setFillColor(INK)
    canvas.drawString(44, 27, "Jacaré Analytics | Guia público | Sem dados confidenciais")
    canvas.drawRightString(A4[0]-44, 27, str(doc.page))


def build():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(OUT), pagesize=A4, leftMargin=44, rightMargin=44, topMargin=45, bottomMargin=55,
                            title="Jacaré Analytics - Guia didático do projeto", author="Pedro", subject="CRISP-DM, SQL, Python, ML, demo, login e VPS")
    story = [Spacer(1, 62), paragraph("JACARÉ ANALYTICS", heading),
             paragraph("Guia completo do projeto de dados", heading),
             paragraph("Do problema de negócio à análise, às previsões e à publicação segura."),
             Spacer(1, 18), paragraph("Python • SQL • DuckDB • dbt • scikit-learn • Streamlit • Docker", sub),
             Spacer(1, 18), paragraph("Desenvolvido por Pedro | Edição de 30/09/2026"),
             paragraph("Documento público. Sem faturamento, resultados ou dados pessoais reais do cliente."),
             paragraph("Login Google: controle implementado, configuração e homologação pendentes. VPS: não publicada. Power BI: próxima entrega."), PageBreak()]
    for number, title, sections in CHAPTERS:
        story.append(paragraph(f"{number} / {title}", heading))
        for label, text in sections:
            story += [paragraph(label, sub), paragraph(text)]
        if number != "16":
            story.append(PageBreak())
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    print(str(OUT))


if __name__ == "__main__":
    build()
