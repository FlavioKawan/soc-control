from django.urls import path

from . import views

app_name = "reports"

urlpatterns = [
    path("clientes/<int:pk>/relatorio.pdf", views.ClientReportPdfView.as_view(), name="client_report_pdf"),
    path(
        "clientes/<int:pk>/relatorio-cliente.pdf",
        views.ClientFacingReportPdfView.as_view(),
        name="client_facing_report_pdf",
    ),
    path("clientes/<int:pk>/relatorio.xlsx", views.ClientReportExcelView.as_view(), name="client_report_excel"),
]
