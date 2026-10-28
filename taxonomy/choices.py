"""
Fixed, structural enums used internally by business logic.

These are NOT business data - they never change without a code deploy,
because the application's own rules (coverage calculation, inoperative
detection checks, permission scoping) depend on them. The *visual* labels
seen by users (Status.name, Category.name, ...) remain fully configurable
in the database; these enums only back a small internal "category"/"scope"
field so that logic never has to compare against a human-edited string.
"""

from django.db import models


class StatusScope(models.TextChoices):
    """Which operational entity a given Status row can be applied to."""

    CLIENT = "CLIENT", "Cliente"
    RULE = "RULE", "Regra"
    CLIENT_USE_CASE = "CLIENT_USE_CASE", "Caso de Uso (por cliente)"
    CLIENT_LOG_SOURCE = "CLIENT_LOG_SOURCE", "Fonte de Log (por cliente)"
    GAP = "GAP", "Gap"


class StatusCategory(models.TextChoices):
    """Internal semantics a Status row carries, grouped by the scope it fits."""

    # generic lifecycle - Client, Rule
    ACTIVE = "ACTIVE", "Ativo"
    INACTIVE = "INACTIVE", "Inativo"
    TESTING = "TESTING", "Em teste"
    IN_REVIEW = "IN_REVIEW", "Em revisão"
    PENDING_EXTERNAL = "PENDING_EXTERNAL", "Aguardando terceiro"

    # ClientUseCase coverage
    COVERED = "COVERED", "Coberto"
    PARTIAL = "PARTIAL", "Parcial"
    NOT_COVERED = "NOT_COVERED", "Não coberto"
    NOT_APPLICABLE = "NOT_APPLICABLE", "Não aplicável"

    # ClientLogSource
    RECEIVING = "RECEIVING", "Recebendo"
    NOT_RECEIVING = "NOT_RECEIVING", "Sem log"
    NOT_INTEGRATED = "NOT_INTEGRATED", "Não integrado"

    # Gap
    OPEN = "OPEN", "Aberto"
    CLOSED = "CLOSED", "Concluído"

    # fallback - no special meaning attached by business logic
    GENERIC = "GENERIC", "Sem semântica especial"


class CategoryScope(models.TextChoices):
    """Which catalog a given Category row can be attached to."""

    TECHNOLOGY = "TECHNOLOGY", "Tecnologia"
    USE_CASE = "USE_CASE", "Caso de Uso"
    RULE = "RULE", "Regra"
    LOG_SOURCE = "LOG_SOURCE", "Fonte de Log"
