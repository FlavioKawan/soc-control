from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db.models import Q
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from .forms import GapFilterForm, GapForm
from .models import Gap


class GapListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Gap
    permission_required = "gaps.view_gap"
    template_name = "gaps/gap_list.html"
    context_object_name = "gaps"
    paginate_by = 25

    def get_queryset(self):
        self.filter_form = GapFilterForm(self.request.GET or None)
        qs = Gap.objects.select_related("client", "status", "criticality", "responsible_party")

        if self.filter_form.is_valid():
            data = self.filter_form.cleaned_data
            if data.get("q"):
                q = data["q"]
                qs = qs.filter(Q(code__icontains=q) | Q(title__icontains=q) | Q(description__icontains=q))
            for field in ["client", "status", "criticality", "responsible_party"]:
                if data.get(field):
                    qs = qs.filter(**{field: data[field]})

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["filter_form"] = self.filter_form
        ctx["can_add"] = self.request.user.has_perm("gaps.add_gap")
        ctx["can_change"] = self.request.user.has_perm("gaps.change_gap")
        ctx["can_delete"] = self.request.user.has_perm("gaps.delete_gap")
        return ctx


class GapDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = Gap
    permission_required = "gaps.view_gap"
    template_name = "gaps/gap_detail.html"
    context_object_name = "gap"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        if self.request.user.has_perm("audit.view_auditlog"):
            from audit.models import AuditLog

            ctx["audit_entries"] = AuditLog.objects.filter(
                app_label="gaps", model_name="gap", object_id=str(self.object.pk)
            ).select_related("user")[:20]
        return ctx


class GapCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Gap
    form_class = GapForm
    permission_required = "gaps.add_gap"
    template_name = "gaps/gap_form.html"

    def get_initial(self):
        initial = super().get_initial()
        client_id = self.request.GET.get("client")
        if client_id:
            initial["client"] = client_id
        return initial

    def get_success_url(self):
        return reverse("gaps:gap_detail", kwargs={"pk": self.object.pk})


class GapUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Gap
    form_class = GapForm
    permission_required = "gaps.change_gap"
    template_name = "gaps/gap_form.html"

    def get_success_url(self):
        return reverse("gaps:gap_detail", kwargs={"pk": self.object.pk})


class GapDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = Gap
    permission_required = "gaps.delete_gap"
    template_name = "gaps/gap_confirm_delete.html"
    success_url = reverse_lazy("gaps:gap_list")
