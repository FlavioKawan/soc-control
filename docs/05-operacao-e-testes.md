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
docker compose exec web python manage.py seed_mitre_attack
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
| `taxonomy` | auto-slug, semântica de Status, escopo de Category, permissões dos catálogos, layer do Navigator, agrupamento de camadas (`framework_layers`/descendentes) |
| `clients` | escopo de status no form, permissões por grupo, busca, isolamento por cliente (`visible_clients`, auto-atribuição ao criar) |
| `catalog` | vínculos por cliente, cálculo de cobertura, templates (idempotência), permissões, isolamento por cliente nas telas `client_pk` |
| `detections` | form, revisão vencida, inoperância, inconsistência de cobertura, CSV, colunas, filtros, parâmetros malformados, open redirect, filtro por camada (`?stage=`) incluindo descendentes, isolamento por cliente (lista/detalhe/form/CSV, inclusive contra "roubo" de regra de outro cliente) |
| `gaps` | model, escopo do form por cliente, permissões, filtros, vínculos opcionais (SET_NULL), catálogo de Responsáveis, isolamento por cliente |
| `audit` | create/update/delete, M2M, usuário da requisição, exclusão em cascata de cliente, permissão, isolamento por cliente (mantendo visíveis os registros sem cliente) |
| `dashboard` | parâmetros malformados, widgets de camada (Kill Chain/MITRE ATT&CK), maturidade combinada, ranking de clientes, isolamento por cliente nos agregados e no ranking |
| `search` | resultados e filtro por permissão, isolamento por cliente nos resultados de Cliente/Regra/Gap |
| `reports` | services interno e para o cliente (ações do cliente, cobertura por framework, camadas de ataque protegidas, só regras ativas), download PDF/Excel, permissões, parágrafo narrativo automático (`NarrativeTests`, concordância singular/plural) e gráficos de barra do PDF do cliente (`ChartHelperTests`) |
| `notifications` | regras vencidas, gaps parados, montagem do digest, comando de envio |

## 5. Digest por e-mail (agendamento)

Configure SMTP no `.env` (`DJANGO_EMAIL_*`, `DJANGO_DEFAULT_FROM_EMAIL`,
`DJANGO_SITE_URL`) e agende no cron do host:

```cron
0 8 * * * cd /caminho/soc-control && docker compose exec -T web python manage.py send_digest >> /var/log/soc-control-digest.log 2>&1
```

### Backup e restore do Postgres

`docker/scripts/backup_db.sh` roda `pg_dump` dentro do container `postgres`
(via `docker compose exec`) e grava um `.sql.gz` com timestamp em
`./backups/` (apaga sozinho o que tem mais de 14 dias). Rode a partir da
raiz do repositório:

```bash
./docker/scripts/backup_db.sh                  # usa ./backups e 14 dias de retenção
./docker/scripts/backup_db.sh /mnt/backups 30   # diretório e retenção customizados
```

Agende no cron do host, do mesmo jeito que o digest:

```cron
0 3 * * * cd /caminho/soc-control && ./docker/scripts/backup_db.sh /mnt/backups 30 >> /var/log/soc-control-backup.log 2>&1
```

Para restaurar (**destrutivo**: apaga todos os dados atuais do banco antes
de restaurar o dump — o script pede confirmação, a menos que você passe
`-y`):

```bash
./docker/scripts/restore_db.sh /mnt/backups/soc_control-20261109-030000.sql.gz
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
- um `DJANGO_SECRET_KEY` longo e exclusivo, gerado com
  `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`
  (nunca reaproveite o do `.env` de desenvolvimento)
- opcionalmente, `DJANGO_SENTRY_DSN` para rastreamento de erros (vazio = desativado)

Para um domínio público próprio com TLS, use `docker-compose.prod.yml` (sem
o bind mount `.:/app`, com Nginx + Let's Encrypt via `certbot`) em vez do
`docker-compose.yml` de desenvolvimento:

```bash
cp .env.example .env   # preencha domínio, SECRET_KEY, senha do banco, SMTP
docker compose -f docker-compose.prod.yml up -d --build
# primeira vez só, com o DNS do domínio já apontando para este servidor:
docker compose -f docker-compose.prod.yml run --rm certbot certonly \
  --webroot -w /var/www/certbot -d SEU_DOMINIO_AQUI \
  --email voce@seudominio.com.br --agree-tos --no-eff-email
docker compose -f docker-compose.prod.yml restart nginx
```

Substitua `SEU_DOMINIO_AQUI` em `docker/nginx/nginx.prod.conf` pelo domínio
real antes do primeiro deploy. O container `certbot` renova o certificado
automaticamente (checa a cada 12h). Também vale rodar
`docker compose exec web python manage.py check --deploy` depois de subir.

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
| Widget de camadas (Kill Chain/MITRE) sumiu do dashboard | framework renomeado (é buscado pelo nome exato "Cyber Kill Chain"/"MITRE ATT&CK") | renomear de volta ou rodar `seed_kill_chain`/`seed_mitre_attack` |
| Mudança em `.py` não surtiu efeito | Gunicorn não recarrega sozinho | `docker compose restart web` |
| Cliente "desaparece" (404 ou some da lista) para um ANALYST/VIEWER | não está em `Client.assigned_users` - ADMIN/SOC_MANAGER não são afetados | editar o Cliente e adicionar o usuário em "Analistas com acesso" |
| Container `web` não sobe / `ImportError` mencionando `weasyprint`, `pango` ou `cairo` | `docker/django/Dockerfile` sem as libs nativas do WeasyPrint (usado pelo relatório para o cliente, `reports/pdf.py`) | conferir que o Dockerfile instala `libpango-1.0-0 libpangocairo-1.0-0 libcairo2`; rebuild (`docker compose build web`) |
| Relatório para o cliente em PDF com texto sem acento (caixas/quadrados no lugar de á, ã, ç) | falta `fonts-dejavu-core` na imagem (`python:3.13-slim` não vem com fonte nenhuma) | instalar o pacote no Dockerfile e rebuild |
| `docker compose ps` mostra `web`/`nginx` como `unhealthy` | `GET /healthz/` (`core/views.py`) não respondeu 200 — app travou, ou banco inacessível (healthcheck faz `SELECT 1`) | `docker compose logs web`; confirmar que `postgres` está `healthy` |

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
| 7 | **Sem isolamento entre clientes na camada de aplicação**: qualquer usuário com a permissão `view_client` via **todos** os clientes — um ANALYST/VIEWER comprometido ou mal configurado enxergava regras, gaps e relatórios de clientes que não eram dele (lista, detalhe, dashboard, busca global, catálogo por cliente, importação CSV e histórico de auditoria). | Alta | `clients/services.py::visible_clients` + `clients/mixins.py::ClientScopedQuerysetMixin` — ADMIN/SOC_MANAGER continuam vendo tudo; ANALYST/VIEWER só veem o que estiver em `Client.assigned_users` (campo gerenciado no formulário de Cliente). Decisão de produto: ver `01-arquitetura.md §7`. |

**Testados e confirmados seguros** (sem necessidade de correção): SQL
injection via campos de busca (ORM parametriza tudo), XSS armazenado
(auto-escape do Django confirmado com `<script>` real), acesso a páginas
protegidas sem login (sempre 302 para o login), header `Host` forjado
(sempre 400, `ALLOWED_HOSTS` funcionando), CSRF (middleware nativo do
Django, cookie agora `HttpOnly`).

Todos os achados corrigidos têm teste de regressão automatizado
(`accounts/tests.py::LoginThrottleTests`,
`detections/tests.py::MalformedQueryParamTests`,
`detections/tests.py::OpenRedirectTests`,
`detections/tests.py::CsvImportTests::test_oversized_file_is_capped...`,
`dashboard/tests.py::MalformedFilterParamTests`). O isolamento por cliente
(achado #7) tem `ClientIsolationTests` em `clients`, `detections`, `gaps`,
`catalog`, `search`, `audit` e `dashboard`.
