from django.urls import path

from . import views

app_name = "audit"

urlpatterns = [
    path("historico/", views.AuditLogListView.as_view(), name="auditlog_list"),
]
