# SOC Control

Ferramenta interna de governança de um SOC (Security Operations Center):
inventário de regras de detecção, casos de uso, fontes de log e gaps por
cliente, com cálculo de cobertura e alertas de inconsistência. Não é um
SIEM, SOAR ou sistema de gestão de incidentes.

> **Vai entender ou alterar o código?** Comece por [`docs/`](docs/README.md) —
> arquitetura, modelo de dados, funcionalidades (tela → URL → permissão →
> código) e um guia passo a passo para cada tipo de alteração.

## Stack

Django 5.2 + PostgreSQL 16, Django Templates + Bootstrap 5.3, Docker Compose
com Nginx + Gunicorn.

## Instalação (Docker)

```bash
cd soc-control
cp .env.example .env   # ajuste DJANGO_SECRET_KEY e POSTGRES_PASSWORD
docker compose up -d --build
docker compose exec web python manage.py createsuperuser
```

Acesse `http://localhost:8088/`. O entrypoint já roda `migrate`,
`setup_roles` e `collectstatic`.

Backup/restore, migrations, testes e deploy estão em
[`docs/05-operacao-e-testes.md`](docs/05-operacao-e-testes.md).

## Variáveis de ambiente

Ver `.env.example`. Nunca commitar `.env` real (já está no `.gitignore`).

## Segurança

Achados e correções de uma revisão ofensiva interna estão em
[`docs/05-operacao-e-testes.md`](docs/05-operacao-e-testes.md) (seção
"Segurança — pentest interno").
