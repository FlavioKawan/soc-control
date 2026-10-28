# Documentação técnica — SOC Control

Documentação para **quem vai manter ou alterar o código**. O `README.md` da
raiz é só a porta de entrada (o que é, stack, instalação); estes arquivos
respondem "como o sistema funciona hoje e o que eu mexo para mudar X".

| Arquivo | Leia quando... |
|---|---|
| [01-arquitetura.md](01-arquitetura.md) | for a primeira vez no projeto: stack, camadas, dependências entre apps, padrões obrigatórios, ciclo de uma requisição. |
| [02-modelo-de-dados.md](02-modelo-de-dados.md) | precisar entender tabelas, relacionamentos, regras de `on_delete` e a semântica de Status. |
| [03-funcionalidades.md](03-funcionalidades.md) | precisar saber o que cada tela faz, qual URL/permissão usa e em qual arquivo está a lógica. |
| [04-guia-de-alteracoes.md](04-guia-de-alteracoes.md) | for **fazer uma alteração**: receitas passo a passo para os tipos de mudança mais comuns + checklist final. |
| [05-operacao-e-testes.md](05-operacao-e-testes.md) | precisar subir o ambiente, rodar testes, gerar migrations, agendar o digest ou fazer deploy. |

## Resumo em 30 segundos

- **O que é**: ferramenta interna de governança de um SOC — inventário de
  regras de detecção, casos de uso, fontes de log e gaps **por cliente**, com
  cálculo de cobertura e alertas de inconsistência. Não é SIEM/SOAR.
- **Stack**: Django 5.2 (server-side rendering, templates + Bootstrap 5.3),
  PostgreSQL 16, Gunicorn atrás de Nginx, tudo em Docker Compose.
- **Princípio central**: *estrutura fixa, conteúdo configurável* — entidades
  são tabelas reais; valores de negócio (status, severidades, tecnologias…)
  são registros em catálogos administráveis, nunca listas no código.
- **Regra de ouro para lógica de negócio**: nunca compare pelo **nome** de um
  Status; compare por `status.category` (enum fixo em `taxonomy/choices.py`).
- **Onde fica cada coisa**: regra de negócio em `services.py`; views só
  orquestram; permissões via `PermissionRequiredMixin` + grupos criados por
  `setup_roles`.

## Convenção desta documentação

- Caminhos são relativos a `soc-control/`.
- Ao mudar um comportamento descrito aqui, **atualize o arquivo
  correspondente no mesmo commit** — documentação desatualizada é pior que
  nenhuma.
