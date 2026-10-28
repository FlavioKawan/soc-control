from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from catalog.models import ClientLogSource, ClientUseCase, LogSource, UseCase
from clients.models import Client
from detections.models import Rule
from taxonomy.choices import StatusScope
from taxonomy.models import ResponsibleParty, Severity, Status, Technology

from .forms import GapForm
from .models import Gap


class GapModelTests(TestCase):
    def setUp(self):
        self.client_obj = Client.objects.create(name="Acme Corp")

    def test_code_is_globally_unique(self):
        Gap.objects.create(code="GAP-001", client=self.client_obj, title="DNS logs ausentes")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Gap.objects.create(code="GAP-001", client=self.client_obj, title="Duplicado")

    def test_opened_at_defaults_to_today(self):
        from django.utils import timezone

        gap = Gap.objects.create(code="GAP-001", client=self.client_obj, title="DNS logs ausentes")
        self.assertEqual(gap.opened_at, timezone.localdate())

    def test_str_combines_code_and_title(self):
        gap = Gap.objects.create(code="GAP-001", client=self.client_obj, title="DNS logs ausentes")
        self.assertEqual(str(gap), "GAP-001 - DNS logs ausentes")


class GapFormScopeTests(TestCase):
    def setUp(self):
        self.client_a = Client.objects.create(name="Acme Corp")
        self.client_b = Client.objects.create(name="Globex")

    def test_status_field_only_offers_gap_scoped_statuses(self):
        gap_status = Status.objects.create(name="Aberto", scope=[StatusScope.GAP])
        Status.objects.create(name="Ativa", scope=[StatusScope.RULE])
        form = GapForm()
        self.assertIn(gap_status, form.fields["status"].queryset)
        self.assertEqual(form.fields["status"].queryset.count(), 1)

    def test_use_case_and_log_source_scoped_to_selected_client(self):
        use_case = UseCase.objects.create(code="UC-001", name="Brute Force")
        log_source = LogSource.objects.create(name="DNS Query Logs")
        ClientUseCase.objects.create(client=self.client_a, use_case=use_case)
        ClientLogSource.objects.create(client=self.client_a, log_source=log_source)

        other_use_case = UseCase.objects.create(code="UC-002", name="Password Spray")
        ClientUseCase.objects.create(client=self.client_b, use_case=other_use_case)

        form = GapForm(initial={"client": self.client_a.pk})
        self.assertIn(use_case, form.fields["use_case"].queryset)
        self.assertNotIn(other_use_case, form.fields["use_case"].queryset)
        self.assertIn(log_source, form.fields["log_source"].queryset)

    def test_without_a_client_all_use_cases_remain_available(self):
        use_case = UseCase.objects.create(code="UC-001", name="Brute Force")
        form = GapForm()
        self.assertIn(use_case, form.fields["use_case"].queryset)


class GapPermissionTests(TestCase):
    def setUp(self):
        call_command("setup_roles")
        self.client_obj = Client.objects.create(name="Acme Corp")
        self.gap = Gap.objects.create(code="GAP-001", client=self.client_obj, title="DNS logs ausentes")

    def test_soc_manager_has_full_crud(self):
        user = User.objects.create_user("manager", password="x")
        user.groups.add(Group.objects.get(name="SOC_MANAGER"))
        for perm in ["view_gap", "add_gap", "change_gap", "delete_gap"]:
            self.assertTrue(user.has_perm(f"gaps.{perm}"))

    def test_analyst_cannot_delete(self):
        user = User.objects.create_user("analyst", password="x")
        user.groups.add(Group.objects.get(name="ANALYST"))
        self.assertTrue(user.has_perm("gaps.add_gap"))
        self.assertFalse(user.has_perm("gaps.delete_gap"))

    def test_viewer_gets_403_on_create_page(self):
        user = User.objects.create_user("viewer", password="x")
        user.groups.add(Group.objects.get(name="VIEWER"))
        self.client.force_login(user)
        response = self.client.get(reverse("gaps:gap_create"))
        self.assertEqual(response.status_code, 403)


class GapFilterTests(TestCase):
    def setUp(self):
        call_command("setup_roles")
        self.user = User.objects.create_superuser("admin4", "admin4@example.com", "x")
        self.client.force_login(self.user)
        self.client_a = Client.objects.create(name="Acme Corp")
        self.client_b = Client.objects.create(name="Globex")
        self.gap_a = Gap.objects.create(code="GAP-001", client=self.client_a, title="DNS logs ausentes")
        self.gap_b = Gap.objects.create(code="GAP-002", client=self.client_b, title="VPN sem telemetria")

    def test_filter_by_client(self):
        response = self.client.get(reverse("gaps:gap_list"), {"client": self.client_a.pk})
        self.assertEqual(list(response.context["gaps"]), [self.gap_a])

    def test_text_search_matches_title(self):
        response = self.client.get(reverse("gaps:gap_list"), {"q": "VPN"})
        self.assertEqual(list(response.context["gaps"]), [self.gap_b])


class GapOptionalRelationshipTests(TestCase):
    def test_gap_can_reference_rule_use_case_and_log_source(self):
        client_obj = Client.objects.create(name="Acme Corp")
        technology = Technology.objects.create(name="Wazuh")
        rule = Rule.objects.create(internal_id="SOC-WIN-001", name="Brute Force", client=client_obj, technology=technology)
        use_case = UseCase.objects.create(code="UC-001", name="Brute Force")
        log_source = LogSource.objects.create(name="Windows Security")

        gap = Gap.objects.create(
            code="GAP-001", client=client_obj, title="Regra sem cobertura total",
            rule=rule, use_case=use_case, log_source=log_source,
        )
        self.assertEqual(gap.rule, rule)
        self.assertEqual(gap.use_case, use_case)
        self.assertEqual(gap.log_source, log_source)

    def test_deleting_referenced_rule_sets_gap_reference_to_null(self):
        client_obj = Client.objects.create(name="Acme Corp")
        technology = Technology.objects.create(name="Wazuh")
        rule = Rule.objects.create(internal_id="SOC-WIN-001", name="Brute Force", client=client_obj, technology=technology)
        gap = Gap.objects.create(code="GAP-001", client=client_obj, title="x", rule=rule)
        rule.delete()
        gap.refresh_from_db()
        self.assertIsNone(gap.rule)


class ResponsiblePartyCatalogTests(TestCase):
    def test_responsible_party_is_a_plain_configurable_catalog(self):
        soc = ResponsibleParty.objects.create(name="SOC")
        cliente = ResponsibleParty.objects.create(name="Cliente")
        self.assertEqual(soc.code, "soc")
        self.assertNotEqual(soc, cliente)

    def test_responsible_party_is_admin_only_via_generic_catalog_views(self):
        call_command("setup_roles")
        user = User.objects.create_user("manager2", password="x")
        user.groups.add(Group.objects.get(name="SOC_MANAGER"))
        self.assertFalse(user.has_perm("taxonomy.add_responsibleparty"))
        admin_user = User.objects.create_user("admin5", password="x")
        admin_user.groups.add(Group.objects.get(name="ADMIN"))
        self.assertTrue(admin_user.has_perm("taxonomy.add_responsibleparty"))
