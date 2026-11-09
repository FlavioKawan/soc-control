from itertools import groupby

from django import forms
from django.db.models import Q

from core.forms import BootstrapModelForm
from catalog.models import LogSource, UseCase
from clients.models import Client
from clients.services import has_full_client_visibility, visible_clients
from taxonomy.choices import CategoryScope, StatusScope
from taxonomy.models import Category, Framework, FrameworkControl, RuleType, Severity, Status, Tag, Technology

from .models import AVAILABLE_RULE_COLUMNS, Rule


class RuleForm(BootstrapModelForm):
    class Meta:
        model = Rule
        fields = [
            "internal_id", "vendor_rule_id", "name", "client", "technology", "rule_type",
            "description", "objective", "log_source", "original_level", "severity", "status",
            "category", "protects", "threat", "use_cases", "framework_controls", "tags",
            "last_reviewed_at", "next_review_at", "notes",
        ]
        widgets = {
            "last_reviewed_at": forms.DateInput(attrs={"type": "date"}),
            "next_review_at": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        # A restricted ANALYST/VIEWER can only create/move a rule into a
        # client they're assigned to - not just any client in the system.
        if user is not None and not has_full_client_visibility(user):
            self.fields["client"].queryset = visible_clients(user)
        self.fields["category"].queryset = Category.objects.filter(
            applicable_to__contains=[CategoryScope.RULE]
        )
        self.fields["status"].queryset = Status.objects.filter(
            Q(scope__contains=[StatusScope.RULE]) & Q(is_active=True) | Q(pk=self.instance.status_id)
        )
        self.fields["status"].required = False
        self.fields["log_source"].queryset = LogSource.objects.filter(is_active=True)
        self.fields["use_cases"].queryset = UseCase.objects.filter(is_active=True)
        for field in ("vendor_rule_id", "rule_type", "log_source", "severity", "category", "use_cases",
                      "framework_controls", "tags", "last_reviewed_at", "next_review_at"):
            self.fields[field].required = False

        # Group MITRE techniques, Cyber Kill Chain stages, etc. under their
        # own <optgroup> so they don't blur into one flat, growing list.
        controls = FrameworkControl.objects.filter(is_active=True).select_related("framework").order_by(
            "framework__name", "code"
        )
        self.fields["framework_controls"].choices = [
            (framework_name, [(c.pk, f"{c.code} - {c.name}") for c in items])
            for framework_name, items in groupby(controls, key=lambda c: c.framework.name)
        ]


class RuleFilterForm(forms.Form):
    q = forms.CharField(
        required=False, label="", strip=True,
        widget=forms.TextInput(attrs={"placeholder": "Buscar por ID, nome, descrição..."}),
    )
    client = forms.ModelChoiceField(queryset=None, required=False, label="Cliente")
    technology = forms.ModelChoiceField(queryset=None, required=False, label="Tecnologia")
    status = forms.ModelChoiceField(queryset=None, required=False, label="Status")
    severity = forms.ModelChoiceField(queryset=None, required=False, label="Severidade")
    log_source = forms.ModelChoiceField(queryset=None, required=False, label="Fonte")
    use_case = forms.ModelChoiceField(queryset=None, required=False, label="Caso de Uso")
    category = forms.ModelChoiceField(queryset=None, required=False, label="Categoria")
    framework = forms.ModelChoiceField(queryset=None, required=False, label="Framework")
    tag = forms.ModelChoiceField(queryset=None, required=False, label="Tag")
    review_status = forms.ChoiceField(
        required=False,
        label="Revisão",
        choices=[("", "Todas"), ("overdue", "Revisão pendente"), ("undated", "Sem data definida")],
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Not a security boundary by itself (RuleListView's base queryset is
        # already client-scoped) - just keeps other clients' names out of a
        # restricted user's filter dropdown.
        self.fields["client"].queryset = visible_clients(user) if user is not None else Client.objects.all()
        self.fields["technology"].queryset = Technology.objects.all()
        self.fields["status"].queryset = Status.objects.filter(scope__contains=[StatusScope.RULE])
        self.fields["severity"].queryset = Severity.objects.all()
        self.fields["log_source"].queryset = LogSource.objects.all()
        self.fields["use_case"].queryset = UseCase.objects.all()
        self.fields["category"].queryset = Category.objects.filter(
            applicable_to__contains=[CategoryScope.RULE]
        )
        self.fields["framework"].queryset = Framework.objects.all()
        self.fields["tag"].queryset = Tag.objects.all()
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.Select):
                widget.attrs.setdefault("class", "form-select form-select-sm")
            else:
                widget.attrs.setdefault("class", "form-control form-control-sm")


class RuleColumnPreferenceForm(forms.Form):
    columns = forms.MultipleChoiceField(
        choices=AVAILABLE_RULE_COLUMNS,
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Colunas visíveis",
    )


class RuleImportForm(forms.Form):
    file = forms.FileField(label="Arquivo CSV")

    def clean_file(self):
        f = self.cleaned_data["file"]
        if not f.name.lower().endswith(".csv"):
            raise forms.ValidationError("Envie um arquivo .csv.")
        return f
