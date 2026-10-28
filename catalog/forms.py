from django import forms
from django.contrib.auth import get_user_model
from django.db.models import Q

from core.forms import BootstrapModelForm
from taxonomy.choices import CategoryScope, StatusScope
from taxonomy.models import Category, Status

from .models import (
    ClientLogSource,
    ClientUseCase,
    ImplementationTemplate,
    LogSource,
    TemplateLogSource,
    TemplateUseCase,
    UseCase,
)

User = get_user_model()


class LogSourceForm(BootstrapModelForm):
    class Meta:
        model = LogSource
        fields = ["name", "description", "category", "technology", "tags", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = Category.objects.filter(
            applicable_to__contains=[CategoryScope.LOG_SOURCE]
        )


class ClientLogSourceForm(BootstrapModelForm):
    class Meta:
        model = ClientLogSource
        fields = ["log_source", "status", "last_event_at", "notes"]
        widgets = {
            "last_event_at": forms.DateTimeInput(
                attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"
            ),
        }

    def __init__(self, *args, client=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["last_event_at"].input_formats = ["%Y-%m-%dT%H:%M"]
        self.client = client or getattr(self.instance, "client", None)

        used_ids = ClientLogSource.objects.filter(client=self.client).exclude(
            pk=self.instance.pk
        ).values_list("log_source_id", flat=True)
        self.fields["log_source"].queryset = LogSource.objects.filter(is_active=True).exclude(
            pk__in=used_ids
        )

        self.fields["status"].queryset = Status.objects.filter(
            Q(scope__contains=[StatusScope.CLIENT_LOG_SOURCE]) & Q(is_active=True)
            | Q(pk=self.instance.status_id)
        )
        self.fields["status"].required = False


class UseCaseForm(BootstrapModelForm):
    class Meta:
        model = UseCase
        fields = [
            "code", "name", "description", "objective", "category", "threat",
            "protects", "tags", "framework_controls", "notes", "is_active",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = Category.objects.filter(
            applicable_to__contains=[CategoryScope.USE_CASE]
        )


class ClientUseCaseForm(BootstrapModelForm):
    class Meta:
        model = ClientUseCase
        fields = ["use_case", "status", "criticality", "owner", "last_validated_at", "notes"]
        widgets = {"last_validated_at": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, client=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.client = client or getattr(self.instance, "client", None)

        used_ids = ClientUseCase.objects.filter(client=self.client).exclude(
            pk=self.instance.pk
        ).values_list("use_case_id", flat=True)
        self.fields["use_case"].queryset = UseCase.objects.filter(is_active=True).exclude(
            pk__in=used_ids
        )

        self.fields["status"].queryset = Status.objects.filter(
            Q(scope__contains=[StatusScope.CLIENT_USE_CASE]) & Q(is_active=True)
            | Q(pk=self.instance.status_id)
        )
        self.fields["status"].required = False
        self.fields["owner"].queryset = User.objects.filter(is_active=True).order_by("username")
        self.fields["owner"].required = False


class ImplementationTemplateForm(BootstrapModelForm):
    class Meta:
        model = ImplementationTemplate
        fields = ["name", "description", "is_active"]


class TemplateLogSourceForm(BootstrapModelForm):
    class Meta:
        model = TemplateLogSource
        fields = ["log_source"]

    def __init__(self, *args, template=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.template = template or getattr(self.instance, "template", None)
        used_ids = TemplateLogSource.objects.filter(template=self.template).exclude(
            pk=self.instance.pk
        ).values_list("log_source_id", flat=True)
        self.fields["log_source"].queryset = LogSource.objects.filter(is_active=True).exclude(
            pk__in=used_ids
        )


class TemplateUseCaseForm(BootstrapModelForm):
    class Meta:
        model = TemplateUseCase
        fields = ["use_case", "default_criticality"]

    def __init__(self, *args, template=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.template = template or getattr(self.instance, "template", None)
        used_ids = TemplateUseCase.objects.filter(template=self.template).exclude(
            pk=self.instance.pk
        ).values_list("use_case_id", flat=True)
        self.fields["use_case"].queryset = UseCase.objects.filter(is_active=True).exclude(
            pk__in=used_ids
        )
        self.fields["default_criticality"].required = False
