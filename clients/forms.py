from django.contrib.auth import get_user_model
from django.db.models import Q

from core.forms import BootstrapModelForm
from taxonomy.choices import StatusScope
from taxonomy.models import Status

from .models import Client
from .services import has_full_client_visibility


class ClientForm(BootstrapModelForm):
    class Meta:
        model = Client
        fields = ["name", "legal_name", "status", "notes", "assigned_users"]

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Only offer statuses scoped to Client, but keep showing the
        # currently selected one even if it was since deactivated.
        self.fields["status"].queryset = Status.objects.filter(
            Q(scope__contains=[StatusScope.CLIENT]) & Q(is_active=True)
            | Q(pk=self.instance.status_id)
        )
        self.fields["status"].required = False
        self.fields["assigned_users"].required = False
        self.fields["assigned_users"].queryset = get_user_model().objects.filter(is_active=True)
        # Deciding who has access to a client is itself restricted to who
        # already sees every client - a restricted ANALYST/VIEWER can't
        # grant themselves (or anyone else) access to more clients.
        if user is not None and not has_full_client_visibility(user):
            del self.fields["assigned_users"]
