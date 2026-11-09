from collections import defaultdict

from django.db.models import Count
from django.urls import reverse
from django.utils import timezone

from catalog.models import ClientLogSource, ClientUseCase
from clients.models import Client
from detections.models import Rule
from gaps.models import Gap
from taxonomy.choices import StatusCategory
from taxonomy.models import Framework
from taxonomy.services import framework_layers

#: How many clients the "melhor cobertura" ranking shows.
CLIENT_RANKING_SIZE = 5

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


def build_dashboard(client=None, technology=None, allowed_clients=None):
    """
    allowed_clients, when not None, restricts every aggregate below to a
    restricted ANALYST/VIEWER's own assigned clients
    (clients.services.visible_clients) - None means "no restriction"
    (ADMIN/SOC_MANAGER).
    """
    rule_qs = Rule.objects.all()
    cuc_qs = ClientUseCase.objects.all()
    gap_qs = Gap.objects.all()
    cls_qs = ClientLogSource.objects.all()

    if allowed_clients is not None:
        rule_qs = rule_qs.filter(client__in=allowed_clients)
        cuc_qs = cuc_qs.filter(client__in=allowed_clients)
        gap_qs = gap_qs.filter(client__in=allowed_clients)
        cls_qs = cls_qs.filter(client__in=allowed_clients)
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
                    "control_ids": layer["control_ids"],
                }
                for layer in framework_layers(framework)
            ]
        layer_widgets.append({"key": key, "name": framework_name, "seed_hint": seed_hint, "layers": layers})

    # Comparing a client against itself (ranking) or showing "our" combined
    # score while already looking at one client's own layer tabs (maturity)
    # is redundant - both only make sense in the "all clients" view.
    layer_maturity = None
    client_ranking = None
    if client is None:
        layer_maturity = _combined_layer_maturity(layer_widgets)
        client_ranking = _client_layer_ranking(layer_widgets, technology, allowed_clients)

    return {
        "cards": cards,
        "charts": charts,
        "layer_widgets": layer_widgets,
        "layer_maturity": layer_maturity,
        "client_ranking": client_ranking,
    }


def _combined_layer_maturity(layer_widgets):
    """One number for "how exposed are we": the share of layers (Kill
    Chain stages + MITRE ATT&CK tactics combined) with at least one rule
    behind them, for the dashboard's current filters."""
    total = sum(len(widget["layers"]) for widget in layer_widgets if widget["layers"])
    if not total:
        return None
    covered = sum(
        1 for widget in layer_widgets if widget["layers"] for layer in widget["layers"] if layer["count"]
    )
    return {"covered": covered, "total": total, "percentage": round(100 * covered / total)}


def _client_layer_ranking(layer_widgets, technology, allowed_clients=None, limit=CLIENT_RANKING_SIZE):
    """
    Top clients by the same combined layer coverage _combined_layer_maturity
    computes for "everyone" - answers "who are we protecting best/worst".
    One query for every (client, control) pair tagged under a tracked
    layer, instead of one query per client per layer. allowed_clients, when
    not None, ranks only among a restricted ANALYST/VIEWER's own clients.
    """
    layer_by_control = {}
    total_layers = 0
    for widget in layer_widgets:
        if not widget["layers"]:
            continue
        for layer in widget["layers"]:
            total_layers += 1
            for control_id in layer["control_ids"]:
                layer_by_control[control_id] = (widget["key"], layer["id"])
    if not total_layers:
        return None

    tagged_rules = Rule.objects.filter(framework_controls__id__in=layer_by_control)
    if technology:
        tagged_rules = tagged_rules.filter(technology=technology)
    if allowed_clients is not None:
        tagged_rules = tagged_rules.filter(client__in=allowed_clients)

    covered_layers_by_client = defaultdict(set)
    for client_id, control_id in tagged_rules.values_list("client_id", "framework_controls__id").distinct():
        covered_layers_by_client[client_id].add(layer_by_control[control_id])

    candidates_qs = Client.objects.all() if allowed_clients is None else allowed_clients
    ranking = [
        {
            "client": candidate,
            "covered": len(covered_layers_by_client.get(candidate.pk, ())),
            "total": total_layers,
            "percentage": round(100 * len(covered_layers_by_client.get(candidate.pk, ())) / total_layers),
        }
        for candidate in candidates_qs
    ]
    ranking.sort(key=lambda row: (-row["percentage"], row["client"].name))
    return ranking[:limit]
