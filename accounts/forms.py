from django import forms
from django.contrib.auth.forms import SetPasswordForm, UserCreationForm
from django.contrib.auth.models import Group, User


def _bootstrap(fields):
    """
    Same idea as core.forms.BootstrapModelForm, but skips checkbox-list
    widgets (e.g. `groups`): those are rendered by hand in the template as
    Bootstrap form-check rows, the same way detections.RuleColumnPreferenceForm
    already does for its own CheckboxSelectMultiple field.
    """
    for name, field in fields.items():
        widget = field.widget
        if isinstance(widget, forms.CheckboxSelectMultiple):
            continue
        if isinstance(widget, forms.CheckboxInput):
            widget.attrs.setdefault("class", "form-check-input")
        elif isinstance(widget, (forms.Select, forms.SelectMultiple)):
            widget.attrs.setdefault("class", "form-select")
        else:
            widget.attrs.setdefault("class", "form-control")


class PlatformUserCreateForm(UserCreationForm):
    """
    Creates a platform login for the "Usuários" screen. Wraps Django's own
    UserCreationForm (keeps its password confirmation + strength validators)
    and adds the profile/role fields the screen needs.

    `is_superuser` is deliberately left out: that bypasses the permission
    system entirely, so granting it stays an /admin/-only action, same as
    today. Group membership is enough to reach ADMIN-level access (see
    accounts/management/commands/setup_roles.py), which already gets every
    permission including auth.* user management.
    """

    groups = forms.ModelMultipleChoiceField(
        queryset=Group.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Grupos",
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ["username", "first_name", "last_name", "email", "is_active", "groups"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["is_active"].initial = True
        _bootstrap(self.fields)


class PlatformUserUpdateForm(forms.ModelForm):
    """Edits profile/role fields only - password changes go through PlatformUserPasswordResetForm."""

    groups = forms.ModelMultipleChoiceField(
        queryset=Group.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Grupos",
    )

    class Meta:
        model = User
        fields = ["username", "first_name", "last_name", "email", "is_active", "groups"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _bootstrap(self.fields)


class PlatformUserPasswordResetForm(SetPasswordForm):
    """Lets an ADMIN set a new password for another user without knowing the old one."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _bootstrap(self.fields)
