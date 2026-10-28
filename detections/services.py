import csv
import io

from django.db import transaction
from django.utils import timezone

from clients.models import Client
from taxonomy.choices import StatusCategory, StatusScope
from taxonomy.models import Severity, Status, Technology

from .models import Rule

# --- "Detecção possivelmente inoperante" checks (query-time, no workers) ---


def rule_is_review_overdue(rule):
    return bool(rule.next_review_at and rule.next_review_at < timezone.localdate())


def rule_is_possibly_inoperative(rule):
    """
    Rule is ACTIVE but the client's reception of its log source is known to
    be broken (or the source was never integrated for that client at all).
    A log source that simply hasn't been classified yet (status=None, or no
    link registered where the catalog item still might be forthcoming)
    does NOT trigger this - only a known-bad state does.
    """
    from catalog.models import ClientLogSource

    if not rule.status or rule.status.category != StatusCategory.ACTIVE:
        return False
    if not rule.log_source_id:
        return False

    link = (
        ClientLogSource.objects.filter(client_id=rule.client_id, log_source_id=rule.log_source_id)
        .select_related("status")
        .first()
    )
    if link is None:
        return True
    if link.status is None:
        return False
    return link.status.category in (StatusCategory.NOT_RECEIVING, StatusCategory.NOT_INTEGRATED)


def use_case_coverage_inconsistencies(client):
    """
    ClientUseCase rows marked COVERED for this client that have no ACTIVE
    Rule actually backing them up - "INCONSISTÊNCIA DE COBERTURA".
    """
    from catalog.models import ClientUseCase

    inconsistent = []
    links = ClientUseCase.objects.filter(client=client).select_related("status", "use_case")
    for link in links:
        if not link.status or link.status.category != StatusCategory.COVERED:
            continue
        has_active_rule = Rule.objects.filter(
            client=client, use_cases=link.use_case, status__category=StatusCategory.ACTIVE
        ).exists()
        if not has_active_rule:
            inconsistent.append(link)
    return inconsistent


# --- CSV import ---

REQUIRED_CSV_COLUMNS = {"rule_id", "name", "client", "technology"}

#: Each row does several individual lookups (client, technology, log
#: source, severity, status) - uncapped, a single upload could tie up a
#: worker for minutes and, with a couple of concurrent uploads, exhaust
#: every Gunicorn worker. Split larger exports instead of raising this.
MAX_CSV_ROWS = 5000


def import_rules_from_csv(file_obj):
    """
    Expects a UTF-8 CSV with at least: rule_id, name, client, technology.
    Optional columns: log_source, level, severity, status, description.

    Matches existing rules by rule_id (-> internal_id): creates new ones,
    updates existing ones. Each row runs in its own transaction, so one bad
    row is reported and skipped instead of aborting the whole file.
    """
    decoded = io.TextIOWrapper(file_obj, encoding="utf-8-sig")
    reader = csv.DictReader(decoded)

    report = {"created": 0, "updated": 0, "errors": [], "warnings": []}

    if reader.fieldnames is None or not REQUIRED_CSV_COLUMNS.issubset(set(reader.fieldnames)):
        report["errors"].append(
            {
                "row": 0,
                "message": f"Cabeçalho inválido. Colunas obrigatórias: {', '.join(sorted(REQUIRED_CSV_COLUMNS))}.",
            }
        )
        return report

    for index, row in enumerate(reader, start=2):  # row 1 is the header
        if index - 1 > MAX_CSV_ROWS:
            report["errors"].append({
                "row": index,
                "message": f"Arquivo tem mais de {MAX_CSV_ROWS} linhas; interrompido aqui. "
                            "Divida o arquivo em partes menores e importe cada uma.",
            })
            break
        try:
            with transaction.atomic():
                _import_row(row, index, report)
        except Exception as exc:
            report["errors"].append({"row": index, "message": str(exc)})

    return report


def _import_row(row, index, report):
    from catalog.models import LogSource

    internal_id = (row.get("rule_id") or "").strip()
    name = (row.get("name") or "").strip()
    client_name = (row.get("client") or "").strip()
    technology_name = (row.get("technology") or "").strip()

    if not internal_id or not name or not client_name or not technology_name:
        raise ValueError("rule_id, name, client e technology são obrigatórios.")

    client = Client.objects.filter(name__iexact=client_name).first()
    if client is None:
        raise ValueError(f'Cliente "{client_name}" não encontrado.')

    technology = Technology.objects.filter(name__iexact=technology_name).first()
    if technology is None:
        raise ValueError(f'Tecnologia "{technology_name}" não encontrada.')

    log_source = None
    log_source_name = (row.get("log_source") or "").strip()
    if log_source_name:
        log_source = LogSource.objects.filter(name__iexact=log_source_name).first()
        if log_source is None:
            report["warnings"].append(
                {"row": index, "message": f'Fonte de log "{log_source_name}" não encontrada; ficou em branco.'}
            )

    severity = None
    severity_name = (row.get("severity") or "").strip()
    if severity_name:
        severity = Severity.objects.filter(name__iexact=severity_name).first()
        if severity is None:
            report["warnings"].append(
                {"row": index, "message": f'Severidade "{severity_name}" não encontrada; ficou em branco.'}
            )

    status = None
    status_name = (row.get("status") or "").strip()
    if status_name:
        status = Status.objects.filter(name__iexact=status_name, scope__contains=[StatusScope.RULE]).first()
        if status is None:
            report["warnings"].append(
                {"row": index, "message": f'Status "{status_name}" não encontrado para o escopo Regra; ficou em branco.'}
            )

    defaults = {
        "name": name,
        "client": client,
        "technology": technology,
        "log_source": log_source,
        "original_level": (row.get("level") or "").strip(),
        "severity": severity,
        "status": status,
        "description": (row.get("description") or "").strip(),
    }

    _, created = Rule.objects.update_or_create(internal_id=internal_id, defaults=defaults)
    report["created" if created else "updated"] += 1
