from django import forms

from core.forms import BootstrapModelForm

from .choices import CategoryScope, StatusCategory, StatusScope
from .models import (
    Category,
    Framework,
    FrameworkControl,
    ResponsibleParty,
    RuleType,
    Severity,
    Status,
    Tag,
    Technology,
)


class TechnologyForm(BootstrapModelForm):
    class Meta:
        model = Technology
        fields = ["name", "code", "description", "category", "color", "icon", "order", "is_active"]


class StatusForm(BootstrapModelForm):
    scope = forms.MultipleChoiceField(
        choices=StatusScope.choices,
        widget=forms.SelectMultiple(attrs={"class": "form-select"}),
        required=False,
        label="Entidades onde pode ser usado",
    )
    category = forms.ChoiceField(
        choices=StatusCategory.choices,
        label="Semântica interna",
        help_text="Usada pelas regras de negócio (cobertura, inconsistências). Não altera o texto exibido.",
    )

    class Meta:
        model = Status
        fields = ["name", "code", "description", "scope", "category", "color", "icon", "order", "is_active"]


class SeverityForm(BootstrapModelForm):
    class Meta:
        model = Severity
        fields = ["name", "code", "description", "weight", "color", "icon", "order", "is_active"]


class CategoryForm(BootstrapModelForm):
    applicable_to = forms.MultipleChoiceField(
        choices=CategoryScope.choices,
        widget=forms.SelectMultiple(attrs={"class": "form-select"}),
        required=False,
        label="Aplicável a",
    )

    class Meta:
        model = Category
        fields = ["name", "code", "description", "applicable_to", "color", "icon", "order", "is_active"]


class TagForm(BootstrapModelForm):
    class Meta:
        model = Tag
        fields = ["name", "code", "description", "color", "icon", "order", "is_active"]


class RuleTypeForm(BootstrapModelForm):
    class Meta:
        model = RuleType
        fields = ["name", "code", "description", "color", "icon", "order", "is_active"]


class ResponsiblePartyForm(BootstrapModelForm):
    class Meta:
        model = ResponsibleParty
        fields = ["name", "code", "is_client", "description", "color", "icon", "order", "is_active"]


class FrameworkForm(BootstrapModelForm):
    class Meta:
        model = Framework
        fields = ["name", "version", "description", "url", "is_active"]


class FrameworkControlForm(BootstrapModelForm):
    class Meta:
        model = FrameworkControl
        fields = ["code", "name", "parent", "description", "url", "is_active"]

    def __init__(self, *args, framework=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.framework = framework or self.instance.framework
        self.fields["parent"].queryset = FrameworkControl.objects.filter(
            framework=framework or self.instance.framework
        ).exclude(pk=self.instance.pk)
