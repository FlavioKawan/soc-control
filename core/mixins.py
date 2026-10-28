from django.contrib import messages
from django.db.models import ProtectedError
from django.shortcuts import redirect


class ProtectedDeleteMixin:
    """
    Add to any DeleteView whose model is the target of an on_delete=PROTECT
    foreign key (e.g. Status, Severity, Technology, LogSource, UseCase).
    Without this, deleting a row still referenced elsewhere raises an
    unhandled ProtectedError - a 500 - instead of telling the user why the
    delete was refused.
    """

    def form_valid(self, form):
        try:
            return super().form_valid(form)
        except ProtectedError as exc:
            protected = list(exc.protected_objects)
            names = ", ".join(str(obj) for obj in protected[:10])
            if len(protected) > 10:
                names += f" e mais {len(protected) - 10}"
            messages.error(
                self.request,
                f'Não é possível excluir "{self.object}": ainda está em uso por: {names}.',
            )
            return redirect(self.request.path)
