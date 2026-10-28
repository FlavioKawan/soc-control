"""
Creates/updates the four standard SOC Control groups and their permissions.

This command is idempotent and safe to re-run after every `migrate` as new
apps/models are added in later phases - it simply (re)grants permissions for
whatever models exist at the time it runs, so role scopes never need to be
hardcoded against a fixed list of models.

Roles:
    ADMIN         - full access to everything, including configuration catalogs.
    SOC_MANAGER   - full CRUD on operational entities (clients, catalog,
                    detections, gaps), no access to configuration catalogs
                    or user/group management.
    ANALYST       - add/change/view on operational entities, no delete, no
                    configuration access.
    VIEWER        - read-only on operational entities and configuration.

"Configuration" apps (catalogs managed under "Configurações") are kept
admin-only on purpose: business catalogs (status, severity, technology,
etc.) are structural to how the whole system behaves, so only ADMIN should
be able to change them.
"""

from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand

CONFIG_APPS = ["taxonomy"]
OPERATIONAL_APPS = ["clients", "catalog", "detections", "gaps"]
# The audit trail is never editable through the UI (its ModelAdmin blocks
# add/change/delete outright) - so no group other than ADMIN gets anything
# but view_auditlog, no matter how much CRUD it has elsewhere.
READ_ONLY_APPS = ["audit"]


def _perms_for_apps(app_labels, actions=None):
    qs = Permission.objects.filter(content_type__app_label__in=app_labels)
    if actions:
        qs = qs.filter(codename__regex=r"^(%s)_" % "|".join(actions))
    return qs


class Command(BaseCommand):
    help = "Create/update the ADMIN, SOC_MANAGER, ANALYST and VIEWER groups."

    def handle(self, *args, **options):
        admin_group, _ = Group.objects.get_or_create(name="ADMIN")
        admin_group.permissions.set(Permission.objects.all())

        manager_group, _ = Group.objects.get_or_create(name="SOC_MANAGER")
        manager_group.permissions.set(
            list(_perms_for_apps(OPERATIONAL_APPS)) + list(_perms_for_apps(READ_ONLY_APPS, actions=["view"]))
        )

        analyst_group, _ = Group.objects.get_or_create(name="ANALYST")
        analyst_group.permissions.set(
            list(_perms_for_apps(OPERATIONAL_APPS, actions=["add", "change", "view"]))
            + list(_perms_for_apps(READ_ONLY_APPS, actions=["view"]))
        )

        viewer_group, _ = Group.objects.get_or_create(name="VIEWER")
        viewer_group.permissions.set(
            _perms_for_apps(OPERATIONAL_APPS + CONFIG_APPS + READ_ONLY_APPS, actions=["view"])
        )

        self.stdout.write(self.style.SUCCESS(
            "Groups ADMIN, SOC_MANAGER, ANALYST and VIEWER are up to date."
        ))
