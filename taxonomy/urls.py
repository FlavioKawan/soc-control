from django.urls import path

from . import views

app_name = "taxonomy"

urlpatterns = [
    path("configuracoes/", views.config_home, name="config_home"),
    path("configuracoes/<slug:catalog>/", views.CatalogListView.as_view(), name="catalog_list"),
    path("configuracoes/<slug:catalog>/novo/", views.CatalogCreateView.as_view(), name="catalog_create"),
    path("configuracoes/<slug:catalog>/<int:pk>/editar/", views.CatalogUpdateView.as_view(), name="catalog_update"),
    path("configuracoes/<slug:catalog>/<int:pk>/excluir/", views.CatalogDeleteView.as_view(), name="catalog_delete"),
    path("frameworks/", views.FrameworkListView.as_view(), name="framework_list"),
    path("frameworks/novo/", views.FrameworkCreateView.as_view(), name="framework_create"),
    path("frameworks/<int:pk>/", views.FrameworkDetailView.as_view(), name="framework_detail"),
    path("frameworks/<int:pk>/editar/", views.FrameworkUpdateView.as_view(), name="framework_update"),
    path(
        "frameworks/<int:pk>/navigator/",
        views.FrameworkNavigatorExportView.as_view(),
        name="framework_navigator_export",
    ),
    path("frameworks/<int:pk>/excluir/", views.FrameworkDeleteView.as_view(), name="framework_delete"),
    path(
        "frameworks/<int:framework_pk>/controles/novo/",
        views.FrameworkControlCreateView.as_view(),
        name="frameworkcontrol_create",
    ),
    path(
        "controles/<int:pk>/editar/",
        views.FrameworkControlUpdateView.as_view(),
        name="frameworkcontrol_update",
    ),
    path(
        "controles/<int:pk>/excluir/",
        views.FrameworkControlDeleteView.as_view(),
        name="frameworkcontrol_delete",
    ),
]
