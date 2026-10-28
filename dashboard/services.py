from django.db.models import Count
from django.urls import reverse
from django.utils import timezone

from catalog.models import ClientLogSource, ClientUseCase
from detections.models import Rule
from gaps.models import Gap
from taxonomy.choices import StatusCategory
from taxonomy.models import Framework
from taxonomy.services import framework_layers

#: key -> (Framework name, hint shown when it hasn't been seeded/created yet).
#: Both are "fixed" widgets the Dashboard always offers a tab for (see
#: taxonomy/services.py::LAYER_FRAMEWORK_NAMES) - MITRE ATT&CK's tactics
#: come from seed_mitre_attack, techniques are added by hand under them.
LAYER_WIDGETS = [
    ("kill_chain", "Cyber Kill Chain", "python manage.py seed_kill_chain"),
    ("mitre_attack", "MITRE ATT&CK", "python manage.py seed_mitre_attack"),
]

FALLBACK_PALETTE = [
    "#4f46e5", "#0ea5e9", "#14b8a6", "#f59e0b", "#ef4444",
    "#8b5cf6", "#ec4899", "#22c55e", "#64748b", "#eab308",
]


def _grouped(queryset, name_field, color_field=None, palette=False):
    """[{label, value, color}] from a GROUP BY, largest first."""
    rows = list(
        queryset.values(name_field, *([color_field] if color_field else []))
        .annotate(value=Count("id"))
        .order_by("-value")
    )
    result = []
    for i, row in enumerate(rows):
        label = row[name_field] or "Sem classificação"
        color = row.get(color_field) if color_field else None
        if not color:
            color = FALLBACK_PALETTE[i % len(FALLBACK_PALETTE)] if palette else "#94a3b8"
        result.append({"label": label, "value": row["value"], "color": color})
    return result


def build_dashboard(client=None, technology=None):
    rule_qs = Rule.objects.all()
    cuc_qs = ClientUseCase.objects.all()
    gap_qs = Gap.objects.all()
    cls_qs = ClientLogSource.objects.all()

    if client:
        rule_qs = rule_qs.filter(client=client)
        cuc_qs = cuc_qs.filter(client=client)
        gap_qs = gap_qs.filter(client=client)
        cls_qs = cls_qs.filter(client=client)
    if technology:
        rule_qs = rule_qs.filter(technology=technology)

    today = timezone.localdate()

    cards = {
        "total_rules": rule_qs.count(),
        "active_rules": rule_qs.filter(status__category=StatusCategory.ACTIVE).count(),
        "testing_rules": rule_qs.filter(status__category=StatusCategory.TESTING).count(),
        "review_rules": rule_qs.filter(status__category=StatusCategory.IN_REVIEW).count(),
        "inactive_rules": rule_qs.filter(status__category=StatusCategory.INACTIVE).count(),
        "reviews_pending": rule_qs.filter(next_review_at__lt=today).count(),
        "total_use_cases": cuc_qs.count(),
        "covered_use_cases": cuc_qs.filter(status__category=StatusCategory.COVERED).count(),
        "partial_use_cases": cuc_qs.filter(status__category=StatusCategory.PARTIAL).count(),
        "not_covered_use_cases": cuc_qs.filter(status__category=StatusCategory.NOT_COVERED).count(),
        "gaps_total": gap_qs.count(),
        "gaps_open": gap_qs.exclude(status__category=StatusCategory.CLOSED).count(),
        "log_sources_without_data": cls_qs.filter(
            status__category__in=[StatusCategory.NOT_RECEIVING, StatusCategory.NOT_INTEGRATED]
        ).count(),
    }

    charts = {
        "rules_by_status": _grouped(rule_qs, "status__name", "status__color"),
        "rules_by_technology": _grouped(rule_qs, "technology__name", palette=True),
        "rules_by_severity": _grouped(rule_qs, "severity__name", "severity__color"),
        "usecases_by_category": _grouped(cuc_qs, "use_case__category__name", palette=True),
        "gaps_by_criticality": _grouped(gap_qs, "criticality__name", "criticality__color"),
        "top_threats": _grouped(rule_qs.exclude(threat=""), "threat", palette=True)[:8],
        "coverage": [
            {"label": "Coberto", "value": cards["covered_use_cases"], "color": "#22c55e"},
            {"label": "Parcial", "value": cards["partial_use_cases"], "color": "#f59e0b"},
            {"label": "Não coberto", "value": cards["not_covered_use_cases"], "color": "#ef4444"},
        ],
    }

    base_url = reverse("detections:rule_list")
    extra = []
    if client:
        extra.append(f"client={client.pk}")
    if technology:
        extra.append(f"technology={technology.pk}")
    suffix = ("&" + "&".join(extra)) if extra else ""

    layer_widgets = []
    for key, framework_name, seed_hint in LAYER_WIDGETS:
        framework = Framework.objects.filter(name=framework_name).first()
        layers = None
        if framework:
            layers = [
                {
                    "id": layer["control"].pk,
                    "code": layer["control"].code,
                    "name": layer["control"].name,
                    "description": layer["control"].description,
                    "count": rule_qs.filter(framework_controls__in=layer["control_ids"]).distinct().count(),
                    "url": f"{base_url}?stage={layer['control'].pk}{suffix}",
                }
                for layer in framework_layers(framework)
            ]
        layer_widgets.append({"key": key, "name": framework_name, "seed_hint": seed_hint, "layers": layers})

    return {"cards": cards, "charts": charts, "layer_widgets": layer_widgets}
