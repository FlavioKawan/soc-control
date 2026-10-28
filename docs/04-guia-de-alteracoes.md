# 04 — Guia de alterações (receitas)

Cada receita lista **todos** os pontos que precisam ser tocados. Se a sua
alteração não se encaixa em nenhuma, use a receita mais próxima e a
[checklist final](#checklist-final-antes-de-entregar).

Antes de qualquer receita, responda:

1. **É dado ou é código?** Nova tecnologia, status, severidade, categoria,
   tag, tipo de regra, responsável, framework/técnica → **cadastro na tela
   de Configurações, sem mudar código**. Só mude código se a *estrutura* ou
   a *regra* mudar.
2. **Em qual app isso mora?** Veja a tabela de responsabilidades em
   `01-arquitetura.md §3`. Não crie app novo para algo que cabe num existente.
3. **Vou mudar a arquitetura?** (nova camada, nova dependência de infra,
   mudar padrão de view/permissão) → **escreva a justificativa técnica
   antes** e alinhe com o responsável pelo projeto.

---

## Índice

- [A. Adicionar um campo a uma entidade existente](#a-adicionar-um-campo-a-uma-entidade-existente)
- [B. Adicionar um novo catálogo de configuração](#b-adicionar-um-novo-catálogo-de-configuração-simples)
- [C. Adicionar uma nova semântica de Status](#c-adicionar-uma-nova-semântica-de-status-statuscategory)
- [D. Criar uma nova entidade operacional (app novo)](#d-criar-uma-nova-entidade-operacional-app-novo)
- [E. Adicionar/alterar uma regra de negócio ou verificação](#e-adicionaralterar-uma-regra-de-negócio-ou-verificação)
- [F. Adicionar coluna configurável na lista de Regras](#f-adicionar-coluna-configurável-na-lista-de-regras)
- [G. Adicionar filtro numa listagem](#g-adicionar-filtro-numa-listagem)
- [H. Novo indicador ou gráfico no Dashboard](#h-novo-indicador-ou-gráfico-no-dashboard)
- [I. Rastrear um model novo no Histórico](#i-rastrear-um-model-novo-no-histórico)
- [J. Incluir entidade na Busca global](#j-incluir-entidade-na-busca-global)
- [K. Incluir dado no relatório PDF/Excel](#k-incluir-dado-no-relatório-pdfexcel)
- [L. Nova coluna na importação CSV de regras](#l-nova-coluna-na-importação-csv-de-regras)
- [M. Alterar permissões de um papel](#m-alterar-permissões-de-um-papel)
- [N. Nova tarefa agendada / comando](#n-nova-tarefa-agendada--comando)
- [O. Nova variável de ambiente / configuração](#o-nova-variável-de-ambiente--configuração)
- [P. Mudanças de interface (template/CSS/menu)](#p-mudanças-de-interface-templatecssmenu)

---

## A. Adicionar um campo a uma entidade existente

Exemplo: campo `mitigation` em `Rule`.

1. **Model** — `detections/models.py`: adicione o campo. Texto opcional →
   `blank=True`; FK → escolha `on_delete` segundo `02-modelo-de-dados.md §4`;
   FK para Status/Category → filtre no form, não no model.
2. **Migration** — `docker compose exec web python manage.py makemigrations detections`
   e versione o arquivo gerado.
3. **Form** — `detections/forms.py::RuleForm.Meta.fields`: inclua o campo na
   posição certa. Se opcional, confira o loop que marca `required = False`.
   Se for data, adicione o widget `DateInput(attrs={"type": "date"})`.
4. **Templates** — `rule_form.html` normalmente renderiza o form inteiro;
   confira. Exiba em `rule_detail.html`.
5. **Pontos que talvez precisem do campo**:
   - lista: coluna configurável → receita F;
   - filtro → receita G;
   - busca textual → `RuleListView.get_queryset` e `search/views.py::_rule_results`;
   - relatório → receita K;
   - import CSV → receita L.
6. **Histórico**: campos concretos (inclusive FK) de models rastreados entram
   no diff **automaticamente**. M2M novo precisa ser adicionado a
   `TRACKED_M2M_FIELDS` em `audit/signals.py`.
7. **Admin** — `detections/admin.py`, se fizer sentido em `list_display`/`list_filter`.
8. **Testes** — no mínimo: o form aceita/valida o campo; a regra de negócio
   que o usa, se houver.
9. **Docs** — atualize `02-modelo-de-dados.md`.

## B. Adicionar um novo catálogo de configuração simples

Exemplo: catálogo "Ambiente" (Produção, Homologação).

1. `taxonomy/models.py`: crie `class Environment(ConfigurableOption)` com
   `Meta(ConfigurableOption.Meta)` e `verbose_name`/`verbose_name_plural`.
2. `taxonomy/forms.py`: crie `EnvironmentForm(BootstrapModelForm)` com os
   campos padrão (`name, code, description, color, icon, order, is_active`).
3. `taxonomy/registry.py`: adicione uma entrada em `CATALOGS` com a chave de
   URL (slug em português, ex. `"ambientes"`), `model`, `form`, `label`,
   `icon` (Bootstrap Icons), `description` e `list_fields`.
   **Pronto: lista, criação, edição e exclusão já funcionam** em
   `/configuracoes/ambientes/`, sem view, URL ou template novos.
4. `taxonomy/admin.py`: `@admin.register(Environment)` herdando `ConfigurableOptionAdmin`.
5. `templates/base.html`: adicione o link no submenu `#configSubmenu`
   (`{% url 'taxonomy:catalog_list' catalog='ambientes' %}`).
6. Migration de `taxonomy`. Permissões: nada a fazer, `taxonomy` já está em
   `CONFIG_APPS`, então basta rodar `setup_roles`, o que o entrypoint já faz.
7. Use o catálogo: FK na entidade alvo (receita A), em geral `SET_NULL` e
   opcional. Se o catálogo for referenciado com `PROTECT`, a
   `CatalogDeleteView` já usa `ProtectedDeleteMixin`.
8. Testes: `taxonomy/tests.py` — acesso por ADMIN, 403 para quem não tem
   permissão.

> Se o catálogo tiver estrutura hierárquica (pai → filhos), ele **não** cabe
> no registry. Siga o modelo de `Framework`/`FrameworkControl`, com views
> dedicadas.

## C. Adicionar uma nova semântica de Status (`StatusCategory`)

Só é necessário quando a **lógica** precisa reconhecer um estado novo (ex.:
"Desativada temporariamente" que não deve contar como inoperante). Se for só
um nome diferente, cadastre um Status novo com uma categoria existente.

1. `taxonomy/choices.py`: adicione o valor no grupo certo, com um comentário
   de onde ele é usado.
2. Migration de `taxonomy` (mudança de `choices`).
3. Procure **todos** os pontos que interpretam categorias e decida o
   comportamento do valor novo em cada um:
   ```bash
   grep -rn "StatusCategory\." --include=*.py .
   ```
   Hoje: `catalog/services.py`, `detections/services.py`,
   `dashboard/services.py`, `reports/services.py`,
   `notifications/services.py`, `clients/views.py`.
4. Testes da regra de negócio afetada, cobrindo o valor novo.
5. Atualize a tabela de `02-modelo-de-dados.md §3.2`.

## D. Criar uma nova entidade operacional (app novo)

Use só quando a entidade é um domínio novo, e não um atributo ou vínculo de
algo existente.

1. `docker compose exec web python manage.py startapp <app>`. Nome curto, em
   inglês, plural se for coleção (siga `clients`, `gaps`).
2. `core/settings.py::INSTALLED_APPS`: adicione na seção "local apps",
   **depois** dos apps de que ele depende.
3. `models.py`: inclua `created_at`/`updated_at`, `Meta` com `verbose_name`
   em português e `ordering`, e `__str__`. FK para `Client` com `CASCADE` se
   a entidade pertence ao cliente. Status → FK `taxonomy.Status` + novo
   valor em `StatusScope` (receita C, passo 1).
4. `forms.py`: `BootstrapModelForm`, status filtrado por escopo (padrão em
   `01-arquitetura.md §5.3`), campos opcionais com `required = False`.
5. `services.py`: toda regra de negócio.
6. `views.py`: copie a estrutura de `gaps/views.py` (List/Detail/Create/
   Update/Delete com `LoginRequiredMixin, PermissionRequiredMixin`,
   `can_*` no contexto da lista, `paginate_by = 25`). Use
   `ProtectedDeleteMixin` se algo referenciar a entidade com `PROTECT`.
7. `urls.py`: `app_name = "<app>"`, caminhos em português
   (`"<plural>/"`, `"novo/"`, `"<int:pk>/editar/"`, `"<int:pk>/excluir/"`).
   Inclua em `core/urls.py`.
8. Templates em `<app>/templates/<app>/`, estendendo `base.html`. Copie
   `gaps/templates/gaps/*` como ponto de partida.
9. Navegação: link em `templates/base.html` **e** um ramo em
   `core/context_processors.py::active_nav` (por `app_name`).
10. Permissões: adicione o app em `OPERATIONAL_APPS` (ou na lista
    adequada) em `accounts/management/commands/setup_roles.py`.
11. Opcional, conforme o caso: Histórico (receita I), Busca (J), Dashboard
    (H), Relatório (K), aba na página do cliente
    (`clients/views.py::ClientDetailView`, com import local).
12. `admin.py` com o registro do model.
13. Testes: permissões por grupo (copie `clients/tests.py::ClientPermissionTests`),
    form scope e services.
14. Docs: `01` (tabela de apps e grafo), `02` (entidade), `03` (URLs).

## E. Adicionar/alterar uma regra de negócio ou verificação

Exemplo: "regra sem caso de uso vinculado".

1. Implemente como função pura em `services.py` do app dono do dado
   (`detections/services.py` neste caso). Ela recebe objetos/IDs e devolve
   bool/lista/dict, sem depender de `request`.
2. Compare sempre por `status.category`, nunca por `status.name`.
3. Calcule em tempo de consulta. Não crie campo "cache" no model nem
   worker, a menos que haja um problema de desempenho medido.
4. Cuidado com N+1: em listagem, prefira anotar o queryset (`annotate`,
   `Exists`, `Subquery`) a chamar a função por linha.
5. Exponha na view (contexto) e no template (badge, seguindo o padrão
   "Alertas" de `rule_list.html`).
6. Se o dado aparecer em mais de um lugar (lista, detalhe, relatório,
   dashboard), **todos chamam a mesma função**. Nunca duplique a regra.
7. Testes cobrindo casos positivos, negativos e de borda (status nulo,
   vínculo inexistente). Modelo: `detections/tests.py::PossiblyInoperativeTests`.
8. Docs: `03-funcionalidades.md`, tabela de regras de negócio.

## F. Adicionar coluna configurável na lista de Regras

1. `detections/models.py::AVAILABLE_RULE_COLUMNS`: adicione `("chave", "Rótulo")`
   na posição de exibição desejada. Se a coluna deve aparecer por padrão,
   inclua também em `DEFAULT_RULE_COLUMNS`.
2. `detections/templates/detections/rule_list.html`: adicione um ramo
   `{% elif key == "chave" %}…` no `if/elif` das células. **Sem esse ramo a
   coluna aparece com cabeçalho e células vazias.**
3. Se a coluna exigir relação, adicione-a ao `select_related`/`prefetch_related`
   de `RuleListView.get_queryset`.
4. Sem migration: preferências antigas continuam válidas.

## G. Adicionar filtro numa listagem

1. Inclua o campo no `*FilterForm` do app (`RuleFilterForm`, `GapFilterForm`,
   `AuditLogFilterForm`), com `required=False`, e defina o `queryset` no
   `__init__` (filtrado por escopo, se for Status/Category).
2. Aplique na `get_queryset` da ListView, dentro do bloco `if form.is_valid()`.
3. Se o filtro for "avançado", adicione o nome à lista `advanced_fields` da
   view para o painel abrir sozinho quando o filtro estiver ativo.
4. Parâmetro fora do form (como `?stage=`)? Leia com `parse_int_or_none`.
5. Em filtro por M2M, mantenha o `.distinct()` no final.
6. A paginação já preserva o querystring (`{% querystring %}`).

## H. Novo indicador ou gráfico no Dashboard

1. `dashboard/services.py::build_dashboard`:
   - **card**: nova chave em `cards`, calculada sobre os querysets já
     filtrados (`rule_qs`, `cuc_qs`, `gap_qs`, `cls_qs`), para respeitar os
     filtros de cliente/tecnologia;
   - **gráfico**: nova chave em `charts` com `_grouped(qs, "campo__name", "campo__color")`,
     ou `palette=True` se o catálogo não tiver cor.
2. `dashboard/templates/dashboard/dashboard.html`: card ou `<canvas>` +
   bloco de inicialização Chart.js, seguindo os existentes. Use as
   variáveis `--scv-*` para cores de interface.
3. Teste: `dashboard/tests.py`, com contagem esperada para um cenário pequeno.

## I. Rastrear um model novo no Histórico

1. `audit/signals.py`: importe o model e adicione-o a `TRACKED_MODELS`.
2. M2M editáveis: adicione em `TRACKED_M2M_FIELDS`.
3. Se o model tiver FK `client`, `AuditLog.client` é preenchido sozinho
   (`_resolve_client`). Se o vínculo com o cliente for indireto, adapte
   `_resolve_client`.
4. Exiba as entradas na tela de detalhe filtrando
   `AuditLog.objects.filter(app_label=..., model_name=..., object_id=str(pk))`
   (padrão de `gaps/views.py::GapDetailView`), protegido por
   `has_perm("audit.view_auditlog")`.
5. O filtro "Entidade" de `/historico/` se atualiza sozinho (lê `TRACKED_MODELS`).
6. Lembre que `QuerySet.update()` e `bulk_*` **não** geram histórico.
7. Testes em `audit/tests.py`: criar, alterar, excluir e o M2M.

## J. Incluir entidade na Busca global

1. `search/views.py`: crie `_<entidade>_results(self, query)` devolvendo
   `{label, icon, see_all_url, total, items[{title, subtitle, url}]}`.
2. Chame-o em `get()` dentro de `if request.user.has_perm("<app>.view_<model>")`.
3. `see_all_url` usa `_list_url(...)`, então a listagem de destino precisa
   aceitar `?q=`.
4. Teste em `search/tests.py`, incluindo que um usuário sem permissão
   **não** vê a categoria.

## K. Incluir dado no relatório PDF/Excel

1. Decida a versão: **interna** (`build_client_report`) ou **para o
   cliente** (`build_client_facing_report`, que não pode expor detalhe
   interno do SOC). Adicione o dado ao dict do service correspondente.
   Reaproveite funções de services existentes, sem recalcular.
2. `reports/excel.py`: nova coluna em `_write_*_sheet` (ajuste `_header_row`
   e `_set_widths`) ou uma nova aba `_write_<x>_sheet`.
3. `reports/pdf.py`: só se o dado couber na página A4. Texto digitado
   pelo usuário deve passar por `_cell()` (quebra linha e escapa `<`/`&`,
   que o ReportLab interpretaria como marcação).
4. Teste em `reports/tests.py`: o arquivo é gerado (status 200 e
   content-type) e o service contém o dado.

## L. Nova coluna na importação CSV de regras

1. `detections/services.py::_import_row`: leia a coluna com
   `(row.get("x") or "").strip()`.
2. Lookup de catálogo: casar por `name__iexact`. Se não encontrar, decida
   entre **erro** (`raise ValueError`, a linha é pulada) para campo
   obrigatório e **aviso** (`report["warnings"].append`, o campo fica vazio)
   para campo opcional.
3. Inclua no dict `defaults`. Se for M2M, `update_or_create` não cobre:
   faça `rule.<m2m>.set(...)` depois.
4. Coluna obrigatória → adicione em `REQUIRED_CSV_COLUMNS`. Pense em quem já
   tem planilhas prontas antes de tornar algo obrigatório.
5. Atualize a ajuda da tela (`rule_import.html`) e `03-funcionalidades.md`.
6. Teste em `detections/tests.py::CsvImportTests`.

## M. Alterar permissões de um papel

1. Edite **somente** `accounts/management/commands/setup_roles.py`. Nunca
   conceda permissão manualmente no admin, porque o próximo deploy
   sobrescreve (`permissions.set`).
2. Para dar uma ação específica de um model a um grupo, filtre `Permission`
   por `codename` e adicione à lista do grupo, com um comentário do porquê.
3. Rode `python manage.py setup_roles`.
4. Ajuste/adicione os testes de permissão do app afetado.
5. Atualize a tabela de `01-arquitetura.md §7`.

## N. Nova tarefa agendada / comando

1. Lógica em `services.py`. O comando em
   `<app>/management/commands/<nome>.py` só orquestra (veja
   `notifications/management/commands/send_digest.py`).
2. Idempotente sempre que possível (rodar duas vezes não causa efeito
   duplicado).
3. Docstring explicando como agendar. O agendamento é externo (cron do
   host): `docker compose exec -T web python manage.py <nome>`.
4. Sem request não há usuário: entradas de histórico geradas pelo comando
   ficam com `user = None`.

## O. Nova variável de ambiente / configuração

1. `core/settings.py`: leia com `env(...)` / `env.bool` / `env.int` /
   `env.list`, **sempre com default seguro** para dev.
2. Documente em `.env.example` com um comentário.
3. Valores de **negócio** não vão para settings: vão para um catálogo no
   banco. Limiares operacionais simples podem ser constantes no service, com
   justificativa (como `STALE_GAP_DAYS`).

## P. Mudanças de interface (template/CSS/menu)

- Novo item de menu: `templates/base.html` + ramo em
  `core/context_processors.py::active_nav`.
- CSS: só em `static/css/app.css`, usando variáveis `--scv-*`. Toda cor nova
  precisa de valor no tema claro (`:root`) **e** no escuro
  (`:root[data-bs-theme="dark"]`).
- Ícones Bootstrap Icons em todas as ações (Novo, Editar, Excluir, Filtrar,
  Importar).
- Botões de ação condicionados a `can_add`/`can_change`/`can_delete` ou a
  `perms.<app>.<perm>`.
- Formulários POST sempre com `{% csrf_token %}`.
- Nunca use `|safe` em conteúdo vindo do usuário.

---

## Checklist final antes de entregar

**Arquitetura**
- [ ] A mudança está no app certo e não importa "para cima" no topo do módulo.
- [ ] Regra de negócio está em `services.py`, e não na view nem no template.
- [ ] Nenhum valor de negócio foi fixado no código (usei catálogo).
- [ ] Lógica compara `status.category`, nunca `status.name`.
- [ ] Nenhuma infraestrutura nova (fila, cache externo, framework JS) sem justificativa aprovada.
- [ ] Sem lógica duplicada: reaproveitei a função de service existente.

**Segurança**
- [ ] Toda view nova tem `LoginRequiredMixin` + `PermissionRequiredMixin` (ou checagem explícita).
- [ ] IDs de querystring passam por `parse_int_or_none`.
- [ ] Redirect para URL do usuário validado com `url_has_allowed_host_and_scheme`.
- [ ] Upload: extensão validada e volume limitado.
- [ ] App novo foi adicionado em `setup_roles`.

**Dados**
- [ ] Migration gerada, revisada e versionada.
- [ ] `on_delete` escolhido conscientemente; DeleteView do alvo usa `ProtectedDeleteMixin` se for `PROTECT`.
- [ ] Forms filtram Status/Category pelo escopo correto.
- [ ] Operações em massa (`update`/`bulk_*`) em models rastreados: aceitei conscientemente que não geram histórico.

**Qualidade**
- [ ] Testes novos/ajustados passando: `docker compose exec web python manage.py test`.
- [ ] Sem N+1 novo em listagem (`select_related`/`prefetch_related`).
- [ ] Interface segue a identidade visual (variáveis `--scv-*`, ícones, tema escuro conferido).
- [ ] Documentação (`docs/` e, se for marco de fase, `README.md`) atualizada.
