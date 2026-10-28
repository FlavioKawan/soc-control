from django import template

register = template.Library()


@register.filter
def getattribute(obj, attr_name):
    """Generic dynamic-column access for the catalog list template."""
    value = getattr(obj, attr_name, "")
    if callable(value):
        value = value()
    if isinstance(value, (list, tuple)):
        return ", ".join(str(v) for v in value) if value else "-"
    if isinstance(value, bool):
        return "Sim" if value else "Não"
    return value
