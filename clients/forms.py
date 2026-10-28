from django.db.models import Q

from core.forms import BootstrapModelForm
from taxonomy.choices import StatusScope
from taxonomy.models import Status

from .models import Client


class ClientForm(BootstrapModelForm):
    class Meta:
        model = Client
        fields = ["name", "legal_name", "status", "notes"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only offer statuses scoped to Client, but keep showing the
        # currently selected one even if it was since deactivated.
        self.fields["status"].queryset = Status.objects.filter(
            Q(scope__contains=[StatusScope.CLIENT]) & Q(is_active=True)
            | Q(pk=self.instance.status_id)
        )
        self.fields["status"].required = False
