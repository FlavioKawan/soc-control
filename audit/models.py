from django.conf import settings
from django.db import models


class AuditLog(models.Model):
    """
    One entry per create/update/delete on a tracked model (see
    audit/signals.py::TRACKED_MODELS). Fase 9 do roteiro - deliberately
    scoped to the entities a SOC governance review cares about most
    (Cliente, Regra, Gap), not every model in the system.
    """

    class Action(models.TextChoices):
        CREATE = "CREATE", "Criado"
        UPDATE = "UPDATE", "Atualizado"
        DELETE = "DELETE", "Excluído"

    timestamp = models.DateTimeField("Data/hora", auto_now_add=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
        verbose_name="Usuário",
    )
    action = models.CharField("Ação", max_length=10, choices=Action.choices)
    app_label = models.CharField(max_length=100)
    model_name = models.CharField(max_length=100)
    object_id = models.CharField(max_length=255)
    object_repr = models.CharField("Objeto", max_length=255)
    # Denormalized on purpose: lets the client's "Histórico" tab show entries
    # for rules/gaps that belonged to it even after they're deleted (their FK
    # to Client is gone by then) or if the client itself was renamed since.
    client = models.ForeignKey(
        "clients.Client",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
        verbose_name="Cliente",
    )
    changes = models.JSONField("Alterações", default=dict, blank=True)

    class Meta:
        verbose_name = "Registro de auditoria"
        verbose_name_plural = "Registros de auditoria"
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["app_label", "model_name", "object_id"]),
            models.Index(fields=["client"]),
        ]

    def __str__(self):
        return f"{self.get_action_display()} - {self.model_name} #{self.object_id}"

    @property
    def model_label(self):
        return f"{self.app_label}.{self.model_name}"
