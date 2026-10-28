# 05 — Operação, ambiente e testes

Os comandos assumem que você está em `soc-control/` com Docker Desktop
rodando. Instalação do zero, backup e restore estão no `README.md` da raiz;
aqui fica o ciclo de **desenvolvimento**.

## 1. Subir o ambiente

```bash
cp .env.example .env          # só na primeira vez; ajuste DJANGO_SECRET_KEY e POSTGRES_PASSWORD
docker compose up -d --build
docker compose exec web python manage.py createsuperuser   # primeira vez
```

Acesse `http://localhost:8088/`. O entrypoint já roda `migrate`,
`setup_roles` e `collectstatic`.

Dados de referência opcionais:

```bash
docker compose exec web python manage.py seed_kill_chain
```

Em desenvolvimento, deixe `DJANGO_EMAIL_BACKEND` fora do `.env` (ou use o de
console) para o digest só imprimir no log.

## 2. Ciclo de desenvolvimento

O código é montado no container (`.:/app`), mas o Gunicorn **não** recarrega
sozinho. Depois de alterar Python:

```bash
docker compose restart web
```

Templates e CSS: basta recarregar a página. Se o CSS não atualizar, rode
`docker compose exec web python manage.py collectstatic --noinput`, porque o
Nginx serve estáticos do volume coletado.

Logs:

```bash
docker compose logs -f web
```

Shell Django (útil para inspecionar dados):

```bash
docker compose exec web python manage.py shell
```

## 3. Migrations

```bash
docker compose exec web python manage.py makemigrations <app>
docker compose exec web python manage.py migrate
docker compose exec web python manage.py setup_roles   # se criou model/app novo
```

- Rode `makemigrations` **dentro do container**: o arquivo aparece no seu
  disco graças ao bind mount.
- Revise o arquivo gerado antes de versionar (renomeações viram
  remove+add se o Django não perguntar).
- Para checar se esqueceu alguma migration:
  `docker compose exec web python manage.py makemigrations --check --dry-run`.

## 4. Testes

```bash
# tudo
docker compose exec web python manage.py test

# um app
docker compose exec web python manage.py test detections

# uma classe ou um teste
docker compose exec web python manage.py test detections.tests.CsvImportTests
docker compose exec web python manage.py test detections.tests.CsvImportTests.test_oversized_file_is_capped_instead_of_processed_in_full
```

Os testes rodam contra um banco PostgreSQL temporário (`test_<POSTGRES_DB>`)
criado pelo próprio Django. O usuário do `.env` precisa de permissão para
criar bancos, e o usuário padrão da imagem oficial tem.

### Convenções dos testes

- Um `tests.py` por app, com classes `TestCase` agrupadas por assunto
  (`<Assunto>Tests`).
- Testes de permissão chamam `call_command("setup_roles")` no `setUp` e
  criam usuários em cada grupo. Modelo:
  `clients/tests.py::ClientPermissionTests`.
- Views: `self.client.force_login(user)` + `reverse("app:nome")`. Confira
  `403` para quem não tem permissão e `302` para anônimo.
- Regra de negócio: teste a função de `services.py` diretamente, cobrindo
  bordas (status `None`, vínculo inexistente, zero itens).
- Todo bug corrigido ganha um teste de regressão com nome descritivo
  (ex.: `test_deleting_a_client_with_rules_and_gaps_does_not_violate_the_fk`).
- Docstring no teste quando ele documenta uma **decisão** ("o banco aceita
  status de escopo errado; quem barra é o form").

### O que cada app testa hoje

| App | Cobertura principal |
|---|---|
| `accounts` | limite de tentativas de login (por IP, reset no sucesso); CRUD de usuários da plataforma, grupos só para ADMIN, redefinição de senha, travas contra autoexclusão/autodesativação |
| `taxonomy` | auto-slug, semântica de Status, escopo de Category, permissões dos catálogos, layer do Navigator |
| `clients` | escopo de status no form, permissões por grupo, busca |
| `catalog` | vínculos por cliente, cálculo de cobertura, templates (idempotência), permissões |
| `detections` | form, revisão vencida, inoperância, inconsistência de cobertura, CSV, colunas, filtros, parâmetros malformados, open redirect |
| `gaps` | model, escopo do form por cliente, permissões, filtros, vínculos opcionais (SET_NULL), catálogo de Responsáveis |
| `audit` | create/update/delete, M2M, usuário da requisição, exclusão em cascata de cliente, permissão |
| `dashboard` | parâmetros malformados |
| `search` | resultados e filtro por permissão |
| `reports` | services interno e para o cliente (ações do cliente, cobertura por framework, só regras ativas), download PDF/Excel, permissões |
| `notifications` | regras vencidas, gaps parados, montagem do digest, comando de envio |

## 5. Digest por e-mail (agendamento)

Configure SMTP no `.env` (`DJANGO_EMAIL_*`, `DJANGO_DEFAULT_FROM_EMAIL`,
`DJANGO_SITE_URL`) e agende no cron do host:

```cron
0 8 * * * cd /caminho/soc-control && docker compose exec -T web python manage.py send_digest >> /var/log/soc-control-digest.log 2>&1
```

## 6. Deploy / atualização

```bash
docker compose up -d --build   # entrypoint aplica migrate + setup_roles + collectstatic
```

Antes de expor em produção, confirme no `.env`:

- `DJANGO_DEBUG=False`
- `DJANGO_ALLOWED_HOSTS` e `DJANGO_CSRF_TRUSTED_ORIGINS` com o domínio real
- `DJANGO_SECURE_SSL_REDIRECT=True`, `DJANGO_SESSION_COOKIE_SECURE=True`,
  `DJANGO_CSRF_COOKIE_SECURE=True` (com HTTPS na frente)
- um `DJANGO_SECRET_KEY` longo e exclusivo

Também vale considerar um `docker-compose.prod.yml` sem o bind mount `.:/app`
e rodar `python manage.py check --deploy`.

## 7. Diagnóstico rápido

| Sintoma | Causa provável | Ação |
|---|---|---|
| 403 numa tela que deveria abrir | usuário sem grupo, ou `setup_roles` não rodou depois de um model novo | `setup_roles`; conferir os grupos do usuário no admin |
| "CSRF verification failed" | host:porta de acesso fora de `DJANGO_CSRF_TRUSTED_ORIGINS` | ajustar o `.env` e reiniciar `web` |
| 400 Bad Request em tudo | host fora de `DJANGO_ALLOWED_HOSTS` | ajustar o `.env` |
| "Não é possível excluir … ainda está em uso" | FK `PROTECT` | reclassificar os registros que usam o item antes de excluir |
| Login bloqueado | 10 falhas do mesmo IP em 15 min | esperar, ou no shell: `from django.core.cache import cache; cache.clear()` |
| Alteração não aparece no Histórico | feita via `QuerySet.update()`/`bulk_*`/SQL cru (não disparam signals), ou o model não está em `TRACKED_MODELS` | ver `01-arquitetura.md §8` |
| Histórico com usuário vazio | alteração feita fora de requisição (shell, comando agendado) | esperado |
| Widget Kill Chain sumiu do dashboard | framework renomeado (é buscado pelo nome "Cyber Kill Chain") | renomear de volta ou rodar `seed_kill_chain` |
| Mudança em `.py` não surtiu efeito | Gunicorn não recarrega sozinho | `docker compose restart web` |

## 8. Segurança — pentest interno

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
(sempre 400, `ALLOWED_HOSTS` funcionando), CSRF (middleware nativo do
Django, cookie agora `HttpOnly`).

**Registrado, não corrigido ainda** — exige uma decisão de produto antes
de implementar: a spec original pede "isolamento entre clientes na
camada de aplicação". Hoje qualquer usuário autenticado com a permissão
`view_client` vê **todos** os clientes — não há um vínculo
usuário↔cliente que restrinja um analista a só ver os clientes dele. O
que já existe é o isolamento "defensivo" dentro dos formulários (ex:
`GapForm` só oferece casos de uso/fontes/regras do cliente selecionado,
para não misturar dados por engano) — isso evita erro, não impede acesso.
Se o requisito for "cada analista só vê os clientes atribuídos a ele", é
uma feature nova (precisa de um modelo de atribuição usuário↔cliente e um
filtro em toda queryset) — vale conversar antes de implementar algo que
pode não ser o que você imaginou.

Todos os achados corrigidos têm teste de regressão automatizado
(`accounts/tests.py::LoginThrottleTests`,
`detections/tests.py::MalformedQueryParamTests`,
`detections/tests.py::OpenRedirectTests`,
`detections/tests.py::CsvImportTests::test_oversized_file_is_capped...`,
`dashboard/tests.py::MalformedFilterParamTests`).
