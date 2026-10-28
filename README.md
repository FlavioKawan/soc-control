# SOC Control

Sistema interno de organização, governança e controle das regras e casos de
uso de um SOC (Security Operations Center).

> **Status do projeto:** em desenvolvimento por fases. Este README é
> atualizado a cada fase concluída. Fase atual: **Fase 10 adiantada —
> Dashboard**, com a **Fase 9 (Histórico)** também concluída (pulamos a
> Fase 8 de propósito a pedido do usuário; fica pendente, ver roteiro
> abaixo).

> **Vai alterar o código?** Comece por [`docs/`](docs/README.md):
> arquitetura, modelo de dados, funcionalidades e um guia passo a passo
> para cada tipo de alteração.

## Objetivo

O SOC Control **não é** um SIEM, SOAR ou sistema de gestão de incidentes.
É uma ferramenta de governança para responder, de forma centralizada:

- quais regras de detecção existem, seu status e para qual cliente;
- qual caso de uso, fonte de log, ameaça e técnica MITRE ATT&CK cada regra
  cobre;
- quais clientes têm cobertura para quais casos de uso;
- quais fontes de log estão operacionais por cliente;
- quais gaps de monitoramento existem e seu impacto;
- a evolução da cobertura de detecção por cliente.

## Princípio de arquitetura

**Estrutura fixa, conteúdo configurável.** As entidades do sistema (Cliente,
Regra, Caso de Uso, Fonte de Log, Gap, Usuário, Histórico) são tabelas reais
com relacionamentos de banco explícitos — nada de "tudo em JSON genérico".
Já os *valores de negócio* que variam entre operações de SOC (tecnologias,
status, severidades, categorias, tags, frameworks) são **catálogos
administráveis no banco**, nunca listas fixas no código.

## Arquitetura

```text
Usuário
   ↓
Nginx        (serve estáticos/mídia, faz proxy do restante)
   ↓
Gunicorn / Django
   ↓
PostgreSQL
```

Stack: Python + Django 5.2 LTS, PostgreSQL, Django Templates + Bootstrap
5.3, HTMX (quando necessário), Chart.js (dashboard), Docker Compose + Nginx
+ Gunicorn. Sem React/Vue/Angular, sem Kubernetes/Kafka/microserviços, sem
Celery/Redis a menos que uma necessidade real apareça.

## Apps do projeto

| App | Responsabilidade |
|---|---|
| `core` | settings, urls, wsgi/asgi (infraestrutura, não contém modelos de negócio) |
| `accounts` | autenticação nativa do Django, grupos (`ADMIN`, `SOC_MANAGER`, `ANALYST`, `VIEWER`) |
| `taxonomy` | catálogos de "Configurações": Tecnologia, Status, Severidade, Categoria, Tag, Tipo de Regra, Framework/FrameworkControl. Campos Personalizados ficam para a fase 8 |
| `clients` | Cliente |
| `catalog` | Fonte de Log / Caso de Uso (globais) + `ClientLogSource` / `ClientUseCase` por cliente + Templates de Implementação |
| `detections` | Regra (+ verificações de inconsistência, colunas configuráveis, importação CSV) |
| `gaps` | Gap |
| `audit` *(fase 9)* | Histórico de alterações |
| `dashboard` | Visão consolidada: cards, gráficos (Chart.js), fluxo de onboarding, Cyber Kill Chain |
| `search` | Busca global (Cliente, Regra, Gap, Caso de Uso, Fonte de Log) a partir de uma única caixa na sidebar |
| `reports` | Exportação de relatório por cliente em PDF e Excel (regras, gaps, cobertura) |
| `notifications` | Comando de digest por e-mail (regras com revisão vencida, gaps sem movimento) |

## Permissões

Grupos criados via `python manage.py setup_roles` (idempotente — rode de
novo após cada `migrate` de uma fase nova, pois ele reconcede permissões
conforme os apps/models existentes no momento):

- **ADMIN** — acesso total, incluindo os catálogos de Configurações.
- **SOC_MANAGER** — CRUD completo nas entidades operacionais (clientes,
  catálogo, regras, gaps); sem acesso aos catálogos de configuração.
- **ANALYST** — cria/edita/consulta entidades operacionais, sem excluir e
  sem acesso à configuração.
- **VIEWER** — somente leitura.

## Instalação (Docker)

Pré-requisitos: Docker e Docker Compose.

```bash
cd soc-control
cp .env.example .env
# edite .env: defina DJANGO_SECRET_KEY, POSTGRES_PASSWORD, DJANGO_DEBUG=False em produção
docker compose up -d --build
```

O entrypoint do container `web` aplica migrations, roda `setup_roles` e
`collectstatic` automaticamente antes de iniciar o Gunicorn.

Acesse `http://localhost:8088/` (porta configurada em `docker-compose.yml`,
serviço `nginx`).

### Criar o primeiro superusuário

```bash
docker compose exec web python manage.py createsuperuser
```

### Migrations manuais (se necessário)

```bash
docker compose exec web python manage.py migrate
docker compose exec web python manage.py setup_roles
```

### Backup do PostgreSQL

```bash
docker compose exec postgres pg_dump -U <POSTGRES_USER> <POSTGRES_DB> > backup.sql
```

### Restore

```bash
cat backup.sql | docker compose exec -T postgres psql -U <POSTGRES_USER> <POSTGRES_DB>
```

### Atualização

```bash
git pull
docker compose up -d --build
docker compose exec web python manage.py migrate
docker compose exec web python manage.py setup_roles
```

## Variáveis de ambiente

Ver `.env.example`. Nunca commitar `.env` real (já está no `.gitignore`).
Em produção: `DJANGO_DEBUG=False`, `DJANGO_SECURE_SSL_REDIRECT=True`,
`DJANGO_SESSION_COOKIE_SECURE=True`, `DJANGO_CSRF_COOKIE_SECURE=True`, e
`DJANGO_ALLOWED_HOSTS` com o(s) domínio(s) reais.

## Segurança — pentest interno

Revisão ofensiva feita no próprio ambiente local (`localhost:8088`),
combinando leitura de código e ataques reais via HTTP. Achados e correções:

| # | Achado | Severidade | Correção |
|---|---|---|---|
| 1 | **Open redirect** (CWE-601): `RuleColumnPreferenceUpdateView` fazia `redirect(request.POST.get("next"))` sem validar o destino — um link malicioso podia redirecionar para qualquer domínio externo. | Alta | `django.utils.http.url_has_allowed_host_and_scheme` — só aceita URL relativa do mesmo host. |
| 2 | **Crash (500) com parâmetros inválidos** (CWE-20): `?stage=abc`, `?client=abc`, `?technology=abc` quebravam com `ValueError` não tratado — página fora do ar para quem usasse esse link, e com `DEBUG=True` expunha stack trace. | Alta | `core/utils.py::parse_int_or_none` — todo ID vindo de querystring passa por aqui antes de qualquer `.filter(pk=...)`. |
| 3 | **Login sem limite de tentativas** (CWE-307): 10+ tentativas de senha errada em sequência, todas aceitas sem bloqueio — força bruta trivial contra o admin. | Alta | `accounts/views.py::ThrottledLoginView` — bloqueia por IP (não por usuário, para não permitir que alguém trave o admin de propósito) após 10 falhas em 15 min. Usa um cache no próprio Postgres (`DatabaseCache`), sem precisar de Redis. |
| 4 | **Importação de CSV sem limite de linhas** (CWE-400): cada linha faz várias consultas individuais; um arquivo gigante travaria um worker do Gunicorn por minutos — com 2-3 uploads simultâneos, a aplicação fica fora do ar para todo mundo. | Média | `MAX_CSV_ROWS = 5000` em `detections/services.py` — interrompe e avisa em vez de processar sem limite. |
| 5 | Nginx expunha a versão (`Server: nginx/1.27.5`) — reconhecimento facilitado para um atacante escolher exploits conhecidos. | Baixa | `server_tokens off;` no `nginx.conf`. |
| 6 | `CSRF_COOKIE_HTTPONLY=False` sem necessidade — nenhum JS do sistema lê esse cookie. | Baixa | `CSRF_COOKIE_HTTPONLY = True`. |

**Testados e confirmados seguros** (sem necessidade de correção): SQL
injection via campos de busca (ORM parametriza tudo), XSS armazenado
(auto-escape do Django confirmado com `<script>` real), acesso a páginas
protegidas sem login (sempre 302 para o login), header `Host` forjado
(sempre 400, `ALLOWED_HOSTS` funcionando), CSRF (já corrigido na sessão
anterior — ver nota do Nginx `$http_host` acima).

**Registrado, não corrigido agora** — exige uma decisão de produto antes
de implementar: a spec original pede "isolamento entre clientes na
camada de aplicação". Hoje qualquer usuário autenticado com a permissão
`view_client` vê **todos** os clientes — não há um vínculo
usuário↔cliente que restrinja um analista a só ver os clientes dele. O
que já existe é o isolamento "defensivo" dentro dos formulários (ex:
`GapForm` só oferece casos de uso/fontes/regras do cliente selecionado,
para não misturar dados por engano) — isso evita erro, não impede acesso.
Se o requisito for "cada analista só vê os clientes atribuídos a ele",
é uma feature nova (precisa de um modelo de atribuição usuário↔cliente e
um filtro em toda queryset) — vale conversar antes de eu implementar
algo que pode não ser o que você imaginou.

Todos os achados corrigidos têm teste de regressão automatizado
(`accounts/tests.py::LoginThrottleTests`,
`detections/tests.py::MalformedQueryParamTests`,
`detections/tests.py::OpenRedirectTests`,
`detections/tests.py::CsvImportTests::test_oversized_file_is_capped...`,
`dashboard/tests.py::MalformedFilterParamTests`).

## Convenções de interface

Ajuste feito após feedback de que as telas estavam poluídas — princípio
adotado a partir daqui: **mostrar o essencial primeiro, o resto atrás de
um clique.**

- **Sidebar**: seção "Configurações" fica recolhida por padrão e só abre
  automaticamente quando você está numa tela de configuração. O item ativo
  é sempre destacado (via `core/context_processors.py::active_nav`,
  resolvido a partir da URL — nenhuma view precisa declarar isso
  manualmente).
- **Página do cliente**: organizada em abas (Visão Geral / Fontes de Log /
  Casos de Uso) em vez de empilhar tabelas e cards um atrás do outro.
- **Listagem de Regras**: só a busca textual fica sempre visível; os
  demais filtros ficam em "Filtros avançados" (recolhido por padrão, abre
  automaticamente se algum desses filtros já estiver aplicado via URL).

Ao criar uma tela nova, siga o mesmo princípio: campo de busca sempre
visível, filtros secundários atrás de um toggle, e nunca mais de ~3 blocos
de conteúdo não relacionados na mesma rolagem sem agrupamento (abas ou
seções com cabeçalho).

### Identidade visual

Depois do feedback de que o visual estava "muito básico" (Bootstrap puro,
sem paleta própria), definimos:

- **Fonte**: Inter (Google Fonts), substituindo a fonte padrão do sistema.
- **Ícones**: [Bootstrap Icons](https://icons.getbootstrap.com/) via CDN
  (`<i class="bi bi-nome-do-icone">`) — nunca emoji ou caractere Unicode
  como substituto de ícone. Toda ação principal (Novo/Adicionar/Editar/
  Excluir/Filtrar/Importar) tem um ícone correspondente; mantenha a
  convenção ao criar botões novos.
- **Paleta**: variáveis CSS em `static/css/app.css` (`--scv-accent` =
  indigo `#4f46e5`, `--scv-sidebar-bg` = slate escuro, etc.). Nunca use
  cores "cruas" (`#0d6efd` do Bootstrap, por exemplo) direto no HTML —
  use as variáveis, ou as classes já estilizadas (`.btn-primary`, `.card`,
  `.table`, `.badge`...), para qualquer tela nova herdar a identidade
  automaticamente.
- **Sidebar escura + conteúdo claro**: layout típico de ferramenta interna
  (ex: dashboards de SOC/observabilidade), não o navbar+sidebar claro
  genérico do Bootstrap.
- Badges de status/severidade continuam usando a cor cadastrada no
  catálogo (`object.color`, via `style="background-color: ..."`) — isso é
  dado, não decoração, e deve continuar vindo do banco, nunca hardcoded.

### Modo escuro

Botão de alternância (ícone de lua/sol) na sidebar e na tela de login.
Implementado em cima do suporte nativo de dark mode do Bootstrap 5.3
(`data-bs-theme="dark"` em `<html>`) — os componentes do Bootstrap
(cards, tabelas, formulários, modais) se re-estilizam automaticamente;
só precisamos adaptar as variáveis `--scv-*` próprias em
`static/css/app.css`, sob o seletor `:root[data-bs-theme="dark"]`.

Preferência salva em `localStorage` (por navegador, não por conta —
decisão deliberada: é uma preferência de exibição, não um dado de
negócio, então não precisa de campo no `User` nem de migration). Um
script inline no `<head>` lê o `localStorage` e aplica o atributo antes
da primeira renderização, evitando o "flash" da tela clara antes de
escurecer. Ao clicar no botão, a página recarrega — mais simples e
confiável do que tentar re-colorir os gráficos do Chart.js dinamicamente
sem reload.

Qualquer CSS novo deve usar as variáveis `--scv-*` (nunca uma cor fixa
como `#fff` ou `#f8f9fc`) para herdar os dois temas automaticamente —
foi exatamente a falta disso em 3 lugares (cabeçalho de tabela,
zebra-striping, estágio vazio da Kill Chain) que precisei corrigir ao
implementar isso.

## Django Admin

Disponível em `/admin/` para usuários `is_staff`. Serve como ferramenta
administrativa de contingência — a operação do dia a dia deve ocorrer pela
interface principal, conforme os catálogos forem implementados nas
próximas fases.

## Catálogos de Configurações (Fase 2)

Modelo compartilhado `ConfigurableOption` (abstrato): `name`, `code`
(slug único, auto-gerado do nome se deixado em branco), `description`,
`color`, `icon`, `order`, `is_active`. Usado por `Technology`, `Status`,
`Severity`, `Category`, `Tag`, `RuleType`.

- **Status** tem um campo `scope` (em quais entidades pode ser usado:
  Cliente, Regra, Caso de Uso por cliente, Fonte de Log por cliente, Gap) e
  um campo `category` com uma lista **fixa** de valores internos (`ACTIVE`,
  `INACTIVE`, `TESTING`, `COVERED`, `PARTIAL`, `RECEIVING`, `OPEN`, ...). O
  nome exibido ("Em Homologação", "Aguardando Cliente") é livre; a lógica de
  negócio das próximas fases (cobertura, detecção inoperante) só vai ler
  `category`, nunca o texto digitado pelo administrador — ver
  `taxonomy/choices.py`.
- **Category** tem `applicable_to` (em quais catálogos pode ser usada:
  Tecnologia, Caso de Uso, Regra, Fonte de Log).
- **Severity** tem `weight` (peso numérico para ordenação/indicadores).
- **Framework**/**FrameworkControl** ficam fora do padrão genérico acima
  (framework → árvore de controles/técnicas, ex: MITRE ATT&CK → T1110) e
  têm views dedicadas.
- Gerenciamento apenas pelo grupo **ADMIN** (`/configuracoes/`, submenu da
  sidebar) e pelo Django Admin. Os demais grupos não têm permissão sobre o
  app `taxonomy` (ver `accounts/management/commands/setup_roles.py`).

Adicionar uma nova tecnologia, status, severidade, categoria, tag ou tipo
de regra é **sempre** um registro novo no catálogo — nunca uma alteração de
código.

## Clientes (Fase 3)

CRUD completo (`clients` app). Campos: `name`, `legal_name` (razão social,
opcional), `status` (FK para `taxonomy.Status`, filtrado por
`scope=CLIENT`), `notes`, `created_at`/`updated_at`. A página de detalhe já
reserva os blocos de Regras, Casos de Uso, Fontes de Log, Gaps, Cobertura e
Últimas Alterações — cada um mostrando "disponível a partir da Fase N" até
a fase correspondente ser implementada.

Busca por nome/razão social na listagem. Permissões seguem o padrão
operacional: `SOC_MANAGER` tem CRUD completo, `ANALYST` não exclui,
`VIEWER` só visualiza (`clients` já fazia parte de `OPERATIONAL_APPS` em
`setup_roles`).

### Nota de desenvolvimento: migrations e o bind mount

O serviço `web` agora monta o projeto inteiro (`.:/app`) além dos volumes
de estáticos/mídia. Isso existe por um motivo prático: sem esse mount,
qualquer `makemigrations` executado dentro do container (via `docker
compose exec`) grava o arquivo apenas na camada do container, não no
código-fonte no host — e some no próximo `--build`. Com o bind mount, o
arquivo gerado aparece direto em `taxonomy/migrations/`, `clients/migrations/`
etc. no seu disco, prontos para ir ao Git. Ao preparar para produção
(Fase 11), considere um `docker-compose.prod.yml` sem esse mount.

## Catálogo global vs. implementação por cliente (Fase 4)

Primeira aplicação concreta do padrão que vai se repetir em Casos de Uso
(Fase 5) e Regras:

```text
LogSource (catálogo global, ex: "Windows Security")
   └── ClientLogSource (client, log_source, status, último evento, obs.)
```

- `LogSource` existe **uma vez só** (`unique=True` em `name`), com
  categoria (`taxonomy.Category`, `applicable_to=LOG_SOURCE`) e tecnologia
  opcionais, e tags. Gerenciado em `/fontes-de-log/` (sidebar "Fontes de
  Log").
- `ClientLogSource` é a situação **daquele cliente específico** para uma
  fonte do catálogo: status (FK `taxonomy.Status`, `scope=CLIENT_LOG_SOURCE`
  — ex: Recebendo/Sem Log/Não Integrado), último evento, observações.
  `unique_together(client, log_source)` impede duplicar a mesma fonte para
  o mesmo cliente. Gerenciado direto na página do cliente (`/clientes/<id>/`),
  não tem página própria.
- Excluir uma `LogSource` do catálogo é bloqueado (`on_delete=PROTECT`)
  enquanto algum cliente a estiver usando — preserva a integridade que o
  catálogo global existe para garantir.

## Casos de Uso, cobertura e Templates (Fase 5)

Mesmo padrão da Fase 4, agora para Casos de Uso:

```text
UseCase (catálogo global, ex: "UC-001 Brute Force")
   └── ClientUseCase (client, use_case, status, criticidade, responsável, última validação)
```

- `UseCase.code` é único (`UC-001`). `category` (Categoria), `threat`,
  `protects`, `tags` e `framework_controls` (MITRE ATT&CK e futuros
  frameworks) seguem o catálogo global.
- `ClientUseCase.status` usa `scope=CLIENT_USE_CASE` (Coberto/Parcial/Não
  Coberto/Não Aplicável, via `category` interno). `criticality` reaproveita
  o catálogo `Severity`. `owner` é o responsável (usuário do sistema).

### Cobertura — já calculada, não só modelada

A página do cliente mostra, com a fórmula definida no requisito:

```text
Casos cobertos
-----------------------------
Casos aplicáveis   (exclui os marcados "Não Aplicável")
```

Implementado em `catalog/services.py::compute_use_case_coverage` e testado
para os casos de borda (zero aplicáveis, tudo não-aplicável, status
ausente). A métrica nunca aparece sem dizer o que está contando.

### Templates de Implementação

```text
ImplementationTemplate ("Windows Server")
   ├── TemplateLogSource × N   (ex: Windows Security, Sysmon)
   └── TemplateUseCase × N     (ex: UC Brute Force, criticidade padrão opcional)
```

Gerenciado em `/templates/`. Na página do cliente, um seletor "Aplicar
template..." roda `catalog/services.py::apply_template_to_client`, que
cria as associações (`ClientLogSource`/`ClientUseCase`) que ainda não
existirem para aquele cliente — **aditivo e idempotente**: aplicar o
mesmo template duas vezes não duplica nem sobrescreve o que já foi
preenchido manualmente (testado).

## Regras (Fase 6)

`detections.Rule` é o inventário operacional principal. Campos fixos
(cliente, tecnologia, tipo, fonte de log, severidade SOC, status,
categoria, casos de uso — M2M, frameworks/técnicas — M2M, tags, datas de
revisão) seguem os catálogos das fases anteriores; `internal_id` é
digitado manualmente (decisão tomada com o usuário) e `original_level`
guarda o rótulo de severidade nativo da ferramenta como texto livre, já
que cada vendor nomeia esse campo de um jeito.

### Filtros e busca

`/regras/` filtra por cliente, tecnologia, status, severidade, fonte,
caso de uso, categoria, framework, tag, revisão (pendente/sem data) e
busca textual (ID, nome, ID na ferramenta, descrição) — tudo combinável
via querystring, preservada na paginação com o tag nativo do Django 5.2
`{% querystring %}`.

### Colunas configuráveis

Botão "Configurar colunas" (modal) grava `RuleColumnPreference` por
usuário (`ArrayField`, sem tabela extra por coluna). Sem preferência
salva, usa `DEFAULT_RULE_COLUMNS`; selecionar zero colunas também cai no
padrão, nunca numa tabela vazia de cabeçalhos.

### Verificações de inconsistência (calculadas em tempo de consulta)

Implementadas em `detections/services.py`, sem workers/filas:

- **Possivelmente inoperante**: regra `ATIVA` (via `status.category`) cuja
  `ClientLogSource` correspondente está `NOT_RECEIVING`/`NOT_INTEGRATED`
  — ou nem existe. Um link ainda sem status classificado **não** é tratado
  como quebrado (não presume problema antes de alguém classificar).
- **Revisão pendente**: `next_review_at` no passado. Badge nas páginas de
  lista e detalhe da regra.
- **Inconsistência de cobertura**: `ClientUseCase` marcado `COBERTO` sem
  nenhuma Regra `ATIVA` ligada ao mesmo caso de uso para aquele cliente —
  badge agora visível na tabela de Casos de Uso da página do cliente.

### Importação CSV

`/regras/importar/`. Colunas obrigatórias: `rule_id, name, client,
technology`; opcionais: `log_source, level, severity, status,
description`. Casa por nome (case-insensitive) com os catálogos já
cadastrados; cliente/tecnologia não encontrados = erro (linha pulada);
fonte/severidade/status não encontrados = aviso (campo fica em branco,
linha segue). Cada linha roda em sua própria transação — uma linha
inválida não aborta o restante do arquivo. Mesmo `rule_id` duas vezes =
atualiza em vez de duplicar.

## Gaps (Fase 7)

`gaps.Gap`: código único (`GAP-004`, manual, mesmo padrão do `internal_id`
da Regra), cliente, título, descrição, impacto, criticidade (reaproveita
`Severity`), responsável, status, recomendação, datas de abertura/conclusão,
observações. Relacionamentos opcionais: fonte de log, caso de uso, regra
(todos `on_delete=SET_NULL` — um Gap nunca desaparece por causa de algo
que ele só referenciava de forma leve).

- **Responsável é configurável**: novo catálogo `taxonomy.ResponsibleParty`
  (SOC / Cliente / Fornecedor, por exemplo) — mesmo padrão `ConfigurableOption`
  dos demais, exposto em "Configurações → Responsáveis", admin-only.
- `status` usa `scope=GAP` (categorias internas `OPEN`/`CLOSED`).
- No formulário, os campos opcionais de Caso de Uso e Fonte de Log são
  filtrados para mostrar apenas os já associados ao cliente selecionado
  (evita escolher algo de outro cliente por engano); sem cliente definido,
  mostram tudo.
- Página do cliente: contagem de gaps e de gaps em aberto, com link para a
  lista já filtrada por aquele cliente.

## Dashboard e Cyber Kill Chain (Fase 10, adiantada)

A pedido do usuário ("não sei por onde começar" + "quero um dash bonitão
com Kill Chain"), pulamos a Fase 8 (Campos Personalizados) e a Fase 9
(Histórico) para entregar o Dashboard real. A Fase 9 foi implementada
depois como POC e aprovada como fase definitiva (ver seção própria mais
abaixo); a Fase 8 continua pendente, no roteiro mais abaixo.

### Fluxo recomendado de cadastro

É a pergunta mais importante que faltava responder: **por onde eu começo?**
Agora ela tem duas respostas:

1. **No app**: o próprio Dashboard (`/`) mostra o fluxo de 7 passos com
   links diretos. Se o sistema ainda não tem clientes/regras, aparece
   expandido por padrão (ensina a interface em vez de mostrar uma tela
   vazia); depois que há dados, fica recolhido como referência.
2. **Aqui**: Configurações → Clientes → Fontes de Log (catálogo) → Casos
   de Uso (catálogo) → Templates (opcional, agrupa os dois anteriores) →
   Regras → Gaps. Cada passo depende do anterior existir.

### Dashboard (`dashboard` app)

Filtros por cliente e tecnologia. Cards: regras (total/ativas/em
teste/em revisão/desativadas/revisão pendente), casos de uso
(total/cobertos/parciais/não cobertos), gaps (abertos/total), fontes sem
log. Gráficos (Chart.js, via `json_script` — sem API própria, os dados
vão direto do contexto da view para o template): regras por status, por
severidade, por tecnologia, cobertura dos casos de uso, casos de uso por
categoria, gaps por criticidade. Toda a agregação está em
`dashboard/services.py::build_dashboard`, sem workers/cache — calculado
na hora, como as demais verificações do sistema.

Um widget extra, fora do pedido original mas direto ao ponto de "o que
estamos protegendo": ranking das ameaças (`Rule.threat`) mais cobertas
pelas regras do filtro atual.

### Cyber Kill Chain

Em vez de criar um modelo novo, a Kill Chain (Lockheed Martin, 7 fases)
é só mais um **Framework** — o mesmo conceito já usado para MITRE
ATT&CK desde a Fase 2. Rodar uma vez:

```bash
docker compose exec web python manage.py seed_kill_chain
```

Isso cria o Framework "Cyber Kill Chain" + as 7 fases como
`FrameworkControl` (idempotente, pode rodar de novo sem duplicar). Depois
disso, marcar uma regra com uma fase é exatamente o mesmo fluxo de marcar
uma técnica MITRE: no formulário da Regra, campo "Técnicas/Controles" —
que agora agrupa as opções por framework (`<optgroup>`), para MITRE e
Kill Chain não virarem uma lista achatada confusa conforme o catálogo
MITRE crescer.

O Dashboard mostra as 7 fases com a contagem de regras de cada uma
(respeitando os filtros de cliente/tecnologia); clicar numa fase abre
`/regras/?stage=<id>`, já filtrado. Se o comando de seed nunca foi
rodado, o Dashboard mostra um aviso com o comando a executar em vez de
simplesmente omitir o bloco.

## Busca global (bônus, fora do roteiro original)

Caixa de busca fixa na sidebar (`search` app, `/buscar/`): um único termo
pesquisa ao mesmo tempo em Cliente (nome/razão social), Regra (ID interno,
nome, ID na ferramenta, descrição), Gap (código, título, descrição), Caso
de Uso (código, nome, descrição) e Fonte de Log (nome, descrição).
Resultados agrupados por categoria, limitados a 8 por categoria com link
"ver todos" para a listagem já filtrada pelo mesmo termo (reaproveita o
`?q=` que cada listagem já aceitava).

- **Cada categoria só aparece se o usuário tiver a permissão `view_*`
  correspondente** (`clients.view_client`, `detections.view_rule`,
  `gaps.view_gap`, `catalog.view_usecase`, `catalog.view_logsource`) — o
  mesmo controle que a listagem dedicada de cada entidade já aplica, só
  verificado aqui por categoria em vez de via um único
  `PermissionRequiredMixin` (não existe uma permissão só que cubra as
  cinco entidades).
- **Caso de Uso e Fonte de Log não têm página de detalhe própria** (só
  listagem/edição) — por isso seus resultados apontam para a listagem já
  filtrada pelo código/nome exato, nunca para a tela de edição, que exige
  permissão de `change` e quebraria (403) para quem só tem `view` (ex:
  grupo VIEWER).

## Exportação de relatório por cliente (bônus, fora do roteiro original)

Botão "Exportar relatório" na página do cliente (`reports` app), com duas
opções:

- **PDF** (`/clientes/<id>/relatorio.pdf`, via ReportLab): resumo (regras,
  regras ativas, gaps em aberto, % de cobertura de casos de uso) + tabela
  de Regras + tabela de Gaps. Pensado para mandar ao cliente final, que
  nunca tem acesso ao sistema.
- **Excel** (`/clientes/<id>/relatorio.xlsx`, via openpyxl): mesmos dados
  em 5 abas (Resumo, Regras, Gaps, Casos de Uso, Fontes de Log) — útil para
  quem quer filtrar/pivotar os dados em vez de só ler.

Mesma permissão que já protege a página do cliente (`clients.view_client`)
— nenhum dado novo é exposto, só reorganizado em formato de arquivo.
`reports/services.py::build_client_report` monta os dados uma única vez;
`reports/pdf.py` e `reports/excel.py` só sabem renderizar, não consultam o
banco diretamente.

## Notificações por e-mail (bônus, fora do roteiro original)

Comando `python manage.py send_digest` (`notifications` app): varre Regras
com `next_review_at` vencido e Gaps abertos sem nenhuma alteração há 14+
dias (`notifications/services.py::STALE_GAP_DAYS`) e manda um e-mail de
texto simples para todo usuário ativo dos grupos **ADMIN**/**SOC_MANAGER**
que tenha e-mail cadastrado. Sem nada para notificar, não envia e-mail
nenhum (sem spam de "tudo certo").

- **Sem worker/fila**: assim como o resto do sistema, não há
  Celery/Redis/cron embutido — o comando é feito para ser chamado por um
  agendador externo. Exemplo de crontab do host rodando todo dia às 8h:
  ```
  0 8 * * * cd /caminho/do/soc-control && docker compose exec -T web python manage.py send_digest
  ```
- **Configuração de e-mail** via `.env` (ver `.env.example`): sem
  `DJANGO_EMAIL_BACKEND` definido, usa o backend de console (só imprime no
  log do container `web`, nunca falha por falta de SMTP) — troque para
  `django.core.mail.backends.smtp.EmailBackend` e configure
  `DJANGO_EMAIL_HOST`/`DJANGO_EMAIL_PORT`/`DJANGO_EMAIL_HOST_USER`/
  `DJANGO_EMAIL_HOST_PASSWORD` em produção. `DJANGO_SITE_URL` é usado para
  montar os links dentro do corpo do e-mail (o comando roda fora de uma
  requisição HTTP, então não há `request.build_absolute_uri()`).

## Exportação para o MITRE ATT&CK Navigator (bônus, fora do roteiro original)

Na página de um Framework (`/frameworks/<id>/`), botão "Exportar camada
ATT&CK Navigator (JSON)" — gera uma [camada do Navigator](https://mitre-attack.github.io/attack-navigator/)
(`taxonomy/services.py::build_navigator_layer`) com uma entrada por
`FrameworkControl.code` (ex: `T1110`), pontuada pela quantidade de Regras
vinculadas a ele — mesma contagem que o widget da Cyber Kill Chain no
Dashboard já usa por fase, só generalizada para qualquer Framework cujos
códigos de controle sejam IDs de técnica do ATT&CK. Filtro opcional por
cliente (`?client=<id>`) no formulário da própria página. Controles sem
nenhuma regra vinculada não entram no arquivo, para o heatmap no Navigator
mostrar só o que realmente está coberto.

## Histórico de Alterações (Fase 9)

`audit` app. Começou como POC para validar se o modelo de auditoria
compensava antes de virar fase definitiva do roteiro — validado e
aprovado, badge "POC" removido de toda a interface onde aparecia
(listagem própria em `/historico/`, aba "Histórico" na página do cliente
e bloco "Últimas alterações" na página de Regra e de Gap).

- **Escopo deliberadamente reduzido**: só rastreia `Cliente`, `Regra` e
  `Gap` (`audit/signals.py::TRACKED_MODELS`), não os catálogos de
  Configurações — é o que uma revisão de governança pergunta primeiro.
- **Baseado em signals** (`pre_save`/`post_save`/`post_delete`/`m2m_changed`),
  sem fila nem worker: cada `save()`/`delete()` já grava o registro na
  mesma transação. `audit/middleware.py::CurrentUserMiddleware` guarda o
  usuário da requisição numa thread-local, já que um model signal não tem
  acesso ao `request`.
- **Diff real**: `AuditLog.changes` guarda só os campos que de fato
  mudaram (`{campo: [antigo, novo]}`); criação e exclusão guardam,
  respectivamente, nada (o próprio registro já diz "criado") e um
  snapshot completo (o que existia antes de ser excluído). Campos
  many-to-many (casos de uso, técnicas MITRE, tags) são tratados à parte
  via `m2m_changed`, porque nunca aparecem no diff de um `save()` normal.
- **Cuidado que valeu a pena testar**: excluir um Cliente que tem Regras/
  Gaps dispara um cascade-delete; sem tratamento, cada exclusão em
  cascata criava um novo registro de auditoria referenciando um Cliente
  que seria apagado na mesma transação — `ForeignKeyViolation` real, não
  só um detalhe cosmético. Resolvido rastreando "clientes em exclusão"
  (`_clients_being_deleted`) para essas entradas não referenciarem o FK
  nesse caso específico; a exclusão do Cliente aparece no histórico assim
  mesmo, só sem o vínculo de FK (óbvio, já que o cliente não existe mais).
  Tem teste de regressão dedicado
  (`audit/tests.py::AuditLogCreateUpdateDeleteTests::test_deleting_a_client_with_rules_and_gaps_does_not_violate_the_fk`).
- **Somente leitura por design**: `AuditLogAdmin` bloqueia add/change/
  delete mesmo para quem tem a permissão Django correspondente; o
  `setup_roles` só concede `view_auditlog` para todo mundo (inclusive
  SOC_MANAGER, que normalmente tem CRUD completo nas entidades
  operacionais) — o histórico não é editável por ninguém pela interface.

## Roteiro de fases

1. ✅ Base Django, Docker, PostgreSQL, autenticação.
2. ✅ Configurações: Tecnologias, Status, Severidades, Categorias, Tags,
   Tipos de Regra, Frameworks, Responsáveis.
3. ✅ Clientes.
4. ✅ Catálogo de Fontes de Log + implementação por cliente.
5. ✅ Catálogo de Casos de Uso + implementação por cliente + Templates de
   Implementação.
6. ✅ Regras (+ importação CSV, verificações de inconsistência, colunas
   configuráveis).
7. ✅ Gaps.
8. Campos personalizados. *(pendente — pulamos para entregar o Dashboard primeiro)*
9. ✅ Histórico (implementado como POC, validado e aprovado como fase definitiva).
10. ✅ Dashboard (+ Cyber Kill Chain, bônus fora do roteiro original).
11. Hardening, testes, documentação final.
