"""
One entry per simple catalog shown under "Configurações". Adding a brand
new catalog type in the future means adding one dict entry here (plus a
model/form) - not a new set of views, URLs and templates.

Framework/FrameworkControl are deliberately NOT here: their shape (a
framework owning a tree of controls) doesn't fit this flat list/form
pattern, so they get their own small dedicated views.
"""

from . import forms, models

CATALOGS = {
    "tecnologias": {
        "model": models.Technology,
        "form": forms.TechnologyForm,
        "label": "Tecnologias",
        "icon": "bi-cpu",
        "description": "As ferramentas/plataformas usadas (Wazuh, CrowdStrike, Sentinel...). "
                        "Toda Regra e toda Fonte de Log pertence a uma tecnologia.",
        "list_fields": [("name", "Nome"), ("category", "Categoria"), ("is_active", "Ativo")],
    },
    "status": {
        "model": models.Status,
        "form": forms.StatusForm,
        "label": "Status",
        "icon": "bi-toggle2-on",
        "description": "Estados possíveis para Cliente, Regra, Caso de Uso, Fonte de Log e Gap "
                        "(ex: Ativa, Em Teste, Coberto, Sem Log). Cada status carrega uma "
                        "\"semântica interna\" fixa (campo Semântica) que o sistema usa para "
                        "calcular cobertura e alertas — o nome que você vê é livre, a semântica não.",
        "list_fields": [("name", "Nome"), ("category", "Semântica"), ("scope", "Escopo"), ("is_active", "Ativo")],
    },
    "severidades": {
        "model": models.Severity,
        "form": forms.SeverityForm,
        "label": "Severidades",
        "icon": "bi-speedometer2",
        "description": "Nível de criticidade, reaproveitado pela Regra (\"Severidade SOC\") e "
                        "pelo Caso de Uso/Gap (\"Criticidade\"). Diferente de Status: Severidade "
                        "nunca muda o significado de nada, só a prioridade/urgência.",
        "list_fields": [("name", "Nome"), ("weight", "Peso"), ("is_active", "Ativo")],
    },
    "categorias": {
        "model": models.Category,
        "form": forms.CategoryForm,
        "label": "Categorias",
        "icon": "bi-tags",
        "description": "Classificação temática (ex: Identidade, Endpoint, Rede) para agrupar "
                        "Tecnologias, Regras, Casos de Uso e Fontes de Log por área de atuação.",
        "list_fields": [("name", "Nome"), ("applicable_to", "Aplicável a"), ("is_active", "Ativo")],
    },
    "tags": {
        "model": models.Tag,
        "form": forms.TagForm,
        "label": "Tags",
        "icon": "bi-tag",
        "description": "Rótulos livres e informais (ex: #Windows, #Ransomware) para busca e "
                        "filtro rápido. Mais leve que Categoria: uma Regra pode ter várias Tags, "
                        "mas só uma Categoria.",
        "list_fields": [("name", "Nome"), ("is_active", "Ativo")],
    },
    "tipos": {
        "model": models.RuleType,
        "form": forms.RuleTypeForm,
        "label": "Tipos de Regra",
        "icon": "bi-bookmark",
        "description": "Classifica a Regra em si (ex: Padrão, Customizada). Não confundir com "
                        "Categoria (tema da ameaça) nem com Severidade (criticidade) — Tipo é "
                        "sobre a origem/natureza da regra.",
        "list_fields": [("name", "Nome"), ("is_active", "Ativo")],
    },
    "responsaveis": {
        "model": models.ResponsibleParty,
        "form": forms.ResponsiblePartyForm,
        "label": "Responsáveis",
        "icon": "bi-person-badge",
        "description": "Quem é o dono de resolver um Gap (ex: SOC, Cliente, Fornecedor). "
                        "Usado apenas em Gaps — não é o usuário do sistema, é a parte responsável. "
                        "Marque \"Responsabilidade do cliente\" no responsável que representa o "
                        "cliente: os gaps dele viram ações pendentes no relatório para o cliente.",
        "list_fields": [("name", "Nome"), ("is_client", "Do cliente"), ("is_active", "Ativo")],
    },
}
