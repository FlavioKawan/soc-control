from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils.text import slugify
from django.views import View

from clients.models import Client

from .excel import render_client_report_excel
from .pdf import render_client_facing_report_pdf, render_client_report_pdf
from .services import build_client_facing_report, build_client_report


class ClientReportPdfView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """
    Exports the same data already shown on the client detail page (coverage,
    rules, gaps) as a PDF - the internal, complete version for the SOC team
    (ClientFacingReportPdfView is the one sent to the client). No new data
    is exposed: same permission the detail page already requires.
    """

    permission_required = "clients.view_client"

    def get(self, request, pk):
        client = get_object_or_404(Client, pk=pk)
        report = build_client_report(client)
        pdf_bytes = render_client_report_pdf(report)
        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="relatorio-{slugify(client.name)}.pdf"'
        return response


class ClientFacingReportPdfView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """
    The version written for the client to read: executive summary, what
    depends on them, coverage. Leaves out internal SOC details (see
    reports.services.build_client_facing_report).
    """

    permission_required = "clients.view_client"

    def get(self, request, pk):
        client = get_object_or_404(Client, pk=pk)
        pdf_bytes = render_client_facing_report_pdf(build_client_facing_report(client))
        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="relatorio-cliente-{slugify(client.name)}.pdf"'
        return response


class ClientReportExcelView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = "clients.view_client"

    def get(self, request, pk):
        client = get_object_or_404(Client, pk=pk)
        report = build_client_report(client)
        xlsx_bytes = render_client_report_excel(report)
        response = HttpResponse(
            xlsx_bytes,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = f'attachment; filename="relatorio-{slugify(client.name)}.xlsx"'
        return response
