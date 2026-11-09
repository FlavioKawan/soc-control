from django import forms
from django.db.models import Q

from clients.services import has_full_client_visibility, visible_clients
from core.forms import BootstrapModelForm
from taxonomy.choices import StatusScope
from taxonomy.models import ResponsibleParty, Severity, Status

from .models import Gap


class GapForm(BootstrapModelForm):
    class Meta:
        model = Gap
        fields = [
            "code", "client", "title", "description", "impact", "criticality",
            "responsible_party", "status", "recommendation", "opened_at", "closed_at",
            "notes", "log_source", "use_case", "rule", "tags",
        ]
        widgets = {
            "opened_at": forms.DateInput(attrs={"type": "date"}),
            "closed_at": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        # A restricted ANALYST/VIEWER can only open a gap for a client
        # they're assigned to.
        if user is not None and not has_full_client_visibility(user):
            self.fields["client"].queryset = visible_clients(user)
        self.fields["status"].queryset = Status.objects.filter(
            Q(scope__contains=[StatusScope.GAP]) & Q(is_active=True) | Q(pk=self.instance.status_id)
        )
        self.fields["status"].required = False
        self.fields["responsible_party"].queryset = ResponsibleParty.objects.filter(
            Q(is_active=True) | Q(pk=self.instance.responsible_party_id)
        )
        for field in ("responsible_party", "criticality", "closed_at", "log_source", "use_case", "rule", "tags"):
            self.fields[field].required = False

        # Optional relationships only make sense scoped to the gap's own client,
        # but the client itself may not be chosen yet (new Gap) - fall back to "all".
        client_id = self.data.get("client") or self.initial.get("client") or getattr(self.instance, "client_id", None)
        if client_id:
            self.fields["use_case"].queryset = self.fields["use_case"].queryset.filter(
                client_links__client_id=client_id
            ).distinct()
            self.fields["log_source"].queryset = self.fields["log_source"].queryset.filter(
                client_links__client_id=client_id
            ).distinct()
            self.fields["rule"].queryset = self.fields["rule"].queryset.filter(client_id=client_id)


class GapFilterForm(forms.Form):
    q = forms.CharField(required=False, label="Buscar")
    client = forms.ModelChoiceField(queryset=None, required=False, label="Cliente")
    status = forms.ModelChoiceField(queryset=None, required=False, label="Status")
    criticality = forms.ModelChoiceField(queryset=None, required=False, label="Criticidade")
    responsible_party = forms.ModelChoiceField(queryset=None, required=False, label="Responsável")

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        from clients.models import Client

        # Not a security boundary by itself (GapListView's base queryset is
        # already client-scoped) - just keeps other clients' names out of a
        # restricted user's filter dropdown.
        self.fields["client"].queryset = visible_clients(user) if user is not None else Client.objects.all()
        self.fields["status"].queryset = Status.objects.filter(scope__contains=[StatusScope.GAP])
        self.fields["criticality"].queryset = Severity.objects.all()
        self.fields["responsible_party"].queryset = ResponsibleParty.objects.all()
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.Select):
                widget.attrs.setdefault("class", "form-select form-select-sm")
            else:
                widget.attrs.setdefault("class", "form-control form-control-sm")
