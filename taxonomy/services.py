from django.utils import timezone


def build_navigator_layer(framework, client=None, technology=None):
    """
    Builds a MITRE ATT&CK Navigator layer (layer format v4.5) from this
    Framework's controls: one techniqueID per control.code, scored by how
    many Rules reference it - exactly the count the Cyber Kill Chain widget
    on the Dashboard already shows per stage (dashboard/services.py), just
    reused here for any Framework whose control codes are ATT&CK technique
    IDs. Controls with zero linked rules are left out, so the heatmap only
    highlights what is actually covered.
    """
    controls = framework.controls.filter(is_active=True).order_by("code")

    techniques = []
    for control in controls:
        rule_qs = control.rules.all()
        if client:
            rule_qs = rule_qs.filter(client=client)
        if technology:
            rule_qs = rule_qs.filter(technology=technology)
        count = rule_qs.count()
        if count:
            techniques.append(
                {
                    "techniqueID": control.code,
                    "score": count,
                    "comment": f"{count} regra(s) de detecção vinculada(s).",
                }
            )

    scope_bits = [part.name for part in (client, technology) if part]
    scope = f" ({', '.join(scope_bits)})" if scope_bits else ""
    max_score = max((t["score"] for t in techniques), default=1)

    return {
        "name": f"SOC Control - {framework.name}{scope}",
        "versions": {"attack": "15", "navigator": "4.9.1", "layer": "4.5"},
        "domain": "enterprise-attack",
        "description": (
            f"Cobertura de regras de detecção gerada pelo SOC Control em "
            f"{timezone.localdate().strftime('%d/%m/%Y')}."
        ),
        "techniques": techniques,
        "gradient": {"colors": ["#ffffff", "#66b1ff", "#0d47a1"], "minValue": 0, "maxValue": max_score},
        "legendItems": [],
        "metadata": [],
        "showTacticRowBackground": False,
        "tacticRowBackground": "#dddddd",
        "selectTechniquesAcrossTactics": True,
        "selectSubtechniquesWithParent": False,
    }
