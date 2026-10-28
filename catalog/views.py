from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from clients.models import Client
from core.mixins import ProtectedDeleteMixin

from .forms import (
    ClientLogSourceForm,
    ClientUseCaseForm,
    ImplementationTemplateForm,
    LogSourceForm,
    TemplateLogSourceForm,
    TemplateUseCaseForm,
    UseCaseForm,
)
from .models import (
    ClientLogSource,
    ClientUseCase,
    ImplementationTemplate,
    LogSource,
    TemplateLogSource,
    TemplateUseCase,
    UseCase,
)
from .services import apply_template_to_client


class LogSourceListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = LogSource
    permission_required = "catalog.view_logsource"
    template_name = "catalog/logsource_list.html"
    context_object_name = "log_sources"

    def get_queryset(self):
        qs = LogSource.objects.select_related("category", "technology").prefetch_related("tags")
        query = self.request.GET.get("q", "").strip()
        if query:
            qs = qs.filter(Q(name__icontains=query) | Q(description__icontains=query))
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["query"] = self.request.GET.get("q", "")
        ctx["can_add"] = self.request.user.has_perm("catalog.add_logsource")
        ctx["can_change"] = self.request.user.has_perm("catalog.change_logsource")
        ctx["can_delete"] = self.request.user.has_perm("catalog.delete_logsource")
        return ctx


class LogSourceCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = LogSource
    form_class = LogSourceForm
    permission_required = "catalog.add_logsource"
    template_name = "catalog/logsource_form.html"
    success_url = reverse_lazy("catalog:logsource_list")


class LogSourceUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = LogSource
    form_class = LogSourceForm
    permission_required = "catalog.change_logsource"
    template_name = "catalog/logsource_form.html"
    success_url = reverse_lazy("catalog:logsource_list")


class LogSourceDeleteView(LoginRequiredMixin, PermissionRequiredMixin, ProtectedDeleteMixin, DeleteView):
    model = LogSource
    permission_required = "catalog.delete_logsource"
    template_name = "catalog/logsource_confirm_delete.html"
    success_url = reverse_lazy("catalog:logsource_list")


class ClientLogSourceFormMixin:
    model = ClientLogSource
    form_class = ClientLogSourceForm
    template_name = "catalog/clientlogsource_form.html"

    def dispatch(self, request, *args, **kwargs):
        client_pk = kwargs.get("client_pk") or self._client_pk_from_object(kwargs)
        self.client_obj = get_object_or_404(Client, pk=client_pk)
        return super().dispatch(request, *args, **kwargs)

    def _client_pk_from_object(self, kwargs):
        obj = get_object_or_404(ClientLogSource, pk=kwargs["pk"])
        return obj.client_id

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["client"] = self.client_obj
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["client_obj"] = self.client_obj
        return ctx

    def get_success_url(self):
        return reverse("clients:client_detail", kwargs={"pk": self.client_obj.pk})


class ClientLogSourceCreateView(
    LoginRequiredMixin, PermissionRequiredMixin, ClientLogSourceFormMixin, CreateView
):
    permission_required = "catalog.add_clientlogsource"

    def form_valid(self, form):
        form.instance.client = self.client_obj
        return super().form_valid(form)


class ClientLogSourceUpdateView(
    LoginRequiredMixin, PermissionRequiredMixin, ClientLogSourceFormMixin, UpdateView
):
    permission_required = "catalog.change_clientlogsource"


class ClientLogSourceDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = ClientLogSource
    permission_required = "catalog.delete_clientlogsource"
    template_name = "catalog/clientlogsource_confirm_delete.html"

    def get_success_url(self):
        return reverse("clients:client_detail", kwargs={"pk": self.object.client_id})


# --- UseCase: global catalog (mirrors LogSource) ---


class UseCaseListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = UseCase
    permission_required = "catalog.view_usecase"
    template_name = "catalog/usecase_list.html"
    context_object_name = "use_cases"

    def get_queryset(self):
        qs = UseCase.objects.select_related("category").prefetch_related("tags")
        query = self.request.GET.get("q", "").strip()
        if query:
            qs = qs.filter(Q(code__icontains=query) | Q(name__icontains=query))
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["query"] = self.request.GET.get("q", "")
        ctx["can_add"] = self.request.user.has_perm("catalog.add_usecase")
        ctx["can_change"] = self.request.user.has_perm("catalog.change_usecase")
        ctx["can_delete"] = self.request.user.has_perm("catalog.delete_usecase")
        return ctx


class UseCaseCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = UseCase
    form_class = UseCaseForm
    permission_required = "catalog.add_usecase"
    template_name = "catalog/usecase_form.html"
    success_url = reverse_lazy("catalog:usecase_list")


class UseCaseUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = UseCase
    form_class = UseCaseForm
    permission_required = "catalog.change_usecase"
    template_name = "catalog/usecase_form.html"
    success_url = reverse_lazy("catalog:usecase_list")


class UseCaseDeleteView(LoginRequiredMixin, PermissionRequiredMixin, ProtectedDeleteMixin, DeleteView):
    model = UseCase
    permission_required = "catalog.delete_usecase"
    template_name = "catalog/usecase_confirm_delete.html"
    success_url = reverse_lazy("catalog:usecase_list")


# --- ClientUseCase: per-client coverage (mirrors ClientLogSource) ---


class ClientUseCaseFormMixin:
    model = ClientUseCase
    form_class = ClientUseCaseForm
    template_name = "catalog/clientusecase_form.html"

    def dispatch(self, request, *args, **kwargs):
        client_pk = kwargs.get("client_pk") or self._client_pk_from_object(kwargs)
        self.client_obj = get_object_or_404(Client, pk=client_pk)
        return super().dispatch(request, *args, **kwargs)

    def _client_pk_from_object(self, kwargs):
        obj = get_object_or_404(ClientUseCase, pk=kwargs["pk"])
        return obj.client_id

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["client"] = self.client_obj
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["client_obj"] = self.client_obj
        return ctx

    def get_success_url(self):
        return reverse("clients:client_detail", kwargs={"pk": self.client_obj.pk})


class ClientUseCaseCreateView(
    LoginRequiredMixin, PermissionRequiredMixin, ClientUseCaseFormMixin, CreateView
):
    permission_required = "catalog.add_clientusecase"

    def form_valid(self, form):
        form.instance.client = self.client_obj
        return super().form_valid(form)


class ClientUseCaseUpdateView(
    LoginRequiredMixin, PermissionRequiredMixin, ClientUseCaseFormMixin, UpdateView
):
    permission_required = "catalog.change_clientusecase"


class ClientUseCaseDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = ClientUseCase
    permission_required = "catalog.delete_clientusecase"
    template_name = "catalog/clientusecase_confirm_delete.html"

    def get_success_url(self):
        return reverse("clients:client_detail", kwargs={"pk": self.object.client_id})


# --- Implementation templates: bundle of log sources + use cases ---


class TemplateListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = ImplementationTemplate
    permission_required = "catalog.view_implementationtemplate"
    template_name = "catalog/template_list.html"
    context_object_name = "templates"


class TemplateDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = ImplementationTemplate
    permission_required = "catalog.view_implementationtemplate"
    template_name = "catalog/template_detail.html"
    context_object_name = "template"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["log_source_items"] = self.object.log_sources.select_related("log_source").all()
        ctx["use_case_items"] = self.object.use_cases.select_related("use_case", "default_criticality").all()
        ctx["can_manage"] = self.request.user.has_perm("catalog.add_templatelogsource")
        return ctx


class TemplateCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = ImplementationTemplate
    form_class = ImplementationTemplateForm
    permission_required = "catalog.add_implementationtemplate"
    template_name = "catalog/template_form.html"
    success_url = reverse_lazy("catalog:template_list")


class TemplateUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = ImplementationTemplate
    form_class = ImplementationTemplateForm
    permission_required = "catalog.change_implementationtemplate"
    template_name = "catalog/template_form.html"

    def get_success_url(self):
        return reverse("catalog:template_detail", kwargs={"pk": self.object.pk})


class TemplateDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = ImplementationTemplate
    permission_required = "catalog.delete_implementationtemplate"
    template_name = "catalog/template_confirm_delete.html"
    success_url = reverse_lazy("catalog:template_list")


class TemplateLogSourceCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = TemplateLogSource
    form_class = TemplateLogSourceForm
    permission_required = "catalog.add_templatelogsource"
    template_name = "catalog/templatelogsource_form.html"

    def dispatch(self, request, *args, **kwargs):
        self.template_obj = get_object_or_404(ImplementationTemplate, pk=kwargs["template_pk"])
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["template"] = self.template_obj
        return kwargs

    def form_valid(self, form):
        form.instance.template = self.template_obj
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["template"] = self.template_obj
        return ctx

    def get_success_url(self):
        return reverse("catalog:template_detail", kwargs={"pk": self.template_obj.pk})


class TemplateLogSourceDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = TemplateLogSource
    permission_required = "catalog.delete_templatelogsource"
    template_name = "catalog/templatelogsource_confirm_delete.html"

    def get_success_url(self):
        return reverse("catalog:template_detail", kwargs={"pk": self.object.template_id})


class TemplateUseCaseCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = TemplateUseCase
    form_class = TemplateUseCaseForm
    permission_required = "catalog.add_templateusecase"
    template_name = "catalog/templateusecase_form.html"

    def dispatch(self, request, *args, **kwargs):
        self.template_obj = get_object_or_404(ImplementationTemplate, pk=kwargs["template_pk"])
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["template"] = self.template_obj
        return kwargs

    def form_valid(self, form):
        form.instance.template = self.template_obj
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["template"] = self.template_obj
        return ctx

    def get_success_url(self):
        return reverse("catalog:template_detail", kwargs={"pk": self.template_obj.pk})


class TemplateUseCaseDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = TemplateUseCase
    permission_required = "catalog.delete_templateusecase"
    template_name = "catalog/templateusecase_confirm_delete.html"

    def get_success_url(self):
        return reverse("catalog:template_detail", kwargs={"pk": self.object.template_id})


class ApplyTemplateView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """Applies a template to a client: creates the missing ClientLogSource/
    ClientUseCase rows. Additive and idempotent, so no confirmation page."""

    permission_required = "catalog.add_clientusecase"

    def post(self, request, client_pk):
        client_obj = get_object_or_404(Client, pk=client_pk)
        template = get_object_or_404(ImplementationTemplate, pk=request.POST.get("template"))
        result = apply_template_to_client(template, client_obj)
        messages.success(
            request,
            f'Template "{template.name}" aplicado: {result["log_sources"]} fonte(s) de log e '
            f'{result["use_cases"]} caso(s) de uso adicionados (itens já existentes não foram duplicados).',
        )
        return redirect("clients:client_detail", pk=client_obj.pk)
