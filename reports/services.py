from collections import Counter

from django.db.models import Count, F, Q
from django.utils import timezone

from catalog.services import compute_use_case_coverage
from detections.services import rule_is_possibly_inoperative, rule_is_review_overdue
from taxonomy.choices import StatusCategory
from taxonomy.models import Framework

#: Frameworks this small (e.g. Cyber Kill Chain, 7 stages) are listed in
#: full, uncovered controls included. Larger ones (MITRE ATT&CK, hundreds of
#: techniques) only list what is covered - the full list would bury the point.
FRAMEWORK_FULL_LIST_MAX_CONTROLS = 30

_LOG_SOURCE_PROBLEM_CATEGORIES = (StatusCategory.NOT_RECEIVING, StatusCategory.NOT_INTEGRATED)


def build_client_report(client):
    """
    Everything the internal (SOC team) report needs for one Cliente: the
    same coverage/rules/gaps/log sources data already shown on the client
    detail page, just assembled once for the PDF/Excel renderers to consume
    without each having to know the model layer. The version sent to the
    client is build_client_facing_report().
    """
    rules = list(
        client.rules.select_related("technology", "severity", "status", "log_source").order_by("internal_id")
    )
    gaps = list(
        client.gaps.select_related("status", "criticality", "responsible_party").order_by("-opened_at")
    )
    use_case_links = list(
        client.use_cases.select_related("use_case", "status", "criticality", "owner").order_by("use_case__code")
    )
    log_source_links = list(
        client.log_sources.select_related("log_source", "status").order_by("log_source__name")
    )

    for rule in rules:
        rule.is_review_overdue = rule_is_review_overdue(rule)
        rule.is_possibly_inoperative = rule_is_possibly_inoperative(rule)

    active_rules_count = sum(
        1 for rule in rules if rule.status and rule.status.category == StatusCategory.ACTIVE
    )
    open_gaps_count = sum(
        1 for gap in gaps if not gap.status or gap.status.category != StatusCategory.CLOSED
    )

    return {
        "client": client,
        "generated_at": timezone.now(),
        "coverage": compute_use_case_coverage(client),
        "rules": rules,
        "gaps": gaps,
        "use_case_links": use_case_links,
        "log_source_links": log_source_links,
        "active_rules_count": active_rules_count,
        "open_gaps_count": open_gaps_count,
    }


def build_client_facing_report(client):
    """
    The version of the report meant to be handed to the client: executive
    summary, what depends on the client, use case and framework coverage.

    Deliberately leaves out everything internal to the SOC - rule internal/
    vendor IDs, notes, the SOC analyst owning each use case, inoperative/
    review flags - so it can be sent as-is. build_client_report() remains
    the internal, complete version.
    """
    active_rules = list(
        client.rules.filter(status__category=StatusCategory.ACTIVE)
        .select_related("severity", "log_source")
        .order_by("name")
    )
    open_gaps = list(
        client.gaps.exclude(status__category=StatusCategory.CLOSED)
        .select_related("status", "criticality", "responsible_party")
        .order_by(F("criticality__weight").desc(nulls_last=True), "opened_at")
    )
    use_case_links = list(
        client.use_cases.exclude(status__category=StatusCategory.NOT_APPLICABLE)
        .select_related("use_case", "status", "criticality")
        .order_by("use_case__code")
    )
    log_source_links = list(client.log_sources.select_related("log_source", "status").order_by("log_source__name"))

    active_rules_per_log_source = Counter(rule.log_source_id for rule in active_rules if rule.log_source_id)
    problem_log_sources = [
        link
        for link in log_source_links
        if link.status and link.status.category in _LOG_SOURCE_PROBLEM_CATEGORIES
    ]
    for link in problem_log_sources:
        link.affected_rules_count = active_rules_per_log_source[link.log_source_id]

    client_gaps, other_gaps = [], []
    for gap in open_gaps:
        is_clients = bool(gap.responsible_party and gap.responsible_party.is_client)
        (client_gaps if is_clients else other_gaps).append(gap)

    today = timezone.localdate()
    for gap in open_gaps:
        gap.days_open = (today - gap.opened_at).days if gap.opened_at else None

    receiving_count = sum(
        1 for link in log_source_links if link.status and link.status.category == StatusCategory.RECEIVING
    )

    return {
        "client": client,
        "generated_at": timezone.now(),
        "coverage": compute_use_case_coverage(client),
        "active_rules": active_rules,
        "open_gaps_by_criticality": _count_by_criticality(open_gaps),
        "open_gaps_count": len(open_gaps),
        "log_sources_total": len(log_source_links),
        "log_sources_receiving": receiving_count,
        "client_gaps": client_gaps,
        "other_gaps": other_gaps,
        "problem_log_sources": problem_log_sources,
        "use_case_links": use_case_links,
        "frameworks": _framework_coverage(client),
    }


def _count_by_criticality(gaps):
    counts = Counter(gap.criticality.name if gap.criticality else "Sem criticidade" for gap in gaps)
    return sorted(counts.items(), key=lambda item: -item[1])


def _framework_coverage(client):
    """
    Per active Framework: which controls have at least one ACTIVE rule of
    this client behind them. Only ACTIVE rules count - a rule in test or
    disabled does not protect the client yet.
    """
    result = []
    for framework in Framework.objects.filter(is_active=True).order_by("name"):
        controls = list(
            framework.controls.filter(is_active=True)
            .annotate(
                active_rules_count=Count(
                    "rules",
                    filter=Q(rules__client=client, rules__status__category=StatusCategory.ACTIVE),
                    distinct=True,
                )
            )
            .order_by("code")
        )
        if not controls:
            continue
        covered = [control for control in controls if control.active_rules_count]
        list_all = len(controls) <= FRAMEWORK_FULL_LIST_MAX_CONTROLS
        result.append(
            {
                "framework": framework,
                "total": len(controls),
                "covered_count": len(covered),
                "controls": controls if list_all else covered,
                "lists_all": list_all,
            }
        )
    return result
