from django.conf import settings
from django.db import models

from taxonomy.models import Status


class Client(models.Model):
    name = models.CharField(max_length=200)
    legal_name = models.CharField("Razão social", max_length=200, blank=True)
    status = models.ForeignKey(
        Status,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="clients",
        verbose_name="Status",
    )
    notes = models.TextField("Observações", blank=True)
    # ADMIN/SOC_MANAGER always see every client (clients.services.visible_clients);
    # this only scopes ANALYST/VIEWER, who see nothing until assigned here.
    assigned_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name="assigned_clients",
        verbose_name="Analistas com acesso",
        help_text="Só vale para usuários ANALYST/VIEWER - ADMIN e SOC_MANAGER já veem todos os clientes.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"
        ordering = ["name"]

    def __str__(self):
        return self.name
