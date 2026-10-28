from taxonomy.choices import StatusCategory

from .models import ClientLogSource, ClientUseCase


def apply_template_to_client(template, client):
    """
    Creates ClientLogSource/ClientUseCase rows for everything in the
    template that the client doesn't already have. Idempotent: running it
    twice for the same client never duplicates existing associations.
    """
    created = {"log_sources": 0, "use_cases": 0}

    for item in template.log_sources.select_related("log_source"):
        _, was_created = ClientLogSource.objects.get_or_create(
            client=client, log_source=item.log_source
        )
        if was_created:
            created["log_sources"] += 1

    for item in template.use_cases.select_related("use_case", "default_criticality"):
        _, was_created = ClientUseCase.objects.get_or_create(
            client=client,
            use_case=item.use_case,
            defaults={"criticality": item.default_criticality},
        )
        if was_created:
            created["use_cases"] += 1

    return created


def compute_use_case_coverage(client):
    """
    "X% of applicable use cases are classified as covered."

    Use cases marked NOT_APPLICABLE never enter the denominator - the
    metric only ever claims what it can explain. Links with no status set
    yet are treated as not applicable to the ratio (status is required
    before a use case counts one way or the other).
    """
    links = ClientUseCase.objects.filter(client=client).select_related("status")
    applicable = [
        link for link in links
        if link.status and link.status.category != StatusCategory.NOT_APPLICABLE
    ]
    covered = [link for link in applicable if link.status.category == StatusCategory.COVERED]

    total_applicable = len(applicable)
    total_covered = len(covered)
    percentage = round((total_covered / total_applicable) * 100) if total_applicable else None

    return {"covered": total_covered, "applicable": total_applicable, "percentage": percentage}
