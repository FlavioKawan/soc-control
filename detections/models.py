from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.db import models

from catalog.models import LogSource, UseCase
from clients.models import Client
from taxonomy.choices import CategoryScope
from taxonomy.models import Category, FrameworkControl, RuleType, Severity, Status, Tag, Technology

#: Columns the "Configurar colunas" picker offers, in display order.
#: Key must match a branch in detections/templates/detections/_rule_columns.html.
AVAILABLE_RULE_COLUMNS = [
    ("internal_id", "ID"),
    ("name", "Nome"),
    ("client", "Cliente"),
    ("technology", "Tecnologia"),
    ("severity", "Severidade"),
    ("status", "Status"),
    ("log_source", "Fonte"),
    ("rule_type", "Tipo"),
    ("vendor_rule_id", "ID na ferramenta"),
    ("mitre", "MITRE"),
    ("last_reviewed_at", "Última revisão"),
    ("next_review_at", "Próxima revisão"),
]
DEFAULT_RULE_COLUMNS = ["internal_id", "name", "client", "technology", "severity", "status"]


class Rule(models.Model):
    internal_id = models.CharField("Identificador interno", max_length=50, unique=True)
    vendor_rule_id = models.CharField("ID na tecnologia", max_length=150, blank=True)
    name = models.CharField("Nome", max_length=255)
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="rules")
    technology = models.ForeignKey(Technology, on_delete=models.PROTECT, related_name="rules")
    rule_type = models.ForeignKey(
        RuleType, on_delete=models.SET_NULL, null=True, blank=True, related_name="rules"
    )
    description = models.TextField(blank=True)
    objective = models.TextField(blank=True)
    log_source = models.ForeignKey(
        LogSource, on_delete=models.PROTECT, null=True, blank=True, related_name="rules"
    )
    original_level = models.CharField(
        "Nível original da ferramenta", max_length=50, blank=True,
        help_text="Rótulo de severidade nativo da ferramenta (ex: High, 7, Critical).",
    )
    severity = models.ForeignKey(
        Severity, on_delete=models.PROTECT, null=True, blank=True, related_name="rules",
        verbose_name="Severidade SOC",
    )
    status = models.ForeignKey(
        Status, on_delete=models.PROTECT, null=True, blank=True, related_name="rules"
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        limit_choices_to={"applicable_to__contains": [CategoryScope.RULE]},
        related_name="rules",
    )
    protects = models.TextField("O que protege", blank=True)
    threat = models.CharField("Ameaça", max_length=255, blank=True)
    use_cases = models.ManyToManyField(UseCase, blank=True, related_name="rules", verbose_name="Casos de uso")
    framework_controls = models.ManyToManyField(
        FrameworkControl, blank=True, related_name="rules", verbose_name="Técnicas/Controles"
    )
    tags = models.ManyToManyField(Tag, blank=True, related_name="rules")
    last_reviewed_at = models.DateField("Última revisão", null=True, blank=True)
    next_review_at = models.DateField("Próxima revisão", null=True, blank=True)
    notes = models.TextField("Observações", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Regra"
        verbose_name_plural = "Regras"
        ordering = ["internal_id"]
        indexes = [
            models.Index(fields=["client", "status"]),
            models.Index(fields=["next_review_at"]),
        ]

    def __str__(self):
        return f"{self.internal_id} - {self.name}"


class RuleColumnPreference(models.Model):
    """Per-user persisted choice of which Rule list columns to display."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="rule_column_preference"
    )
    visible_columns = ArrayField(models.CharField(max_length=30), default=list, blank=True)

    def __str__(self):
        return f"Preferência de colunas - {self.user}"
