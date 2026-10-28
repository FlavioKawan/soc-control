from django.urls import path

from . import views

app_name = "search"

urlpatterns = [
    path("buscar/", views.GlobalSearchView.as_view(), name="results"),
]
