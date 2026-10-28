from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.utils.text import slugify

from .choices import CategoryScope, StatusCategory, StatusScope


class ConfigurableOption(models.Model):
    """
    Shared shape for every admin-managed catalog in the system (Technology,
    Status, Severity, Category, Tag, RuleType, ...).

    The table structure is fixed by this class; the *rows* are entirely
    managed by administrators through the "Configurações" area or the
    Django Admin - new technologies, statuses, categories, etc. never
    require a code change or a migration.
    """

    name = models.CharField(max_length=100)
    code = models.SlugField(max_length=60, unique=True, blank=True)
    description = models.TextField(blank=True)
    color = models.CharField(max_length=7, blank=True, help_text="Cor em hexadecimal, ex: #0d6efd")
    icon = models.CharField(max_length=50, blank=True, help_text="Nome do ícone (opcional)")
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ["order", "name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = slugify(self.name)[:60]
        super().save(*args, **kwargs)


class Technology(ConfigurableOption):
    category = models.ForeignKey(
        "taxonomy.Category",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        limit_choices_to={"applicable_to__contains": [CategoryScope.TECHNOLOGY]},
        related_name="technologies",
    )

    class Meta(ConfigurableOption.Meta):
        verbose_name = "Tecnologia"
        verbose_name_plural = "Tecnologias"


class Status(ConfigurableOption):
    scope = ArrayField(
        models.CharField(max_length=30, choices=StatusScope.choices),
        default=list,
        blank=True,
        help_text="Em quais entidades este status pode ser usado.",
    )
    category = models.CharField(
        max_length=30,
        choices=StatusCategory.choices,
        default=StatusCategory.GENERIC,
        help_text="Semântica interna usada pelas regras de negócio (nunca pelo texto do status).",
    )

    class Meta(ConfigurableOption.Meta):
        verbose_name = "Status"
        verbose_name_plural = "Status"


class Severity(ConfigurableOption):
    weight = models.PositiveIntegerField(default=0, help_text="Usado em ordenações e indicadores.")

    class Meta(ConfigurableOption.Meta):
        verbose_name = "Severidade"
        verbose_name_plural = "Severidades"


class Category(ConfigurableOption):
    applicable_to = ArrayField(
        models.CharField(max_length=30, choices=CategoryScope.choices),
        default=list,
        blank=True,
        help_text="Em quais catálogos esta categoria pode ser usada.",
    )

    class Meta(ConfigurableOption.Meta):
        verbose_name = "Categoria"
        verbose_name_plural = "Categorias"


class Tag(ConfigurableOption):
    class Meta(ConfigurableOption.Meta):
        verbose_name = "Tag"
        verbose_name_plural = "Tags"


class ResponsibleParty(ConfigurableOption):
    """Who owns closing a Gap - e.g. SOC, Cliente, Fornecedor. Configurable
    because this varies by SOC operation, not a fixed set of roles."""

    # Same idea as Status.category: the client-facing report needs to know
    # which gaps are the client's to act on, and must never infer that from
    # the human-edited name.
    is_client = models.BooleanField(
        "Responsabilidade do cliente",
        default=False,
        help_text="Marque se este responsável representa o próprio cliente. Gaps com ele aparecem "
                  "como \"ações pendentes\" no relatório enviado ao cliente.",
    )

    class Meta(ConfigurableOption.Meta):
        verbose_name = "Responsável"
        verbose_name_plural = "Responsáveis"


class RuleType(ConfigurableOption):
    class Meta(ConfigurableOption.Meta):
        verbose_name = "Tipo de Regra"
        verbose_name_plural = "Tipos de Regra"


class Framework(models.Model):
    name = models.CharField(max_length=150, unique=True)
    version = models.CharField(max_length=50, blank=True)
    description = models.TextField(blank=True)
    url = models.URLField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Framework"
        verbose_name_plural = "Frameworks"
        ordering = ["name"]

    def __str__(self):
        return self.name


class FrameworkControl(models.Model):
    """A control/technique within a Framework (e.g. MITRE ATT&CK T1110)."""

    framework = models.ForeignKey(Framework, on_delete=models.CASCADE, related_name="controls")
    code = models.CharField(max_length=50)
    name = models.CharField(max_length=255)
    parent = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True, related_name="children"
    )
    description = models.TextField(blank=True)
    url = models.URLField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Controle/Técnica"
        verbose_name_plural = "Controles/Técnicas"
        unique_together = [("framework", "code")]
        ordering = ["framework", "code"]

    def __str__(self):
        return f"{self.code} - {self.name}"
