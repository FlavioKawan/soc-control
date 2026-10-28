from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from catalog.models import UseCase
from clients.models import Client
from detections.models import Rule
from gaps.models import Gap
from taxonomy.models import Status, Technology

from .models import AuditLog


class AuditLogCreateUpdateDeleteTests(TestCase):
    def setUp(self):
        call_command("setup_roles")
        self.user = User.objects.create_user("analyst1", password="x")
        self.user.groups.add(Group.objects.get(name="SOC_MANAGER"))
        self.client.force_login(self.user)

    def test_creating_a_client_logs_create(self):
        response = self.client.post(reverse("clients:client_create"), {"name": "Acme Corp"})
        self.assertEqual(response.status_code, 302)
        entry = AuditLog.objects.get(app_label="clients", model_name="client")
        self.assertEqual(entry.action, AuditLog.Action.CREATE)
        self.assertEqual(entry.user, self.user)
        self.assertEqual(entry.object_repr, "Acme Corp")
        self.assertEqual(entry.changes, {})

    def test_updating_a_client_logs_only_changed_fields(self):
        client_obj = Client.objects.create(name="Acme Corp")
        AuditLog.objects.all().delete()  # isolate from the CREATE entry above

        client_obj.name = "Acme Corporation"
        client_obj.save()

        entry = AuditLog.objects.get(action=AuditLog.Action.UPDATE)
        self.assertEqual(entry.changes, {"name": ["Acme Corp", "Acme Corporation"]})

    def test_saving_without_changes_does_not_create_a_log_entry(self):
        client_obj = Client.objects.create(name="Acme Corp")
        AuditLog.objects.all().delete()

        client_obj.save()  # no field actually changed

        self.assertEqual(AuditLog.objects.filter(action=AuditLog.Action.UPDATE).count(), 0)

    def test_deleting_a_rule_logs_delete_with_a_snapshot(self):
        client_obj = Client.objects.create(name="Acme Corp")
        technology = Technology.objects.create(name="Wazuh")
        rule = Rule.objects.create(internal_id="SOC-WIN-001", name="Brute Force", client=client_obj, technology=technology)
        AuditLog.objects.all().delete()

        rule_pk = rule.pk
        rule.delete()

        entry = AuditLog.objects.get(action=AuditLog.Action.DELETE)
        self.assertEqual(entry.object_id, str(rule_pk))
        self.assertEqual(entry.changes["internal_id"], "SOC-WIN-001")
        self.assertEqual(entry.client, client_obj)

    def test_deleting_a_client_does_not_reference_the_deleted_client_as_fk(self):
        client_obj = Client.objects.create(name="Acme Corp")
        AuditLog.objects.all().delete()

        client_obj.delete()

        entry = AuditLog.objects.get(action=AuditLog.Action.DELETE, model_name="client")
        self.assertIsNone(entry.client)

    def test_deleting_a_client_with_rules_and_gaps_does_not_violate_the_fk(self):
        # Regression test: Client.rules/gaps cascade-delete on client removal,
        # and each cascade-deleted Rule/Gap used to get a fresh AuditLog entry
        # pointing at the client row that's about to disappear in the very
        # same transaction - a real ForeignKeyViolation, not just a lint nit.
        client_obj = Client.objects.create(name="Acme Corp")
        technology = Technology.objects.create(name="Wazuh")
        rule = Rule.objects.create(internal_id="SOC-WIN-001", name="Brute Force", client=client_obj, technology=technology)
        Gap.objects.create(code="GAP-001", client=client_obj, title="x")
        AuditLog.objects.all().delete()

        client_obj.delete()  # must not raise IntegrityError

        delete_entries = AuditLog.objects.filter(action=AuditLog.Action.DELETE)
        self.assertEqual(delete_entries.count(), 3)  # client + rule + gap
        self.assertTrue(all(e.client_id is None for e in delete_entries))
        rule_entry = delete_entries.get(model_name="rule")
        self.assertEqual(rule_entry.object_id, str(rule.pk))


class AuditLogM2MTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("analyst2", password="x")
        self.client_obj = Client.objects.create(name="Acme Corp")
        self.technology = Technology.objects.create(name="Wazuh")
        self.rule = Rule.objects.create(
            internal_id="SOC-WIN-001", name="Brute Force", client=self.client_obj, technology=self.technology
        )

    def test_adding_a_use_case_logs_an_update_entry(self):
        use_case = UseCase.objects.create(code="UC-001", name="Brute Force")
        AuditLog.objects.all().delete()

        self.rule.use_cases.add(use_case)

        entry = AuditLog.objects.get(action=AuditLog.Action.UPDATE, object_id=str(self.rule.pk))
        self.assertIn("UC-001", entry.changes["use_cases"])


class AuditLogUserAttributionTests(TestCase):
    def test_entry_records_the_logged_in_user_via_middleware(self):
        call_command("setup_roles")
        user = User.objects.create_user("analyst3", password="x")
        user.groups.add(Group.objects.get(name="SOC_MANAGER"))
        self.client.force_login(user)
        self.client.post(reverse("clients:client_create"), {"name": "Globex"})
        entry = AuditLog.objects.get(app_label="clients", model_name="client")
        self.assertEqual(entry.user, user)

    def test_changes_made_outside_a_request_have_no_user(self):
        Client.objects.create(name="Acme Corp")
        entry = AuditLog.objects.get(app_label="clients", model_name="client")
        self.assertIsNone(entry.user)


class AuditLogPermissionAndListViewTests(TestCase):
    def setUp(self):
        call_command("setup_roles")
        self.client_obj = Client.objects.create(name="Acme Corp")

    def test_soc_manager_can_view_history(self):
        user = User.objects.create_user("manager", password="x")
        user.groups.add(Group.objects.get(name="SOC_MANAGER"))
        self.assertTrue(user.has_perm("audit.view_auditlog"))
        self.client.force_login(user)
        response = self.client.get(reverse("audit:auditlog_list"))
        self.assertEqual(response.status_code, 200)

    def test_list_view_filters_by_client(self):
        other_client = Client.objects.create(name="Globex")
        admin_user = User.objects.create_user("admin6", password="x")
        admin_user.groups.add(Group.objects.get(name="ADMIN"))
        self.client.force_login(admin_user)

        response = self.client.get(reverse("audit:auditlog_list"), {"client": self.client_obj.pk})
        entries = response.context["entries"]
        self.assertTrue(all(e.client_id == self.client_obj.pk for e in entries))
        self.assertTrue(entries)

    def test_audit_log_itself_cannot_be_created_changed_or_deleted_via_permissions(self):
        # Read-only by design: setup_roles only ever grants *_rule/_client/etc,
        # but AuditLog's own add/change/delete perms should never be handed out.
        admin_user = User.objects.create_user("admin7", password="x")
        admin_user.groups.add(Group.objects.get(name="SOC_MANAGER"))
        self.assertFalse(admin_user.has_perm("audit.add_auditlog"))
        self.assertFalse(admin_user.has_perm("audit.change_auditlog"))
        self.assertFalse(admin_user.has_perm("audit.delete_auditlog"))
