# SOC Control

[![CI](https://github.com/FlavioKawan/soc-control/actions/workflows/ci.yml/badge.svg)](https://github.com/FlavioKawan/soc-control/actions/workflows/ci.yml)

Ferramenta interna de governança de um SOC (Security Operations Center):
inventário de regras de detecção, casos de uso, fontes de log e gaps por
cliente, com cálculo de cobertura e alertas de inconsistência.

Não é um SIEM, SOAR ou sistema de gestão de incidentes — não ingere logs nem
dispara alertas; é onde o time registra **o que já foi configurado**, para
que fique visível (por cliente) o que está coberto, o que está pendente de
revisão e onde há lacunas.

> **Vai entender ou alterar o código?** Comece por [`docs/`](docs/README.md) —
> arquitetura, modelo de dados, funcionalidades (tela → URL → permissão →
> código) e um guia passo a passo para cada tipo de alteração.

## Principais funcionalidades

- **Inventário de regras de detecção** por cliente, com status, severidade,
  revisão periódica (vencimento automático) e importação via CSV.
- **Casos de uso e fontes de log** por cliente, com cálculo de cobertura
  (coberto / parcial / não coberto) e detecção de inconsistências entre
  regra e caso de uso.
- **Gaps** (lacunas conhecidas) com responsável e criticidade.
- **Dashboard** com indicadores agregados, cobertura por Cyber Kill Chain e
  MITRE ATT&CK (Navigator), maturidade combinada e ranking de clientes.
- **Isolamento por cliente**: ANALYST/VIEWER só veem os clientes em que
  foram explicitamente atribuídos; ADMIN/SOC_MANAGER veem tudo.
- **Relatório para o cliente** em PDF (visual, com gráficos e narrativa
  automática) e exportação em Excel.
- **Busca global**, **histórico de auditoria** (quem mudou o quê) e
  **digest por e-mail** de regras vencidas/gaps parados (agendável via cron).
- Catálogos administráveis (status, severidade, tecnologia, categoria,
  frameworks) — valores de negócio nunca ficam hardcoded no código.

Detalhe de cada tela (URL, permissão, regra de negócio) em
[`docs/03-funcionalidades.md`](docs/03-funcionalidades.md).

## Stack

| Camada | Tecnologia |
|---|---|
| Backend | Django 5.2 (Python 3.13) |
| Banco de dados | PostgreSQL 16 |
| Frontend | Django Templates + Bootstrap 5.3 + Chart.js |
| Relatórios | WeasyPrint (PDF), openpyxl (Excel) |
| Infra | Docker Compose, Gunicorn atrás de Nginx |
| CI | GitHub Actions ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)) |

## Pré-requisitos

Docker Desktop (ou Docker Engine + Compose plugin) — nenhuma outra
dependência é instalada no host; tudo roda em containers.

## Instalação (Docker)

```bash
cd soc-control
cp .env.example .env   # ajuste DJANGO_SECRET_KEY e POSTGRES_PASSWORD
docker compose up -d --build
docker compose exec web python manage.py createsuperuser
```

Acesse `http://localhost:8088/`. O entrypoint já roda `migrate`,
`setup_roles` e `collectstatic`.

Dados de referência opcionais (frameworks para o dashboard de camadas):

```bash
docker compose exec web python manage.py seed_kill_chain
docker compose exec web python manage.py seed_mitre_attack
```

## Testes

```bash
docker compose exec web python manage.py test
```

Roda contra um banco PostgreSQL temporário, criado e destruído
automaticamente pelo Django. O mesmo comando roda no CI a cada push/PR.

## Documentação

| Arquivo | Conteúdo |
|---|---|
| [docs/01-arquitetura.md](docs/01-arquitetura.md) | Stack, camadas, dependências entre apps, padrões obrigatórios |
| [docs/02-modelo-de-dados.md](docs/02-modelo-de-dados.md) | Tabelas, relacionamentos, regras de `on_delete` |
| [docs/03-funcionalidades.md](docs/03-funcionalidades.md) | Cada tela: URL, permissão, regra de negócio |
| [docs/04-guia-de-alteracoes.md](docs/04-guia-de-alteracoes.md) | Receitas passo a passo para os tipos de alteração mais comuns |
| [docs/05-operacao-e-testes.md](docs/05-operacao-e-testes.md) | Ambiente, migrations, testes, backup/restore, deploy, diagnóstico, pentest interno |

## Deploy em produção

Para um servidor com domínio público próprio (TLS via Let's Encrypt), use o
stack dedicado em vez do `docker-compose.yml` de desenvolvimento:

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

Checklist completo (variáveis de ambiente, emissão do certificado, Sentry,
backup agendado) em
[`docs/05-operacao-e-testes.md` §6](docs/05-operacao-e-testes.md#6-deploy--atualização).

## Variáveis de ambiente

Ver [`.env.example`](.env.example) (inclui a seção de produção). Nunca
commitar `.env` real (já está no `.gitignore`).

## Segurança

Achados e correções de uma revisão ofensiva interna estão em
[`docs/05-operacao-e-testes.md` §8](docs/05-operacao-e-testes.md#8-segurança--pentest-interno).
