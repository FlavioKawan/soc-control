from django.urls import path

from . import views

app_name = "clients"

urlpatterns = [
    path("clientes/", views.ClientListView.as_view(), name="client_list"),
    path("clientes/novo/", views.ClientCreateView.as_view(), name="client_create"),
    path("clientes/<int:pk>/", views.ClientDetailView.as_view(), name="client_detail"),
    path("clientes/<int:pk>/editar/", views.ClientUpdateView.as_view(), name="client_update"),
    path("clientes/<int:pk>/excluir/", views.ClientDeleteView.as_view(), name="client_delete"),
]
