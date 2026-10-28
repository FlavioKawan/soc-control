from django import forms

from .models import AuditLog


class AuditLogFilterForm(forms.Form):
    q = forms.CharField(required=False, label="Buscar")
    client = forms.ModelChoiceField(queryset=None, required=False, label="Cliente")
    action = forms.ChoiceField(choices=[("", "Todas")] + AuditLog.Action.choices, required=False, label="Ação")
    model_name = forms.ChoiceField(required=False, label="Entidade")
    user = forms.ModelChoiceField(queryset=None, required=False, label="Usuário")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from django.contrib.auth import get_user_model

        from clients.models import Client

        from .signals import TRACKED_MODELS

        self.fields["client"].queryset = Client.objects.all()
        self.fields["user"].queryset = get_user_model().objects.order_by("username")
        self.fields["model_name"].choices = [("", "Todas")] + [
            (model._meta.model_name, model._meta.verbose_name.title()) for model in TRACKED_MODELS
        ]
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.Select):
                widget.attrs.setdefault("class", "form-select form-select-sm")
            else:
                widget.attrs.setdefault("class", "form-control form-control-sm")
