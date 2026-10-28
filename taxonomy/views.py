import json

from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse, reverse_lazy
from django.utils.text import slugify
from django.views import View
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from core.mixins import ProtectedDeleteMixin
from core.utils import parse_int_or_none

from .forms import FrameworkControlForm, FrameworkForm
from .models import Framework, FrameworkControl, Technology
from .registry import CATALOGS
from .services import build_navigator_layer


@login_required
def config_home(request):
    cards = []
    for key, cfg in CATALOGS.items():
        model_name = cfg["model"]._meta.model_name
        if request.user.has_perm(f"taxonomy.view_{model_name}"):
            cards.append({
                "key": key, "label": cfg["label"], "icon": cfg.get("icon", "bi-folder"),
                "description": cfg.get("description", ""),
                "count": cfg["model"].objects.count(),
            })

    show_frameworks = request.user.has_perm("taxonomy.view_framework")
    return render(
        request,
        "taxonomy/config_home.html",
        {
            "cards": cards,
            "show_frameworks": show_frameworks,
            "frameworks_count": Framework.objects.count() if show_frameworks else 0,
        },
    )


class CatalogPermissionMixin:
    """
    Resolves the catalog (model/form/label) from the `catalog` URL kwarg and
    enforces the matching Django model permission, so one set of views can
    serve every simple catalog without per-catalog view classes.
    """

    action = "view"

    def dispatch(self, request, *args, **kwargs):
        self.catalog_key = kwargs.get("catalog")
        self.catalog = CATALOGS.get(self.catalog_key)
        if self.catalog is None:
            raise Http404("Catálogo desconhecido.")
        self.model = self.catalog["model"]
        perm = f"taxonomy.{self.action}_{self.model._meta.model_name}"
        if not request.user.has_perm(perm):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(
            catalog_key=self.catalog_key,
            label=self.catalog["label"],
            description=self.catalog.get("description", ""),
        )
        return ctx


class CatalogListView(LoginRequiredMixin, CatalogPermissionMixin, ListView):
    action = "view"
    template_name = "taxonomy/catalog_list.html"
    context_object_name = "objects"

    def get_queryset(self):
        return self.model.objects.all()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["list_fields"] = self.catalog["list_fields"]
        ctx["can_add"] = self.request.user.has_perm(f"taxonomy.add_{self.model._meta.model_name}")
        ctx["can_change"] = self.request.user.has_perm(f"taxonomy.change_{self.model._meta.model_name}")
        ctx["can_delete"] = self.request.user.has_perm(f"taxonomy.delete_{self.model._meta.model_name}")
        return ctx


class CatalogFormMixin(CatalogPermissionMixin):
    template_name = "taxonomy/catalog_form.html"

    def get_form_class(self):
        return self.catalog["form"]

    def get_success_url(self):
        return reverse("taxonomy:catalog_list", kwargs={"catalog": self.catalog_key})


class CatalogCreateView(LoginRequiredMixin, CatalogFormMixin, CreateView):
    action = "add"


class CatalogUpdateView(LoginRequiredMixin, CatalogFormMixin, UpdateView):
    action = "change"


class CatalogDeleteView(LoginRequiredMixin, CatalogPermissionMixin, ProtectedDeleteMixin, DeleteView):
    action = "delete"
    template_name = "taxonomy/catalog_confirm_delete.html"

    def get_success_url(self):
        return reverse("taxonomy:catalog_list", kwargs={"catalog": self.catalog_key})


# --- Frameworks: nested shape (framework -> controls), dedicated views ---


class FrameworkListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Framework
    permission_required = "taxonomy.view_framework"
    template_name = "taxonomy/framework_list.html"
    context_object_name = "frameworks"


class FrameworkDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = Framework
    permission_required = "taxonomy.view_framework"
    template_name = "taxonomy/framework_detail.html"
    context_object_name = "framework"

    def get_context_data(self, **kwargs):
        from clients.models import Client

        ctx = super().get_context_data(**kwargs)
        ctx["controls"] = self.object.controls.select_related("parent").all()
        ctx["can_manage_controls"] = self.request.user.has_perm("taxonomy.add_frameworkcontrol")
        ctx["all_clients"] = Client.objects.all()
        return ctx


class FrameworkCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Framework
    form_class = FrameworkForm
    permission_required = "taxonomy.add_framework"
    template_name = "taxonomy/framework_form.html"
    success_url = reverse_lazy("taxonomy:framework_list")


class FrameworkUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Framework
    form_class = FrameworkForm
    permission_required = "taxonomy.change_framework"
    template_name = "taxonomy/framework_form.html"

    def get_success_url(self):
        return reverse("taxonomy:framework_detail", kwargs={"pk": self.object.pk})


class FrameworkDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = Framework
    permission_required = "taxonomy.delete_framework"
    template_name = "taxonomy/framework_confirm_delete.html"
    success_url = reverse_lazy("taxonomy:framework_list")


class FrameworkNavigatorExportView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """
    Downloads this Framework's coverage as a MITRE ATT&CK Navigator layer
    JSON - meant for Frameworks whose control codes are ATT&CK technique
    IDs (e.g. "T1110"), but technically works for any Framework since it
    only reads code/rule links. Optional ?client=/?technology= narrow the
    count, mirroring the Dashboard's own filters.
    """

    permission_required = "taxonomy.view_framework"

    def get(self, request, pk):
        from clients.models import Client

        framework = get_object_or_404(Framework, pk=pk)
        client = None
        technology = None
        client_id = parse_int_or_none(request.GET.get("client"))
        technology_id = parse_int_or_none(request.GET.get("technology"))
        if client_id:
            client = Client.objects.filter(pk=client_id).first()
        if technology_id:
            technology = Technology.objects.filter(pk=technology_id).first()

        layer = build_navigator_layer(framework, client=client, technology=technology)
        response = HttpResponse(
            json.dumps(layer, ensure_ascii=False, indent=2), content_type="application/json"
        )
        response["Content-Disposition"] = f'attachment; filename="{slugify(framework.name)}-navigator-layer.json"'
        return response


class FrameworkControlFormMixin:
    model = FrameworkControl
    form_class = FrameworkControlForm
    template_name = "taxonomy/frameworkcontrol_form.html"

    def dispatch(self, request, *args, **kwargs):
        framework_pk = kwargs.get("framework_pk") or self._framework_pk_from_object(kwargs)
        self.framework = get_object_or_404(Framework, pk=framework_pk)
        return super().dispatch(request, *args, **kwargs)

    def _framework_pk_from_object(self, kwargs):
        obj = get_object_or_404(FrameworkControl, pk=kwargs["pk"])
        return obj.framework_id

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["framework"] = self.framework
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["framework"] = self.framework
        return ctx

    def get_success_url(self):
        return reverse("taxonomy:framework_detail", kwargs={"pk": self.framework.pk})


class FrameworkControlCreateView(
    LoginRequiredMixin, PermissionRequiredMixin, FrameworkControlFormMixin, CreateView
):
    permission_required = "taxonomy.add_frameworkcontrol"

    def form_valid(self, form):
        form.instance.framework = self.framework
        return super().form_valid(form)


class FrameworkControlUpdateView(
    LoginRequiredMixin, PermissionRequiredMixin, FrameworkControlFormMixin, UpdateView
):
    permission_required = "taxonomy.change_frameworkcontrol"


class FrameworkControlDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = FrameworkControl
    permission_required = "taxonomy.delete_frameworkcontrol"
    template_name = "taxonomy/frameworkcontrol_confirm_delete.html"

    def get_success_url(self):
        return reverse("taxonomy:framework_detail", kwargs={"pk": self.object.framework_id})
