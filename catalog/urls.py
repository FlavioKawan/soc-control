from django.urls import path

from . import views

app_name = "catalog"

urlpatterns = [
    # LogSource (global catalog)
    path("fontes-de-log/", views.LogSourceListView.as_view(), name="logsource_list"),
    path("fontes-de-log/novo/", views.LogSourceCreateView.as_view(), name="logsource_create"),
    path("fontes-de-log/<int:pk>/editar/", views.LogSourceUpdateView.as_view(), name="logsource_update"),
    path("fontes-de-log/<int:pk>/excluir/", views.LogSourceDeleteView.as_view(), name="logsource_delete"),
    # ClientLogSource
    path(
        "clientes/<int:client_pk>/fontes-de-log/novo/",
        views.ClientLogSourceCreateView.as_view(),
        name="clientlogsource_create",
    ),
    path(
        "clientes/fontes-de-log/<int:pk>/editar/",
        views.ClientLogSourceUpdateView.as_view(),
        name="clientlogsource_update",
    ),
    path(
        "clientes/fontes-de-log/<int:pk>/excluir/",
        views.ClientLogSourceDeleteView.as_view(),
        name="clientlogsource_delete",
    ),
    # UseCase (global catalog)
    path("casos-de-uso/", views.UseCaseListView.as_view(), name="usecase_list"),
    path("casos-de-uso/novo/", views.UseCaseCreateView.as_view(), name="usecase_create"),
    path("casos-de-uso/<int:pk>/editar/", views.UseCaseUpdateView.as_view(), name="usecase_update"),
    path("casos-de-uso/<int:pk>/excluir/", views.UseCaseDeleteView.as_view(), name="usecase_delete"),
    # ClientUseCase
    path(
        "clientes/<int:client_pk>/casos-de-uso/novo/",
        views.ClientUseCaseCreateView.as_view(),
        name="clientusecase_create",
    ),
    path(
        "clientes/casos-de-uso/<int:pk>/editar/",
        views.ClientUseCaseUpdateView.as_view(),
        name="clientusecase_update",
    ),
    path(
        "clientes/casos-de-uso/<int:pk>/excluir/",
        views.ClientUseCaseDeleteView.as_view(),
        name="clientusecase_delete",
    ),
    # Implementation templates
    path("templates/", views.TemplateListView.as_view(), name="template_list"),
    path("templates/novo/", views.TemplateCreateView.as_view(), name="template_create"),
    path("templates/<int:pk>/", views.TemplateDetailView.as_view(), name="template_detail"),
    path("templates/<int:pk>/editar/", views.TemplateUpdateView.as_view(), name="template_update"),
    path("templates/<int:pk>/excluir/", views.TemplateDeleteView.as_view(), name="template_delete"),
    path(
        "templates/<int:template_pk>/fontes-de-log/novo/",
        views.TemplateLogSourceCreateView.as_view(),
        name="templatelogsource_create",
    ),
    path(
        "templates/fontes-de-log/<int:pk>/excluir/",
        views.TemplateLogSourceDeleteView.as_view(),
        name="templatelogsource_delete",
    ),
    path(
        "templates/<int:template_pk>/casos-de-uso/novo/",
        views.TemplateUseCaseCreateView.as_view(),
        name="templateusecase_create",
    ),
    path(
        "templates/casos-de-uso/<int:pk>/excluir/",
        views.TemplateUseCaseDeleteView.as_view(),
        name="templateusecase_delete",
    ),
    # Apply template to a client
    path(
        "clientes/<int:client_pk>/aplicar-template/",
        views.ApplyTemplateView.as_view(),
        name="apply_template",
    ),
]
