# 03 — Funcionalidades (tela → URL → permissão → código)

Para cada funcionalidade: o que faz, onde está e quais regras de negócio
aplica. Nomes de URL no formato `namespace:nome` (use com `{% url %}` /
`reverse()`).

## 1. Login, sessão e usuários — `accounts`

| URL | Nome | Permissão | View |
|---|---|---|---|
| `/login/` | `login` | - | `ThrottledLoginView` |
| `/logout/` (POST) | `logout` | - | `LogoutView` do Django |
| `/usuarios/` | `user_list` | `auth.view_user` | `UserListView` |
| `/usuarios/novo/` | `user_create` | `auth.add_user` | `UserCreateView` |
| `/usuarios/<pk>/editar/` | `user_update` | `auth.change_user` | `UserUpdateView` |
| `/usuarios/<pk>/senha/` | `user_password_reset` | `auth.change_user` | `UserPasswordResetView` |
| `/usuarios/<pk>/excluir/` | `user_delete` | `auth.delete_user` | `UserDeleteView` |

- Bloqueio após `MAX_LOGIN_ATTEMPTS = 10` falhas em `THROTTLE_WINDOW_SECONDS = 15 min`, por IP.
- Login bem-sucedido zera o contador. Após login → `dashboard`.
- `auth.*_user` só é concedida ao grupo ADMIN por `setup_roles` (o `auth` app não entra em `OPERATIONAL_APPS`/`CONFIG_APPS`) - então só ADMIN vê o link "Usuários" na sidebar (`{% if perms.auth.view_user %}`) e passa pelas views, as demais recebem 403.
- `PlatformUserCreateForm`/`PlatformUserUpdateForm` (`accounts/forms.py`) cobrem usuário, nome, e-mail, `is_active` e grupos; senha é sempre definida/redefinida por um form separado (`PlatformUserPasswordResetForm`, baseado em `SetPasswordForm` - admin troca a senha de outra pessoa sem saber a antiga).
- `is_superuser` fica de fora de propósito: continua só pelo `/admin/`, por ignorar todo o sistema de permissões.
- Duas travas contra lockout, aplicadas nas views (não só escondidas no template): não dá para desativar (`UserUpdateView`) nem excluir (`UserDeleteView`) a própria conta por essa tela.
- Excluir usuário é permitido (sem `PROTECT`): `AuditLog.user` e `ClientUseCase.owner` usam `SET_NULL`, `RuleColumnPreference.user` usa `CASCADE` - histórico de auditoria é preservado, só perde a referência ao autor. Para só bloquear acesso sem perder essa referência, prefira editar o usuário e desmarcar "Ativo".

## 2. Dashboard — `dashboard`

| URL | Nome | Permissão |
|---|---|---|
| `/` | `dashboard` | só login |

- Filtros opcionais `?client=<id>&technology=<id>` (validados com `parse_int_or_none`). O filtro de tecnologia afeta só as regras.
- Toda a agregação está em `dashboard/services.py::build_dashboard`, que devolve `{cards, charts, kill_chain}`:
  - **cards**: totais de regras por `status.category`, revisões pendentes, casos de uso cobertos/parciais/não cobertos, gaps totais/abertos, fontes sem dados.
  - **charts**: listas `[{label, value, color}]` via `_grouped()` (GROUP BY). A cor vem do catálogo; se não houver, usa `FALLBACK_PALETTE`.
  - **kill_chain**: se existir o Framework `"Cyber Kill Chain"`, 1 item por etapa com contagem de regras e link para `/regras/?stage=<id>`.
- Template: `dashboard/templates/dashboard/dashboard.html` (Chart.js). Mostra o fluxo de primeiros passos quando não há cliente ou regra (`is_new_setup`).

## 3. Clientes — `clients`

| URL | Nome | Permissão |
|---|---|---|
| `/clientes/` | `clients:client_list` | `clients.view_client` |
| `/clientes/novo/` | `clients:client_create` | `clients.add_client` |
| `/clientes/<pk>/` | `clients:client_detail` | `clients.view_client` |
| `/clientes/<pk>/editar/` | `clients:client_update` | `clients.change_client` |
| `/clientes/<pk>/excluir/` | `clients:client_delete` | `clients.delete_client` |

- Listagem paginada (25), busca `?q=` em nome/razão social.
- **Página de detalhe é o hub do cliente** (abas Visão Geral / Fontes de Log / Casos de Uso / Histórico). O contexto é montado em `ClientDetailView.get_context_data`:
  - `coverage` ← `catalog.services.compute_use_case_coverage`
  - `inconsistent_use_case_ids` ← `detections.services.use_case_coverage_inconsistencies`
  - `open_gaps_count`, `templates` (para "Aplicar template")
  - `audit_entries` (só se o usuário tiver `audit.view_auditlog`)
- Botões de exportar relatório PDF/Excel (ver §9).

## 4. Fontes de Log e Casos de Uso — `catalog`

### Catálogo global

| URL | Nome | Permissão |
|---|---|---|
| `/fontes-de-log/` (+ `novo/`, `<pk>/editar/`, `<pk>/excluir/`) | `catalog:logsource_*` | `catalog.<ação>_logsource` |
| `/casos-de-uso/` (+ idem) | `catalog:usecase_*` | `catalog.<ação>_usecase` |

Não há página de detalhe para estes itens: a listagem filtrada (`?q=`) é usada como "detalhe".

### Vínculos por cliente (operados na página do cliente)

| URL | Nome |
|---|---|
| `/clientes/<client_pk>/fontes-de-log/novo/` | `catalog:clientlogsource_create` |
| `/clientes/fontes-de-log/<pk>/editar/` · `/excluir/` | `catalog:clientlogsource_update` · `_delete` |
| `/clientes/<client_pk>/casos-de-uso/novo/` | `catalog:clientusecase_create` |
| `/clientes/casos-de-uso/<pk>/editar/` · `/excluir/` | `catalog:clientusecase_update` · `_delete` |

- Os forms (`ClientLogSourceForm`, `ClientUseCaseForm`) recebem `client=` e **escondem itens já vinculados** ao cliente, filtram status por escopo e só oferecem itens de catálogo ativos.

### Templates de Implementação

| URL | Nome | Permissão |
|---|---|---|
| `/templates/…` (CRUD + detalhe) | `catalog:template_*` | `catalog.<ação>_implementationtemplate` |
| `/templates/<template_pk>/fontes-de-log/novo/`, `/casos-de-uso/novo/` | `catalog:templatelogsource_create`, `templateusecase_create` | `add_template*` |
| `/clientes/<client_pk>/aplicar-template/` (POST) | `catalog:apply_template` | `catalog.add_clientusecase` |

`apply_template_to_client` cria só o que falta (idempotente, nunca sobrescreve o que foi preenchido à mão).

### Regra de negócio: cobertura

`catalog/services.py::compute_use_case_coverage(client)`:

```text
percentual = vínculos com status COVERED / vínculos com status definido e ≠ NOT_APPLICABLE
```

Vínculos sem status ficam fora da conta. Sem nenhum aplicável → `percentage = None` (a interface mostra "—", nunca um 0% enganoso).

## 5. Regras — `detections`

| URL | Nome | Permissão |
|---|---|---|
| `/regras/` | `detections:rule_list` | `detections.view_rule` |
| `/regras/novo/` | `detections:rule_create` | `detections.add_rule` |
| `/regras/<pk>/` | `detections:rule_detail` | `detections.view_rule` |
| `/regras/<pk>/editar/` · `/excluir/` | `rule_update` · `rule_delete` | `change_rule` · `delete_rule` |
| `/regras/importar/` | `detections:rule_import` | `detections.add_rule` |
| `/regras/colunas/` (POST) | `detections:rule_columns` | só login |

### Listagem

- Filtros em `RuleFilterForm` (`q`, cliente, tecnologia, status, severidade, fonte, caso de uso, categoria, framework, tag, `review_status=overdue|undated`) + `?stage=<FrameworkControl id>` (vindo do dashboard). Tudo combinável e preservado na paginação com `{% querystring %}`.
- Colunas visíveis por usuário (`RuleColumnPreference`); sem preferência → `DEFAULT_RULE_COLUMNS`.
- Coluna "Alertas" com os badges das verificações abaixo.

### Regras de negócio (`detections/services.py`)

| Função | Regra |
|---|---|
| `rule_is_review_overdue(rule)` | `next_review_at` existe e é anterior a hoje. |
| `rule_is_possibly_inoperative(rule)` | status `ACTIVE` **e** tem `log_source` **e** o `ClientLogSource` do mesmo cliente está `NOT_RECEIVING`/`NOT_INTEGRATED` **ou não existe**. Vínculo existente sem status **não** dispara. |
| `use_case_coverage_inconsistencies(client)` | `ClientUseCase` com status `COVERED` sem nenhuma regra `ACTIVE` do mesmo cliente ligada àquele caso de uso. |

### Importação CSV (`import_rules_from_csv`)

- UTF-8 (aceita BOM). Obrigatórias: `rule_id, name, client, technology`. Opcionais: `log_source, level, severity, status, description`.
- Casamento por nome, sem diferenciar maiúsculas. Cliente/tecnologia inexistente = **erro** (linha pulada). Fonte/severidade/status inexistente = **aviso** (campo em branco). Status só é aceito se tiver escopo RULE.
- `update_or_create` por `internal_id`: reimportar atualiza.
- Uma transação por linha: uma linha ruim não derruba o arquivo.
- Limite `MAX_CSV_ROWS = 5000`.
- Retorna `{created, updated, errors[], warnings[]}`, exibido na própria tela.

## 6. Gaps — `gaps`

| URL | Nome | Permissão |
|---|---|---|
| `/gaps/` (+ `novo/`, `<pk>/`, `<pk>/editar/`, `<pk>/excluir/`) | `gaps:gap_*` | `gaps.<ação>_gap` |

- `/gaps/novo/?client=<id>` já vem com o cliente selecionado (link da página do cliente).
- `GapForm` limita caso de uso / fonte de log / regra aos **vinculados ao cliente escolhido** (prevenção de erro, não controle de acesso).
- "Em aberto" = qualquer status cuja categoria não seja `CLOSED`.

## 7. Configurações e Frameworks — `taxonomy`

| URL | Nome | Permissão |
|---|---|---|
| `/configuracoes/` | `taxonomy:config_home` | login (cards filtrados por `view_<model>`) |
| `/configuracoes/<catalog>/` (+ `novo/`, `<pk>/editar/`, `<pk>/excluir/`) | `taxonomy:catalog_*` | `taxonomy.<ação>_<model>` |
| `/frameworks/…` | `taxonomy:framework_*` | `taxonomy.<ação>_framework` |
| `/frameworks/<framework_pk>/controles/novo/`, `/controles/<pk>/editar|excluir/` | `taxonomy:frameworkcontrol_*` | `taxonomy.<ação>_frameworkcontrol` |
| `/frameworks/<pk>/navigator/` | `taxonomy:framework_navigator_export` | `taxonomy.view_framework` |

- **Catálogos simples são genéricos**: um único conjunto de views (`CatalogListView`, `CatalogCreateView`…) serve todos. O `<catalog>` da URL é a chave de `taxonomy/registry.py::CATALOGS` (`tecnologias`, `status`, `severidades`, `categorias`, `tags`, `tipos`, `responsaveis`), que define model, form, rótulo, ícone, descrição e colunas. `CatalogPermissionMixin` resolve o model e checa a permissão dinamicamente.
- **Export ATT&CK Navigator**: `taxonomy/services.py::build_navigator_layer` gera layer JSON v4.5, `score` = nº de regras por controle; aceita `?client=` e `?technology=`. Controles sem regra são omitidos.
- `python manage.py seed_kill_chain` cria o framework "Cyber Kill Chain" com as etapas KC1–KC7 (idempotente).

## 8. Histórico — `audit`

| URL | Nome | Permissão |
|---|---|---|
| `/historico/` | `audit:auditlog_list` | `audit.view_auditlog` |

- Filtros: texto, cliente, ação, entidade (derivada de `TRACKED_MODELS`), usuário. Paginação 50.
- Também aparece como aba na página do cliente (até 50 entradas) e como bloco "Últimas alterações" na regra e no gap (até 20).
- Formatação do diff: filtro `audit_changes` (`audit/templatetags/audit_extras.py`).
- Mecânica interna: ver `01-arquitetura.md §8`.

## 9. Relatório por cliente — `reports`

Há duas versões, ambas no botão "Exportar relatório" da página do cliente:

| Versão | URL | Nome | Permissão |
|---|---|---|---|
| **Para o cliente** (PDF) | `/clientes/<pk>/relatorio-cliente.pdf` | `reports:client_facing_report_pdf` | `clients.view_client` |
| Interna (PDF) | `/clientes/<pk>/relatorio.pdf` | `reports:client_report_pdf` | `clients.view_client` |
| Interna (Excel) | `/clientes/<pk>/relatorio.xlsx` | `reports:client_report_excel` | `clients.view_client` |

**Versão interna** (equipe do SOC, completa):

- `reports/services.py::build_client_report` → dict com cliente, cobertura, regras (com flags de alerta), gaps, vínculos, contadores.
- `reports/pdf.py::render_client_report_pdf` (ReportLab): resumo + tabelas de Regras e Gaps.
- `reports/excel.py` (openpyxl): abas Resumo, Regras, Gaps, Casos de Uso, Fontes de Log.

**Versão para o cliente** (pode ser enviada como está):

- `reports/services.py::build_client_facing_report` → dict próprio; `reports/pdf.py::render_client_facing_report_pdf` renderiza.
- Seções: resumo executivo → ações pendentes do cliente → cobertura por caso de uso → cobertura por framework → detecções ativas → itens em tratamento pelo SOC/terceiros.
- **Nunca inclui** dados internos: ID interno/do vendor da regra, notas, analista dono do caso de uso, flags de inoperância/revisão, regras que não estão ativas.
- Regras de negócio:
  - "Ações pendentes do cliente" = gaps abertos cujo Responsável tem `is_client=True` (marcado em Configurações › Responsáveis — nunca pelo nome) + fontes de log com status `NOT_RECEIVING`/`NOT_INTEGRATED`, com quantas detecções **ativas** dependem de cada uma.
  - Casos de uso `NOT_APPLICABLE` não aparecem.
  - Cobertura por framework: um controle está coberto se tem ≥ 1 regra **ativa** deste cliente. Frameworks com até `FRAMEWORK_FULL_LIST_MAX_CONTROLS` (30) controles são listados inteiros (ex.: Kill Chain); maiores (ex.: MITRE completo) listam só os cobertos.

Para incluir um dado novo: adicione-o no service da versão certa e depois em **cada** renderizador que deve exibi-lo. Antes de pôr algo na versão do cliente, pergunte: "posso mostrar isso ao cliente?".

## 10. Busca global — `search`

| URL | Nome | Permissão |
|---|---|---|
| `/buscar/?q=` | `search:results` | login; cada categoria exige o `view_*` correspondente |

- Caixa na sidebar. Busca Clientes, Regras, Gaps, Casos de Uso e Fontes de Log; até `RESULTS_PER_CATEGORY = 8` por categoria + "ver todos" (listagem filtrada pelo mesmo `?q=`).
- Cada categoria é um método `_<entidade>_results` que devolve `{label, icon, see_all_url, total, items}`.

## 11. Digest por e-mail — `notifications`

- Comando: `python manage.py send_digest` (agendar no cron do host).
- `notifications/services.py`: `overdue_rules()` (revisão vencida) e `stale_gaps()` (gap aberto sem `save()` há `STALE_GAP_DAYS = 14` dias). `build_digest()` devolve `None` se não houver nada, e aí nenhum e-mail é enviado.
- Destinatários: usuários ativos com e-mail dos grupos ADMIN e SOC_MANAGER.
- Links do e-mail usam `SITE_URL` (o comando roda fora de requisição).
- Backend padrão é o de console (só imprime no log). Configure SMTP pelo `.env`.

## 12. Django Admin

`/admin/` para `is_staff`. É ferramenta de contingência; criar/editar/desativar/excluir usuário e redefinir senha já têm tela própria (§1). **Grupos** (o conjunto de permissões de cada papel, mantido por `setup_roles`) e conceder `is_superuser` continuam só pelo `/admin/` - de propósito, já que superusuário ignora todo o sistema de permissões. `AuditLogAdmin` é somente leitura para todos.
