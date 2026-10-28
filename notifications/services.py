from datetime import timedelta

from django.utils import timezone

from detections.models import Rule
from gaps.models import Gap
from taxonomy.choices import StatusCategory

#: A Gap counts as "sem movimento" once it has gone this many days without
#: an update while still open. A plain constant, not a catalog: it is an
#: operational threshold for the digest job, not a business value that
#: varies per SOC operation the way Status/Severity/etc. do.
STALE_GAP_DAYS = 14


def overdue_rules():
    """Rules whose next_review_at has already passed."""
    today = timezone.localdate()
    return (
        Rule.objects.filter(next_review_at__lt=today)
        .select_related("client", "technology")
        .order_by("next_review_at")
    )


def stale_gaps(days=STALE_GAP_DAYS):
    """Open gaps that haven't been touched (no save()) in `days` days."""
    cutoff = timezone.now() - timedelta(days=days)
    return (
        Gap.objects.exclude(status__category=StatusCategory.CLOSED)
        .filter(updated_at__lt=cutoff)
        .select_related("client", "status")
        .order_by("updated_at")
    )


def build_digest(site_url):
    """
    Plain-text digest body combining both lists, or None if there's nothing
    to report - callers use that to skip sending an empty e-mail.
    """
    rules = list(overdue_rules())
    gaps = list(stale_gaps())
    if not rules and not gaps:
        return None

    lines = ["Pendências do SOC Control:", ""]

    if rules:
        lines.append(f"Regras com revisão vencida ({len(rules)}):")
        for rule in rules:
            lines.append(
                f"  - {rule.internal_id} - {rule.name} ({rule.client}) "
                f"- venceu em {rule.next_review_at:%d/%m/%Y}"
            )
        lines.append(f"  Ver lista: {site_url}/regras/?review_status=overdue")
        lines.append("")

    if gaps:
        lines.append(f"Gaps sem movimento há {STALE_GAP_DAYS}+ dias ({len(gaps)}):")
        for gap in gaps:
            lines.append(
                f"  - {gap.code} - {gap.title} ({gap.client}) "
                f"- última atualização em {gap.updated_at:%d/%m/%Y}"
            )
        lines.append(f"  Ver lista: {site_url}/gaps/")
        lines.append("")

    return "\n".join(lines)
