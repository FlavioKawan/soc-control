from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from clients.models import Client
from core.utils import parse_int_or_none
from taxonomy.models import Technology

from .services import build_dashboard


@login_required
def dashboard(request):
    client = None
    technology = None
    client_id = parse_int_or_none(request.GET.get("client"))
    technology_id = parse_int_or_none(request.GET.get("technology"))
    if client_id:
        client = Client.objects.filter(pk=client_id).first()
    if technology_id:
        technology = Technology.objects.filter(pk=technology_id).first()

    data = build_dashboard(client=client, technology=technology)

    context = {
        "clients": Client.objects.all(),
        "technologies": Technology.objects.all(),
        "selected_client": client,
        "selected_technology": technology,
        "is_new_setup": not Client.objects.exists() or not data["cards"]["total_rules"],
        **data,
    }
    return render(request, "dashboard/dashboard.html", context)
