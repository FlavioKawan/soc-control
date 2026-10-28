from urllib.parse import urlencode

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.shortcuts import render
from django.urls import reverse
from django.views import View

from catalog.models import LogSource, UseCase
from clients.models import Client
from detections.models import Rule
from gaps.models import Gap

#: How many hits each category shows inline before "ver todos".
RESULTS_PER_CATEGORY = 8


def _list_url(url_name, query):
    """A list page's URL pre-filtered by its existing ?q= search field."""
    return f"{reverse(url_name)}?{urlencode({'q': query})}"


class GlobalSearchView(LoginRequiredMixin, View):
    """
    Searches Cliente, Regra, Gap, Caso de Uso e Fonte de Log at once from a
    single box. Each category is included only if the signed-in user holds
    the matching "view" permission - the same check the dedicated list page
    for that entity already enforces, just applied here per-category
    instead of via a single PermissionRequiredMixin (there is no one
    permission that covers all five entities).

    Caso de Uso e Fonte de Log não têm página de detalhe própria (só
    listagem/edição), então seus resultados apontam para a listagem já
    filtrada pelo código/nome exato, em vez da tela de edição - que exige
    permissão de "change" e quebraria para quem só tem "view" (ex: grupo
    VIEWER).
    """

    template_name = "search/results.html"

    def get(self, request):
        query = request.GET.get("q", "").strip()
        categories = []

        if query:
            if request.user.has_perm("clients.view_client"):
                categories.append(self._client_results(query))
            if request.user.has_perm("detections.view_rule"):
                categories.append(self._rule_results(query))
            if request.user.has_perm("gaps.view_gap"):
                categories.append(self._gap_results(query))
            if request.user.has_perm("catalog.view_usecase"):
                categories.append(self._usecase_results(query))
            if request.user.has_perm("catalog.view_logsource"):
                categories.append(self._logsource_results(query))

        context = {
            "query": query,
            "categories": categories,
            "has_results": any(category["total"] for category in categories),
        }
        return render(request, self.template_name, context)

    def _client_results(self, query):
        qs = Client.objects.filter(
            Q(name__icontains=query) | Q(legal_name__icontains=query)
        ).select_related("status")
        return {
            "label": "Clientes",
            "icon": "bi-building",
            "see_all_url": _list_url("clients:client_list", query),
            "total": qs.count(),
            "items": [
                {
                    "title": client.name,
                    "subtitle": client.legal_name or (client.status.name if client.status else ""),
                    "url": reverse("clients:client_detail", kwargs={"pk": client.pk}),
                }
                for client in qs[:RESULTS_PER_CATEGORY]
            ],
        }

    def _rule_results(self, query):
        qs = Rule.objects.filter(
            Q(internal_id__icontains=query)
            | Q(name__icontains=query)
            | Q(vendor_rule_id__icontains=query)
            | Q(description__icontains=query)
        ).select_related("client", "technology")
        return {
            "label": "Regras",
            "icon": "bi-shield-check",
            "see_all_url": _list_url("detections:rule_list", query),
            "total": qs.count(),
            "items": [
                {
                    "title": f"{rule.internal_id} - {rule.name}",
                    "subtitle": f"{rule.client} · {rule.technology}",
                    "url": reverse("detections:rule_detail", kwargs={"pk": rule.pk}),
                }
                for rule in qs[:RESULTS_PER_CATEGORY]
            ],
        }

    def _gap_results(self, query):
        qs = Gap.objects.filter(
            Q(code__icontains=query) | Q(title__icontains=query) | Q(description__icontains=query)
        ).select_related("client")
        return {
            "label": "Gaps",
            "icon": "bi-exclamation-triangle",
            "see_all_url": _list_url("gaps:gap_list", query),
            "total": qs.count(),
            "items": [
                {
                    "title": f"{gap.code} - {gap.title}",
                    "subtitle": str(gap.client),
                    "url": reverse("gaps:gap_detail", kwargs={"pk": gap.pk}),
                }
                for gap in qs[:RESULTS_PER_CATEGORY]
            ],
        }

    def _usecase_results(self, query):
        qs = UseCase.objects.filter(
            Q(code__icontains=query) | Q(name__icontains=query) | Q(description__icontains=query)
        )
        return {
            "label": "Casos de Uso",
            "icon": "bi-list-check",
            "see_all_url": _list_url("catalog:usecase_list", query),
            "total": qs.count(),
            "items": [
                {
                    "title": f"{use_case.code} - {use_case.name}",
                    "subtitle": "",
                    "url": _list_url("catalog:usecase_list", use_case.code),
                }
                for use_case in qs[:RESULTS_PER_CATEGORY]
            ],
        }

    def _logsource_results(self, query):
        qs = LogSource.objects.filter(Q(name__icontains=query) | Q(description__icontains=query))
        return {
            "label": "Fontes de Log",
            "icon": "bi-file-earmark-text",
            "see_all_url": _list_url("catalog:logsource_list", query),
            "total": qs.count(),
            "items": [
                {
                    "title": log_source.name,
                    "subtitle": "",
                    "url": _list_url("catalog:logsource_list", log_source.name),
                }
                for log_source in qs[:RESULTS_PER_CATEGORY]
            ],
        }
