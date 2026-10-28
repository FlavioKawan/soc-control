"""
Signal-based audit trail for Fase 9.

Deliberately scoped to the three entities a governance review asks about
most often - Cliente, Regra, Gap (see TRACKED_MODELS) - rather than every
model in the system. Diffing is done on concrete scalar/FK fields via
pre_save + post_save; many-to-many fields (tags, casos de uso, técnicas) are
tracked separately through m2m_changed, since they never appear in a normal
save() diff.
"""

import datetime

from django.db.models.signals import m2m_changed, post_delete, post_save, pre_delete, pre_save
from django.dispatch import receiver

from clients.models import Client
from detections.models import Rule
from gaps.models import Gap

from .middleware import get_current_user
from .models import AuditLog

TRACKED_MODELS = (Client, Rule, Gap)

#: Purely technical bookkeeping fields - never useful in a diff.
IGNORED_FIELDS = {"id", "created_at", "updated_at"}

#: {sender model: [m2m field names to track]} - only fields editable by users,
#: never a reverse/implicit through table.
TRACKED_M2M_FIELDS = {
    Rule: {"use_cases", "framework_controls", "tags"},
    Gap: {"tags"},
}

# Keyed by (model, pk); holds the pre-save snapshot so post_save can diff
# against it. Entries are popped as soon as they're consumed. In-memory and
# per-process is fine here - it never needs to survive past the save() call
# that created it.
_pending_snapshots = {}

# Client pks currently being deleted. Django's delete() collector nulls out
# AuditLog.client (on_delete=SET_NULL) only for rows that already existed
# when it scanned relations - never for rows our own signal handlers insert
# *during* that same delete (e.g. the DELETE entry for a Rule cascade-deleted
# together with its Client). Without this guard, such a new entry would
# reference a client row that disappears later in the same transaction and
# blow up with a ForeignKeyViolation. Populated in pre_delete (fired before
# any cascade deletes happen) and cleared in post_delete for Client itself.
_clients_being_deleted = set()


def _field_value(instance, field):
    value = getattr(instance, field.attname, None)
    if value is None:
        return None
    if field.is_relation:
        related = getattr(instance, field.name, None)
        return str(related) if related is not None else None
    if isinstance(value, (datetime.date, datetime.datetime)):
        return value.isoformat()
    return value if isinstance(value, (str, int, float, bool)) else str(value)


def _snapshot(instance):
    return {
        f.name: _field_value(instance, f)
        for f in instance._meta.concrete_fields
        if f.name not in IGNORED_FIELDS
    }


def _resolve_client(instance):
    if isinstance(instance, Client):
        return None if instance.pk in _clients_being_deleted else instance
    try:
        client = getattr(instance, "client", None)
    except Exception:
        # Defensive only: a cascading delete can remove the related Client
        # row before this instance's own post_delete runs.
        return None
    if client is not None and client.pk in _clients_being_deleted:
        return None
    return client


def _create_entry(instance, action, changes):
    AuditLog.objects.create(
        user=get_current_user(),
        action=action,
        app_label=instance._meta.app_label,
        model_name=instance._meta.model_name,
        object_id=str(instance.pk),
        object_repr=str(instance)[:255],
        client=_resolve_client(instance),
        changes=changes,
    )


@receiver(pre_delete, sender=Client)
def _mark_client_deleting(sender, instance, **kwargs):
    _clients_being_deleted.add(instance.pk)


@receiver(pre_save)
def _capture_snapshot(sender, instance, raw, **kwargs):
    if sender not in TRACKED_MODELS or raw or not instance.pk:
        return
    try:
        old = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        return
    _pending_snapshots[(sender, instance.pk)] = _snapshot(old)


@receiver(post_save)
def _log_save(sender, instance, created, raw, **kwargs):
    if sender not in TRACKED_MODELS or raw:
        return

    if created:
        _create_entry(instance, AuditLog.Action.CREATE, {})
        return

    old_values = _pending_snapshots.pop((sender, instance.pk), None)
    if old_values is None:
        return
    new_values = _snapshot(instance)
    changes = {
        field: [old_values.get(field), new_values.get(field)]
        for field in new_values
        if old_values.get(field) != new_values.get(field)
    }
    if changes:
        _create_entry(instance, AuditLog.Action.UPDATE, changes)


@receiver(post_delete)
def _log_delete(sender, instance, **kwargs):
    if sender not in TRACKED_MODELS:
        return
    # Client itself gone from the DB by the time this fires - _resolve_client
    # checks _clients_being_deleted and returns None for it, never a
    # self-reference to a row that no longer exists.
    _create_entry(instance, AuditLog.Action.DELETE, _snapshot(instance))
    if sender is Client:
        # Safe to stop tracking now - Client's own post_delete always runs
        # last among cascade-deleted rows (children are deleted first).
        _clients_being_deleted.discard(instance.pk)


@receiver(m2m_changed)
def _log_m2m_change(sender, instance, action, pk_set, model, field_name=None, **kwargs):
    if action not in ("post_add", "post_remove", "post_clear"):
        return
    owner = type(instance)
    if owner not in TRACKED_MODELS:
        return
    tracked_fields = TRACKED_M2M_FIELDS.get(owner, set())
    # m2m_changed doesn't pass the field name directly - recover it from the
    # through table's metadata on `sender`.
    name = next(
        (f.name for f in owner._meta.many_to_many if f.remote_field.through == sender),
        None,
    )
    if name is None or name not in tracked_fields:
        return

    if action == "post_clear":
        description = "todos os itens removidos"
    else:
        verb = "adicionado(s)" if action == "post_add" else "removido(s)"
        items = list(model.objects.filter(pk__in=pk_set or []))
        description = f"{verb}: " + ", ".join(str(item) for item in items) if items else verb

    _create_entry(instance, AuditLog.Action.UPDATE, {name: description})
