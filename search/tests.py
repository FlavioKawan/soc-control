from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from catalog.models import LogSource, UseCase
from clients.models import Client
from detections.models import Rule
from gaps.models import Gap
from taxonomy.models import Technology


class GlobalSearchTests(TestCase):
    def setUp(self):
        call_command("setup_roles")
        self.user = User.objects.create_superuser("admin", "admin@example.com", "x")
        self.client.force_login(self.user)

        self.client_obj = Client.objects.create(name="Acme Corp")
        technology = Technology.objects.create(name="Wazuh")
        self.rule = Rule.objects.create(
            internal_id="SOC-WIN-001", name="Brute Force", client=self.client_obj, technology=technology
        )
        self.gap = Gap.objects.create(code="GAP-001", client=self.client_obj, title="DNS logs ausentes")
        self.use_case = UseCase.objects.create(code="UC-001", name="Brute Force")
        self.log_source = LogSource.objects.create(name="Windows Security")

    def test_empty_query_returns_no_categories(self):
        response = self.client.get(reverse("search:results"))
        self.assertEqual(response.context["categories"], [])

    def test_query_matches_across_all_entities(self):
        response = self.client.get(reverse("search:results"), {"q": "Brute Force"})
        labels = {c["label"]: c["total"] for c in response.context["categories"]}
        self.assertEqual(labels.get("Regras"), 1)
        self.assertEqual(labels.get("Casos de Uso"), 1)

    def test_query_matches_client_by_name(self):
        response = self.client.get(reverse("search:results"), {"q": "Acme"})
        labels = {c["label"]: c["total"] for c in response.context["categories"]}
        self.assertEqual(labels.get("Clientes"), 1)

    def test_query_matches_gap_by_code(self):
        response = self.client.get(reverse("search:results"), {"q": "GAP-001"})
        labels = {c["label"]: c["total"] for c in response.context["categories"]}
        self.assertEqual(labels.get("Gaps"), 1)

    def test_query_matches_log_source_by_name(self):
        response = self.client.get(reverse("search:results"), {"q": "Windows"})
        labels = {c["label"]: c["total"] for c in response.context["categories"]}
        self.assertEqual(labels.get("Fontes de Log"), 1)

    def test_no_match_reports_no_results(self):
        response = self.client.get(reverse("search:results"), {"q": "nonexistent-xyz"})
        self.assertFalse(response.context["has_results"])

    def test_anonymous_user_is_redirected_to_login(self):
        self.client.logout()
        response = self.client.get(reverse("search:results"), {"q": "Acme"})
        self.assertEqual(response.status_code, 302)


class GlobalSearchPermissionScopingTests(TestCase):
    """
    A VIEWER has no app-specific create/change rights but does hold every
    "view_*" permission (see setup_roles) - so they should still see every
    category. A user with none of those view permissions should see none.
    """

    def setUp(self):
        call_command("setup_roles")
        self.client_obj = Client.objects.create(name="Acme Corp")

    def test_viewer_sees_client_category(self):
        user = User.objects.create_user("viewer", password="x")
        user.groups.add(Group.objects.get(name="VIEWER"))
        self.client.force_login(user)

        response = self.client.get(reverse("search:results"), {"q": "Acme"})
        labels = {c["label"] for c in response.context["categories"]}
        self.assertIn("Clientes", labels)

    def test_user_without_any_view_permission_sees_no_categories(self):
        user = User.objects.create_user("nobody", password="x")
        self.client.force_login(user)

        response = self.client.get(reverse("search:results"), {"q": "Acme"})
        self.assertEqual(response.context["categories"], [])
