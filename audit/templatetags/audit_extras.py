from django import template

register = template.Library()


@register.filter
def audit_changes(changes):
    """
    Renders an AuditLog.changes dict as "Campo: antigo → novo; ...".
    Handles both the [old, new] pairs produced for scalar/FK fields and the
    plain string description produced for many-to-many fields (see
    audit/signals.py).
    """
    if not changes:
        return "-"
    parts = []
    for field, value in changes.items():
        label = field.replace("_", " ").capitalize()
        if isinstance(value, list) and len(value) == 2:
            old, new = value
            parts.append(f"{label}: {old if old not in (None, '') else '—'} → {new if new not in (None, '') else '—'}")
        else:
            parts.append(f"{label}: {value}")
    return "; ".join(parts)
