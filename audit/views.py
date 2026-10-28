from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db.models import Q
from django.views.generic import ListView

from .forms import AuditLogFilterForm
from .models import AuditLog


class AuditLogListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = AuditLog
    permission_required = "audit.view_auditlog"
    template_name = "audit/auditlog_list.html"
    context_object_name = "entries"
    paginate_by = 50

    def get_queryset(self):
        self.filter_form = AuditLogFilterForm(self.request.GET or None)
        qs = AuditLog.objects.select_related("user", "client")

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
