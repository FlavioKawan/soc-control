from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from clients.models import Client
from clients.services import has_full_client_visibility, visible_clients
from core.utils import parse_int_or_none
from taxonomy.models import Technology

from .services import build_dashboard


@login_required
def dashboard(request):
    # None means "unrestricted" (ADMIN/SOC_MANAGER) - keeps the aggregate
    # queries below identical to before for them, instead of adding a
    # needless client__in=<all clients> filter.
    allowed_clients = None if has_full_client_visibility(request.user) else visible_clients(request.user)
    client_choices = allowed_clients if allowed_clients is not None else Client.objects.all()

    client = None
    technology = None
    client_id = parse_int_or_none(request.GET.get("client"))
    technology_id = parse_int_or_none(request.GET.get("technology"))
    if client_id:
        client = client_choices.filter(pk=client_id).first()
    if technology_id:
        technology = Technology.objects.filter(pk=technology_id).first()

    data = build_dashboard(client=client, technology=technology, allowed_clients=allowed_clients)

    context = {
        "clients": client_choices,
        "technologies": Technology.objects.all(),
        "selected_client": client,
        "selected_technology": technology,
        "is_new_setup": not client_choices.exists() or not data["cards"]["total_rules"],
        **data,
    }
    return render(request, "dashboard/dashboard.html", context)
