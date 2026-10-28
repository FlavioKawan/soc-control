from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from taxonomy.choices import StatusCategory, StatusScope
from taxonomy.models import Status

from .forms import ClientForm
from .models import Client


class ClientModelTests(TestCase):
    def test_client_can_be_created_without_a_status(self):
        client = Client.objects.create(name="Acme Corp")
        self.assertIsNone(client.status)

    def test_status_with_wrong_scope_cannot_protect_against_wrong_assignment_silently(self):
        """
        Assigning a Status whose scope does NOT include CLIENT is still
        allowed at the DB level (FK has no CHECK constraint on array
        contents) - the form is what enforces the catalog's intent. This
        test documents that boundary so it isn't "discovered" later.
        """
        rule_only_status = Status.objects.create(name="Em Teste", scope=[StatusScope.RULE])
        client = Client.objects.create(name="Acme Corp", status=rule_only_status)
        self.assertEqual(client.status, rule_only_status)


class ClientFormScopeTests(TestCase):
    def test_form_only_offers_statuses_scoped_to_client(self):
        client_status = Status.objects.create(name="Ativo", scope=[StatusScope.CLIENT], category=StatusCategory.ACTIVE)
        Status.objects.create(name="Em Teste", scope=[StatusScope.RULE])
        form = ClientForm()
        self.assertIn(client_status, form.fields["status"].queryset)
        self.assertEqual(form.fields["status"].queryset.count(), 1)

    def test_form_keeps_currently_selected_status_even_if_inactive(self):
        status = Status.objects.create(
            name="Descontinuado", scope=[StatusScope.CLIENT], is_active=False
        )
        client = Client.objects.create(name="Acme Corp", status=status)
        form = ClientForm(instance=client)
        self.assertIn(status, form.fields["status"].queryset)


class ClientPermissionTests(TestCase):
    def setUp(self):
        call_command("setup_roles")
        self.client_obj = Client.objects.create(name="Acme Corp")

    def test_soc_manager_has_full_crud(self):
        user = User.objects.create_user("manager", password="x")
        user.groups.add(Group.objects.get(name="SOC_MANAGER"))
        for perm in ["view_client", "add_client", "change_client", "delete_client"]:
            self.assertTrue(user.has_perm(f"clients.{perm}"))

    def test_analyst_cannot_delete(self):
        user = User.objects.create_user("analyst", password="x")
        user.groups.add(Group.objects.get(name="ANALYST"))
        self.assertTrue(user.has_perm("clients.add_client"))
        self.assertTrue(user.has_perm("clients.change_client"))
        self.assertFalse(user.has_perm("clients.delete_client"))

    def test_viewer_is_read_only(self):
        user = User.objects.create_user("viewer", password="x")
        user.groups.add(Group.objects.get(name="VIEWER"))
        self.assertTrue(user.has_perm("clients.view_client"))
        self.assertFalse(user.has_perm("clients.add_client"))

    def test_viewer_gets_403_on_create_page(self):
        user = User.objects.create_user("viewer2", password="x")
        user.groups.add(Group.objects.get(name="VIEWER"))
        self.client.force_login(user)
        response = self.client.get(reverse("clients:client_create"))
        self.assertEqual(response.status_code, 403)

    def test_anonymous_is_redirected_to_login(self):
        response = self.client.get(reverse("clients:client_list"))
        self.assertEqual(response.status_code, 302)


class ClientListSearchTests(TestCase):
    def setUp(self):
        call_command("setup_roles")
        Client.objects.create(name="Acme Corp")
        Client.objects.create(name="Globex", legal_name="Globex Industrias Ltda")
        self.user = User.objects.create_superuser("admin2", "admin2@example.com", "x")
        self.client.force_login(self.user)

    def test_search_filters_by_name(self):
        response = self.client.get(reverse("clients:client_list"), {"q": "Acme"})
        names = [c.name for c in response.context["clients"]]
        self.assertEqual(names, ["Acme Corp"])

    def test_search_filters_by_legal_name(self):
        response = self.client.get(reverse("clients:client_list"), {"q": "Industrias"})
        names = [c.name for c in response.context["clients"]]
        self.assertEqual(names, ["Globex"])

    def test_empty_search_returns_all(self):
        response = self.client.get(reverse("clients:client_list"))
        self.assertEqual(len(response.context["clients"]), 2)
