from django.urls import path

from . import views

app_name = "gaps"

urlpatterns = [
    path("gaps/", views.GapListView.as_view(), name="gap_list"),
    path("gaps/novo/", views.GapCreateView.as_view(), name="gap_create"),
    path("gaps/<int:pk>/", views.GapDetailView.as_view(), name="gap_detail"),
    path("gaps/<int:pk>/editar/", views.GapUpdateView.as_view(), name="gap_update"),
    path("gaps/<int:pk>/excluir/", views.GapDeleteView.as_view(), name="gap_delete"),
]
