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
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"
        ordering = ["name"]

    def __str__(self):
        return self.name
