from django.db import models
from django.utils import timezone

from catalog.models import LogSource, UseCase
from clients.models import Client
from detections.models import Rule
from taxonomy.models import ResponsibleParty, Severity, Status, Tag


class Gap(models.Model):
    code = models.CharField("Código", max_length=20, unique=True)
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="gaps")
    title = models.CharField("Título", max_length=255)
    description = models.TextField("Descrição", blank=True)
    impact = models.TextField("Impacto", blank=True)
    criticality = models.ForeignKey(
        Severity, on_delete=models.SET_NULL, null=True, blank=True, related_name="gaps"
    )
    responsible_party = models.ForeignKey(
        ResponsibleParty, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="gaps", verbose_name="Responsável",
    )
    status = models.ForeignKey(
        Status, on_delete=models.PROTECT, null=True, blank=True, related_name="gaps"
    )
    recommendation = models.TextField("Recomendação", blank=True)
    opened_at = models.DateField("Data de abertura", default=timezone.localdate)
    closed_at = models.DateField("Data de conclusão", null=True, blank=True)
    notes = models.TextField("Observações", blank=True)

    # optional relationships
    log_source = models.ForeignKey(
        LogSource, on_delete=models.SET_NULL, null=True, blank=True, related_name="gaps"
    )
    use_case = models.ForeignKey(
        UseCase, on_delete=models.SET_NULL, null=True, blank=True, related_name="gaps"
    )
    rule = models.ForeignKey(
        Rule, on_delete=models.SET_NULL, null=True, blank=True, related_name="gaps"
    )
    tags = models.ManyToManyField(Tag, blank=True, related_name="gaps")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Gap"
        verbose_name_plural = "Gaps"
        ordering = ["-opened_at", "code"]

    def __str__(self):
        return f"{self.code} - {self.title}"
