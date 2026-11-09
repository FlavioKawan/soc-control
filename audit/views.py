from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db.models import Q
from django.views.generic import ListView

from clients.services import has_full_client_visibility, visible_clients

from .forms import AuditLogFilterForm
from .models import AuditLog


class AuditLogListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = AuditLog
    permission_required = "audit.view_auditlog"
    template_name = "audit/auditlog_list.html"
    context_object_name = "entries"
    paginate_by = 50

    def get_queryset(self):
        self.filter_form = AuditLogFilterForm(self.request.GET or None, user=self.request.user)
        qs = AuditLog.objects.select_related("user", "client")

        # client=NULL entries are changes to non-client-scoped catalogs
        # (UseCase, LogSource, Framework...), not any specific client's
        # data - a restricted ANALYST/VIEWER keeps seeing those, only
        # entries tied to a client outside their assignment are hidden.
        if not has_full_client_visibility(self.request.user):
            qs = qs.filter(Q(client__isnull=True) | Q(client__in=visible_clients(self.request.user)))

        if self.filter_form.is_valid():
            data = self.filter_form.cleaned_data
            if data.get("q"):
                qs = qs.filter(Q(object_repr__icontains=data["q"]) | Q(object_id__icontains=data["q"]))
            if data.get("client"):
                qs = qs.filter(client=data["client"])
            if data.get("action"):
                qs = qs.filter(action=data["action"])
            if data.get("model_name"):
                qs = qs.filter(model_name=data["model_name"])
            if data.get("user"):
                qs = qs.filter(user=data["user"])

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["filter_form"] = self.filter_form
        advanced_fields = ["client", "action", "model_name", "user"]
        ctx["has_advanced_filters"] = any(self.request.GET.get(f) for f in advanced_fields)
        return ctx
