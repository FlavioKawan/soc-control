from django.urls import path

from . import views

app_name = "detections"

urlpatterns = [
    path("regras/", views.RuleListView.as_view(), name="rule_list"),
    path("regras/novo/", views.RuleCreateView.as_view(), name="rule_create"),
    path("regras/importar/", views.RuleImportView.as_view(), name="rule_import"),
    path("regras/colunas/", views.RuleColumnPreferenceUpdateView.as_view(), name="rule_columns"),
    path("regras/<int:pk>/", views.RuleDetailView.as_view(), name="rule_detail"),
    path("regras/<int:pk>/editar/", views.RuleUpdateView.as_view(), name="rule_update"),
    path("regras/<int:pk>/excluir/", views.RuleDeleteView.as_view(), name="rule_delete"),
]
