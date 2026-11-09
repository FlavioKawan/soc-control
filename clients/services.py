#: Groups that bypass per-client assignment entirely and see every Client.
FULL_VISIBILITY_GROUPS = ("ADMIN", "SOC_MANAGER")


def has_full_client_visibility(user):
    """
    ADMIN, SOC_MANAGER and superusers see every client. ANALYST and VIEWER
    only see the clients explicitly assigned to them (Client.assigned_users)
    - the per-client isolation the internal pentest flagged as missing
    (docs/05-operacao-e-testes.md §8: "qualquer usuário autenticado com a
    permissão view_client vê todos os clientes").
    """
    return user.is_superuser or user.groups.filter(name__in=FULL_VISIBILITY_GROUPS).exists()


def visible_clients(user):
    """The Client queryset `user` is allowed to see - every app that scopes
    data by client (clients, catalog, detections, gaps, dashboard, search,
    reports, audit) filters through this instead of Client.objects.all()."""
    from .models import Client

    if has_full_client_visibility(user):
        return Client.objects.all()
    return Client.objects.filter(assigned_users=user)
