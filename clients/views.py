from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db.models import Q
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from .forms import ClientForm
from .models import Client


class ClientListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Client
    permission_required = "clients.view_client"
    template_name = "clients/client_list.html"
    context_object_name = "clients"
    paginate_by = 25

    def get_queryset(self):
        qs = Client.objects.select_related("status")
        query = self.request.GET.get("q", "").strip()
        if query:
            qs = qs.filter(Q(name__icontains=query) | Q(legal_name__icontains=query))
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["query"] = self.request.GET.get("q", "")
        ctx["can_add"] = self.request.user.has_perm("clients.add_client")
        ctx["can_change"] = self.request.user.has_perm("clients.change_client")
        ctx["can_delete"] = self.request.user.has_perm("clients.delete_client")
        return ctx


class ClientDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = Client
    permission_required = "clients.view_client"
    template_name = "clients/client_detail.html"
    context_object_name = "client"

    def get_context_data(self, **kwargs):
        from catalog.models import ImplementationTemplate
        from catalog.services import compute_use_case_coverage
        from detections.services import use_case_coverage_inconsistencies
        from taxonomy.choices import StatusCategory

        ctx = super().get_context_data(**kwargs)
        ctx["coverage"] = compute_use_case_coverage(self.object)
        ctx["templates"] = ImplementationTemplate.objects.filter(is_active=True)
        ctx["inconsistent_use_case_ids"] = {
            link.use_case_id for link in use_case_coverage_inconsistencies(self.object)
        }
        ctx["open_gaps_count"] = self.object.gaps.exclude(status__category=StatusCategory.CLOSED).count()

        if self.request.user.has_perm("audit.view_auditlog"):
            from audit.models import AuditLog

            ctx["audit_entries"] = AuditLog.objects.filter(client=self.object).select_related("user")[:50]
        return ctx


class ClientCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Client
    form_class = ClientForm
    permission_required = "clients.add_client"
    template_name = "clients/client_form.html"

    def get_success_url(self):
        return reverse_lazy("clients:client_detail", kwargs={"pk": self.object.pk})


class ClientUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Client
    form_class = ClientForm
    permission_required = "clients.change_client"
    template_name = "clients/client_form.html"

    def get_success_url(self):
        return reverse_lazy("clients:client_detail", kwargs={"pk": self.object.pk})


class ClientDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = Client
    permission_required = "clients.delete_client"
    template_name = "clients/client_confirm_delete.html"
    success_url = reverse_lazy("clients:client_list")
