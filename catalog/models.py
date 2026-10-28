from django.conf import settings
from django.db import models

from clients.models import Client
from taxonomy.choices import CategoryScope
from taxonomy.models import Category, FrameworkControl, Severity, Status, Tag, Technology


class LogSource(models.Model):
    """
    Global catalog entry (e.g. "Windows Security", "Sysmon", "Microsoft
    365"). Exists once; each client's actual reception status lives in
    ClientLogSource.
    """

    name = models.CharField(max_length=150, unique=True)
    description = models.TextField(blank=True)
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        limit_choices_to={"applicable_to__contains": [CategoryScope.LOG_SOURCE]},
        related_name="log_sources",
    )
    technology = models.ForeignKey(
        Technology, on_delete=models.SET_NULL, null=True, blank=True, related_name="log_sources"
    )
    tags = models.ManyToManyField(Tag, blank=True, related_name="log_sources")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Fonte de Log"
        verbose_name_plural = "Fontes de Log"
        ordering = ["name"]

    def __str__(self):
        return self.name


class ClientLogSource(models.Model):
    """A client's actual implementation of a catalog LogSource."""

    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="log_sources")
    log_source = models.ForeignKey(LogSource, on_delete=models.PROTECT, related_name="client_links")
    status = models.ForeignKey(
        Status,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="client_log_sources",
    )
    last_event_at = models.DateTimeField("Último evento", null=True, blank=True)
    notes = models.TextField("Observações", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Fonte de Log (cliente)"
        verbose_name_plural = "Fontes de Log (cliente)"
        unique_together = [("client", "log_source")]
        ordering = ["log_source__name"]

    def __str__(self):
        return f"{self.client} - {self.log_source}"


class UseCase(models.Model):
    """
    Global catalog entry (e.g. "UC-001 Brute Force"). Exists once; each
    client's actual coverage status lives in ClientUseCase.
    """

    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    objective = models.TextField(blank=True)
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        limit_choices_to={"applicable_to__contains": [CategoryScope.USE_CASE]},
        related_name="use_cases",
    )
    threat = models.CharField("Ameaça relacionada", max_length=255, blank=True)
    protects = models.TextField("O que protege", blank=True)
    tags = models.ManyToManyField(Tag, blank=True, related_name="use_cases")
    framework_controls = models.ManyToManyField(
        FrameworkControl, blank=True, related_name="use_cases", verbose_name="Técnicas/Controles"
    )
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Caso de Uso"
        verbose_name_plural = "Casos de Uso"
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} - {self.name}"


class ClientUseCase(models.Model):
    """A client's actual coverage of a catalog UseCase."""

    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="use_cases")
    use_case = models.ForeignKey(UseCase, on_delete=models.PROTECT, related_name="client_links")
    status = models.ForeignKey(
        Status, on_delete=models.PROTECT, null=True, blank=True, related_name="client_use_cases"
    )
    criticality = models.ForeignKey(
        Severity, on_delete=models.SET_NULL, null=True, blank=True, related_name="client_use_cases"
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="owned_use_cases",
        verbose_name="Responsável",
    )
    last_validated_at = models.DateField("Última validação", null=True, blank=True)
    notes = models.TextField("Observações", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Caso de Uso (cliente)"
        verbose_name_plural = "Casos de Uso (cliente)"
        unique_together = [("client", "use_case")]
        ordering = ["use_case__code"]

    def __str__(self):
        return f"{self.client} - {self.use_case}"


class ImplementationTemplate(models.Model):
    """
    A reusable bundle of log sources + use cases (e.g. "Windows Server")
    that can be applied to a client in one action, creating the
    corresponding ClientLogSource/ClientUseCase rows.
    """

    name = models.CharField(max_length=150, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Template de Implementação"
        verbose_name_plural = "Templates de Implementação"
        ordering = ["name"]

    def __str__(self):
        return self.name


class TemplateLogSource(models.Model):
    template = models.ForeignKey(ImplementationTemplate, on_delete=models.CASCADE, related_name="log_sources")
    log_source = models.ForeignKey(LogSource, on_delete=models.CASCADE, related_name="template_links")

    class Meta:
        unique_together = [("template", "log_source")]
        ordering = ["log_source__name"]

    def __str__(self):
        return f"{self.template} - {self.log_source}"


class TemplateUseCase(models.Model):
    template = models.ForeignKey(ImplementationTemplate, on_delete=models.CASCADE, related_name="use_cases")
    use_case = models.ForeignKey(UseCase, on_delete=models.CASCADE, related_name="template_links")
    default_criticality = models.ForeignKey(Severity, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        unique_together = [("template", "use_case")]
        ordering = ["use_case__code"]

    def __str__(self):
        return f"{self.template} - {self.use_case}"
