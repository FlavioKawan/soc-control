from django.utils import timezone

#: The two Frameworks the Dashboard and the client-facing report always
#: offer a dedicated "layer" view for, picked by name. Both are seeded by
#: management commands (seed_kill_chain, seed_mitre_attack) as reference
#: content, not hardcoded business rules - any other Framework still works
#: everywhere else (Navigator export, framework-by-framework coverage on
#: the internal report), it just doesn't get this specific widget.
LAYER_FRAMEWORK_NAMES = ("Cyber Kill Chain", "MITRE ATT&CK")


def control_and_descendant_ids(control):
    """A control's id plus every active descendant's (e.g. a MITRE ATT&CK
    tactic's techniques and sub-techniques) - recursive, so it also copes
    with sub-techniques one level deeper than the tactic->technique a
    Framework like Kill Chain never has."""
    ids = [control.pk]
    for child in control.children.filter(is_active=True):
        ids.extend(control_and_descendant_ids(child))
    return ids


def framework_layers(framework):
    """
    Groups a Framework's controls into top-level "layers" - a Cyber Kill
    Chain stage, or a MITRE ATT&CK tactic - each with the ids of every
    descendant control folded in. Counting rules one technique at a time
    reads as a wall of codes; counting at this level reads as "which
    layers are we protecting", which is what the Dashboard widget and the
    client report need.

    Frameworks without hierarchy (Kill Chain: every control is already
    top-level) come back as one layer per control, same as iterating
    `framework.controls` directly.
    """
    top_level = framework.controls.filter(is_active=True, parent__isnull=True).order_by("code")
    return [
        {"control": control, "control_ids": control_and_descendant_ids(control)}
        for control in top_level
    ]


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
