from .services import visible_clients


class ClientScopedQuerysetMixin:
    """
    Restricts a ListView/DetailView/UpdateView/DeleteView's get_queryset()
    to the clients the logged-in user is allowed to see
    (clients.services.visible_clients). Since DetailView/UpdateView/
    DeleteView build get_object() from get_queryset(), this also turns an
    out-of-scope pk into a 404 for free, with no extra code per view.

    Set client_lookup="pk" when the view's model IS Client; leave the
    default "client" when it's the name of a client foreign key (Rule,
    Gap, AuditLog, ...).
    """

    client_lookup = "client"

    def get_queryset(self):
        qs = super().get_queryset()
        field = "pk" if self.client_lookup == "pk" else self.client_lookup
        return qs.filter(**{f"{field}__in": visible_clients(self.request.user)})
