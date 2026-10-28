from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db.models import Q
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View
from django.views.generic import CreateView, DeleteView, DetailView, FormView, ListView, UpdateView

from core.utils import parse_int_or_none

from .forms import RuleColumnPreferenceForm, RuleFilterForm, RuleForm, RuleImportForm
from .models import AVAILABLE_RULE_COLUMNS, DEFAULT_RULE_COLUMNS, Rule, RuleColumnPreference
from .services import import_rules_from_csv, rule_is_possibly_inoperative, rule_is_review_overdue


class RuleListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Rule
    permission_required = "detections.view_rule"
    template_name = "detections/rule_list.html"
    context_object_name = "rules"
    paginate_by = 25

    def get_queryset(self):
        self.filter_form = RuleFilterForm(self.request.GET or None)
        qs = Rule.objects.select_related(
            "client", "technology", "severity", "status", "log_source", "rule_type", "category"
        ).prefetch_related("tags", "framework_controls__framework")

        if self.filter_form.is_valid():
            data = self.filter_form.cleaned_data
            if data.get("q"):
                q = data["q"]
                qs = qs.filter(
                    Q(internal_id__icontains=q)
                    | Q(name__icontains=q)
                    | Q(vendor_rule_id__icontains=q)
                    | Q(description__icontains=q)
                )
            for field in ["client", "technology", "status", "severity", "log_source", "category"]:
                if data.get(field):
                    qs = qs.filter(**{field: data[field]})
            if data.get("use_case"):
                qs = qs.filter(use_cases=data["use_case"])
            if data.get("framework"):
                qs = qs.filter(framework_controls__framework=data["framework"])
            if data.get("tag"):
                qs = qs.filter(tags=data["tag"])
            review_status = data.get("review_status")
            if review_status == "overdue":
                qs = qs.filter(next_review_at__lt=timezone.localdate())
            elif review_status == "undated":
                qs = qs.filter(next_review_at__isnull=True)

        # Not part of the filter form: the Cyber Kill Chain widget on the
        # dashboard links straight to a stage via ?stage=<FrameworkControl id>.
        stage_id = parse_int_or_none(self.request.GET.get("stage"))
        if stage_id:
            qs = qs.filter(framework_controls__id=stage_id)

        return qs.distinct()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        pref = RuleColumnPreference.objects.filter(user=self.request.user).first()
        visible = (pref.visible_columns if pref and pref.visible_columns else DEFAULT_RULE_COLUMNS)

        for rule in ctx["rules"]:
            rule.is_review_overdue = rule_is_review_overdue(rule)
            rule.is_possibly_inoperative = rule_is_possibly_inoperative(rule)

        advanced_fields = [
            "client", "technology", "status", "severity", "log_source",
            "use_case", "category", "framework", "tag", "review_status",
        ]
        ctx["has_advanced_filters"] = any(self.request.GET.get(f) for f in advanced_fields)
        stage_id = parse_int_or_none(self.request.GET.get("stage"))
        if stage_id:
            from taxonomy.models import FrameworkControl
            ctx["active_stage"] = FrameworkControl.objects.filter(pk=stage_id).select_related("framework").first()
        ctx["filter_form"] = self.filter_form
        ctx["visible_columns"] = visible
        ctx["available_columns"] = AVAILABLE_RULE_COLUMNS
        ctx["column_form"] = RuleColumnPreferenceForm(initial={"columns": visible})
        ctx["can_add"] = self.request.user.has_perm("detections.add_rule")
        ctx["can_change"] = self.request.user.has_perm("detections.change_rule")
        ctx["can_delete"] = self.request.user.has_perm("detections.delete_rule")
        ctx["can_import"] = self.request.user.has_perm("detections.add_rule")
        return ctx


class RuleDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = Rule
    permission_required = "detections.view_rule"
    template_name = "detections/rule_detail.html"
    context_object_name = "rule"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["is_review_overdue"] = rule_is_review_overdue(self.object)
        ctx["is_possibly_inoperative"] = rule_is_possibly_inoperative(self.object)

        if self.request.user.has_perm("audit.view_auditlog"):
            from audit.models import AuditLog

            ctx["audit_entries"] = AuditLog.objects.filter(
                app_label="detections", model_name="rule", object_id=str(self.object.pk)
            ).select_related("user")[:20]
        return ctx


class RuleCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Rule
    form_class = RuleForm
    permission_required = "detections.add_rule"
    template_name = "detections/rule_form.html"

    def get_success_url(self):
        return reverse("detections:rule_detail", kwargs={"pk": self.object.pk})


class RuleUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Rule
    form_class = RuleForm
    permission_required = "detections.change_rule"
    template_name = "detections/rule_form.html"

    def get_success_url(self):
        return reverse("detections:rule_detail", kwargs={"pk": self.object.pk})


class RuleDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = Rule
    permission_required = "detections.delete_rule"
    template_name = "detections/rule_confirm_delete.html"
    success_url = reverse_lazy("detections:rule_list")


class RuleColumnPreferenceUpdateView(LoginRequiredMixin, View):
    def post(self, request):
        form = RuleColumnPreferenceForm(request.POST)
        if form.is_valid():
            columns = form.cleaned_data["columns"] or DEFAULT_RULE_COLUMNS
            RuleColumnPreference.objects.update_or_create(
                user=request.user, defaults={"visible_columns": columns}
            )
        next_url = request.POST.get("next")
        if not next_url or not url_has_allowed_host_and_scheme(
            next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
        ):
            next_url = reverse("detections:rule_list")
        return redirect(next_url)


class RuleImportView(LoginRequiredMixin, PermissionRequiredMixin, FormView):
    form_class = RuleImportForm
    permission_required = "detections.add_rule"
    template_name = "detections/rule_import.html"

    def form_valid(self, form):
        report = import_rules_from_csv(form.cleaned_data["file"])
        return self.render_to_response(self.get_context_data(form=self.form_class(), report=report))
