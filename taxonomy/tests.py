import json

from django.contrib.auth.models import Group, Permission, User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from clients.models import Client
from detections.models import Rule

from .choices import CategoryScope, StatusCategory, StatusScope
from .models import Category, Framework, FrameworkControl, Severity, Status, Tag, Technology
from .services import build_navigator_layer


class ConfigurableOptionTests(TestCase):
    def test_code_is_auto_generated_from_name_when_blank(self):
        tech = Technology.objects.create(name="Google SecOps")
        self.assertEqual(tech.code, "google-secops")

    def test_code_is_preserved_when_explicitly_set(self):
        tech = Technology.objects.create(name="Google SecOps", code="secops")
        self.assertEqual(tech.code, "secops")

    def test_code_must_be_unique(self):
        Technology.objects.create(name="Wazuh")
        with self.assertRaises(Exception):
            Technology.objects.create(name="Wazuh")

    def test_new_technology_does_not_require_code_changes(self):
        """
        The whole point of the catalog: adding a brand new technology is a
        plain row insert, never a code/deploy change.
        """
        before = Technology.objects.count()
        Technology.objects.create(name="Microsoft Sentinel")
        self.assertEqual(Technology.objects.count(), before + 1)


class StatusSemanticsTests(TestCase):
    """
    The visual name of a Status is free text, but business logic must only
    ever depend on `category` (fixed internal enum) and `scope`.
    """

    def test_status_visual_name_is_free_but_category_is_constrained(self):
        status = Status.objects.create(
            name="Em Homologação",
            category=StatusCategory.TESTING,
            scope=[StatusScope.RULE],
        )
        self.assertEqual(status.category, StatusCategory.TESTING)
        self.assertIn(StatusScope.RULE, status.scope)

    def test_two_different_visual_names_can_share_the_same_internal_category(self):
        active_a = Status.objects.create(name="Ativa", category=StatusCategory.ACTIVE)
        active_b = Status.objects.create(name="Em Produção", category=StatusCategory.ACTIVE)
        self.assertEqual(active_a.category, active_b.category)
        self.assertNotEqual(active_a.name, active_b.name)


class CategoryScopeTests(TestCase):
    def test_category_applicable_to_accepts_multiple_scopes(self):
        category = Category.objects.create(
            name="Identidade",
            applicable_to=[CategoryScope.USE_CASE, CategoryScope.RULE],
        )
        self.assertIn(CategoryScope.USE_CASE, category.applicable_to)
        self.assertIn(CategoryScope.RULE, category.applicable_to)
        self.assertNotIn(CategoryScope.LOG_SOURCE, category.applicable_to)


class SeverityOrderingTests(TestCase):
    def test_severities_order_by_order_field_then_name(self):
        Severity.objects.create(name="Crítica", weight=100, order=4)
        Severity.objects.create(name="Baixa", weight=20, order=2)
        Severity.objects.create(name="Alta", weight=75, order=3)
        names = list(Severity.objects.values_list("name", flat=True))
        self.assertEqual(names, ["Baixa", "Alta", "Crítica"])


class CatalogPermissionTests(TestCase):
    """
    Only ADMIN should manage configuration catalogs; SOC_MANAGER/ANALYST
    must not, even though they manage operational entities.
    """

    def setUp(self):
        call_command("setup_roles")
        Tag.objects.create(name="Windows")

    def test_admin_group_can_add_tags(self):
        user = User.objects.create_user("admin_user", password="x")
        user.groups.add(Group.objects.get(name="ADMIN"))
        self.assertTrue(user.has_perm("taxonomy.add_tag"))

    def test_soc_manager_cannot_manage_taxonomy(self):
        user = User.objects.create_user("manager_user", password="x")
        user.groups.add(Group.objects.get(name="SOC_MANAGER"))
        self.assertFalse(user.has_perm("taxonomy.add_tag"))
        self.assertFalse(user.has_perm("taxonomy.change_tag"))

    def test_viewer_group_has_read_only_access_to_taxonomy(self):
        user = User.objects.create_user("viewer_user", password="x")
        user.groups.add(Group.objects.get(name="VIEWER"))
        self.assertTrue(user.has_perm("taxonomy.view_tag"))
        self.assertFalse(user.has_perm("taxonomy.add_tag"))

    def test_catalog_list_view_requires_login(self):
        response = self.client.get(reverse("taxonomy:catalog_list", kwargs={"catalog": "tags"}))
        self.assertEqual(response.status_code, 302)

    def test_unknown_catalog_slug_returns_404(self):
        self.client.force_login(
            User.objects.create_superuser("super_user", "super@example.com", "x")
        )
        response = self.client.get(reverse("taxonomy:catalog_list", kwargs={"catalog": "does-not-exist"}))
        self.assertEqual(response.status_code, 404)

    def test_viewer_gets_403_on_catalog_create(self):
        user = User.objects.create_user("viewer_user2", password="x")
        user.groups.add(Group.objects.get(name="VIEWER"))
        self.client.force_login(user)
        response = self.client.get(reverse("taxonomy:catalog_create", kwargs={"catalog": "tags"}))
        self.assertEqual(response.status_code, 403)

    def test_deleting_status_in_use_shows_a_friendly_message_instead_of_500(self):
        admin_user = User.objects.create_user("admin_statusdel", password="x")
        admin_user.groups.add(Group.objects.get(name="ADMIN"))
        self.client.force_login(admin_user)
        status = Status.objects.create(name="Ativo")
        Client.objects.create(name="Acme Corp", status=status)

        response = self.client.post(
            reverse("taxonomy:catalog_delete", kwargs={"catalog": "status", "pk": status.pk})
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(Status.objects.filter(pk=status.pk).exists())
        messages = list(response.wsgi_request._messages)
        self.assertTrue(any("ainda está em uso" in str(m) for m in messages))


class NavigatorLayerServiceTests(TestCase):
    def setUp(self):
        self.framework = Framework.objects.create(name="MITRE ATT&CK")
        self.control = FrameworkControl.objects.create(
            framework=self.framework, code="T1110", name="Brute Force"
        )
        self.client_a = Client.objects.create(name="Acme Corp")
        self.client_b = Client.objects.create(name="Globex")
        self.technology = Technology.objects.create(name="Wazuh")

    def test_control_with_no_linked_rules_is_left_out(self):
        layer = build_navigator_layer(self.framework)
        self.assertEqual(layer["techniques"], [])

    def test_control_score_counts_linked_rules(self):
        rule = Rule.objects.create(
            internal_id="SOC-001", name="Brute Force", client=self.client_a, technology=self.technology
        )
        rule.framework_controls.add(self.control)

        layer = build_navigator_layer(self.framework)
        self.assertEqual(layer["techniques"], [{
            "techniqueID": "T1110", "score": 1, "comment": "1 regra(s) de detecção vinculada(s)."
        }])

    def test_client_filter_only_counts_that_clients_rules(self):
        rule_a = Rule.objects.create(
            internal_id="SOC-001", name="Brute Force A", client=self.client_a, technology=self.technology
        )
        rule_a.framework_controls.add(self.control)
        rule_b = Rule.objects.create(
            internal_id="SOC-002", name="Brute Force B", client=self.client_b, technology=self.technology
        )
        rule_b.framework_controls.add(self.control)

        layer = build_navigator_layer(self.framework, client=self.client_a)
        self.assertEqual(layer["techniques"][0]["score"], 1)

    def test_layer_name_mentions_framework_and_scope(self):
        layer = build_navigator_layer(self.framework, client=self.client_a)
        self.assertIn("MITRE ATT&CK", layer["name"])
        self.assertIn("Acme Corp", layer["name"])


class NavigatorExportViewTests(TestCase):
    def setUp(self):
        call_command("setup_roles")
        self.framework = Framework.objects.create(name="MITRE ATT&CK")
        control = FrameworkControl.objects.create(framework=self.framework, code="T1110", name="Brute Force")
        client_obj = Client.objects.create(name="Acme Corp")
        technology = Technology.objects.create(name="Wazuh")
        rule = Rule.objects.create(
            internal_id="SOC-001", name="Brute Force", client=client_obj, technology=technology
        )
        rule.framework_controls.add(control)

    def test_viewer_can_download_the_layer_as_json(self):
        user = User.objects.create_user("viewer", password="x")
        user.groups.add(Group.objects.get(name="VIEWER"))
        self.client.force_login(user)

        response = self.client.get(reverse("taxonomy:framework_navigator_export", kwargs={"pk": self.framework.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/json")
        payload = json.loads(response.content)
        self.assertEqual(payload["techniques"][0]["techniqueID"], "T1110")

    def test_analyst_without_view_framework_permission_gets_403(self):
        user = User.objects.create_user("analyst", password="x")
        user.groups.add(Group.objects.get(name="ANALYST"))
        self.client.force_login(user)

        response = self.client.get(reverse("taxonomy:framework_navigator_export", kwargs={"pk": self.framework.pk}))
        self.assertEqual(response.status_code, 403)
