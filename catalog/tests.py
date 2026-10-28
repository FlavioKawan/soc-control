from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from clients.models import Client
from taxonomy.choices import CategoryScope, StatusCategory, StatusScope
from taxonomy.models import Category, Status

from .forms import ClientLogSourceForm, ClientUseCaseForm, LogSourceForm, UseCaseForm
from .models import (
    ClientLogSource,
    ClientUseCase,
    ImplementationTemplate,
    LogSource,
    TemplateLogSource,
    TemplateUseCase,
    UseCase,
)
from .services import apply_template_to_client, compute_use_case_coverage


class LogSourceCatalogTests(TestCase):
    def test_log_source_name_is_globally_unique(self):
        LogSource.objects.create(name="Windows Security")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                LogSource.objects.create(name="Windows Security")

    def test_log_source_form_only_offers_categories_scoped_to_log_source(self):
        log_source_category = Category.objects.create(
            name="Identidade", applicable_to=[CategoryScope.LOG_SOURCE]
        )
        Category.objects.create(name="Malware", applicable_to=[CategoryScope.RULE])
        form = LogSourceForm()
        self.assertIn(log_source_category, form.fields["category"].queryset)
        self.assertEqual(form.fields["category"].queryset.count(), 1)


class ClientLogSourceTests(TestCase):
    def setUp(self):
        self.client_obj = Client.objects.create(name="Acme Corp")
        self.log_source = LogSource.objects.create(name="Sysmon")

    def test_same_log_source_cannot_be_linked_twice_to_the_same_client(self):
        ClientLogSource.objects.create(client=self.client_obj, log_source=self.log_source)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ClientLogSource.objects.create(client=self.client_obj, log_source=self.log_source)

    def test_same_log_source_can_be_linked_to_two_different_clients(self):
        other_client = Client.objects.create(name="Globex")
        ClientLogSource.objects.create(client=self.client_obj, log_source=self.log_source)
        ClientLogSource.objects.create(client=other_client, log_source=self.log_source)
        self.assertEqual(ClientLogSource.objects.filter(log_source=self.log_source).count(), 2)

    def test_deleting_log_source_in_use_is_blocked(self):
        ClientLogSource.objects.create(client=self.client_obj, log_source=self.log_source)
        with self.assertRaises(Exception):
            with transaction.atomic():
                self.log_source.delete()
        self.assertTrue(LogSource.objects.filter(pk=self.log_source.pk).exists())

    def test_form_excludes_log_sources_already_linked_to_this_client(self):
        ClientLogSource.objects.create(client=self.client_obj, log_source=self.log_source)
        other_log_source = LogSource.objects.create(name="DNS")
        form = ClientLogSourceForm(client=self.client_obj)
        self.assertNotIn(self.log_source, form.fields["log_source"].queryset)
        self.assertIn(other_log_source, form.fields["log_source"].queryset)

    def test_editing_existing_link_keeps_its_own_log_source_selectable(self):
        link = ClientLogSource.objects.create(client=self.client_obj, log_source=self.log_source)
        form = ClientLogSourceForm(instance=link, client=self.client_obj)
        self.assertIn(self.log_source, form.fields["log_source"].queryset)

    def test_status_queryset_limited_to_client_log_source_scope(self):
        matching = Status.objects.create(
            name="Recebendo", scope=[StatusScope.CLIENT_LOG_SOURCE], category=StatusCategory.RECEIVING
        )
        Status.objects.create(name="Em Teste", scope=[StatusScope.RULE])
        form = ClientLogSourceForm(client=self.client_obj)
        self.assertIn(matching, form.fields["status"].queryset)
        self.assertEqual(form.fields["status"].queryset.count(), 1)

    def test_deleting_log_source_in_use_shows_a_friendly_message_instead_of_500(self):
        call_command("setup_roles")
        admin_user = User.objects.create_user("admin_lsdel", password="x")
        admin_user.groups.add(Group.objects.get(name="ADMIN"))
        self.client.force_login(admin_user)
        ClientLogSource.objects.create(client=self.client_obj, log_source=self.log_source)

        response = self.client.post(
            reverse("catalog:logsource_delete", kwargs={"pk": self.log_source.pk})
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(LogSource.objects.filter(pk=self.log_source.pk).exists())
        messages = list(response.wsgi_request._messages)
        self.assertTrue(any("ainda está em uso" in str(m) for m in messages))


class CatalogPermissionTests(TestCase):
    def setUp(self):
        call_command("setup_roles")
        self.client_obj = Client.objects.create(name="Acme Corp")
        self.log_source = LogSource.objects.create(name="Sysmon")

    def test_soc_manager_has_full_crud_on_logsource(self):
        user = User.objects.create_user("manager", password="x")
        user.groups.add(Group.objects.get(name="SOC_MANAGER"))
        for perm in ["view_logsource", "add_logsource", "change_logsource", "delete_logsource"]:
            self.assertTrue(user.has_perm(f"catalog.{perm}"))

    def test_viewer_cannot_add_client_log_source(self):
        user = User.objects.create_user("viewer", password="x")
        user.groups.add(Group.objects.get(name="VIEWER"))
        self.client.force_login(user)
        response = self.client.get(
            reverse("catalog:clientlogsource_create", kwargs={"client_pk": self.client_obj.pk})
        )
        self.assertEqual(response.status_code, 403)

    def test_analyst_can_add_but_not_delete_logsource(self):
        user = User.objects.create_user("analyst", password="x")
        user.groups.add(Group.objects.get(name="ANALYST"))
        self.assertTrue(user.has_perm("catalog.add_logsource"))
        self.assertFalse(user.has_perm("catalog.delete_logsource"))


class UseCaseCatalogTests(TestCase):
    def test_use_case_code_is_globally_unique(self):
        UseCase.objects.create(code="UC-001", name="Brute Force")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                UseCase.objects.create(code="UC-001", name="Duplicate")

    def test_use_case_form_only_offers_categories_scoped_to_use_case(self):
        use_case_category = Category.objects.create(
            name="Identidade", applicable_to=[CategoryScope.USE_CASE]
        )
        Category.objects.create(name="Rede", applicable_to=[CategoryScope.LOG_SOURCE])
        form = UseCaseForm()
        self.assertIn(use_case_category, form.fields["category"].queryset)
        self.assertEqual(form.fields["category"].queryset.count(), 1)


class ClientUseCaseTests(TestCase):
    def setUp(self):
        self.client_obj = Client.objects.create(name="Acme Corp")
        self.use_case = UseCase.objects.create(code="UC-001", name="Brute Force")

    def test_same_use_case_cannot_be_linked_twice_to_the_same_client(self):
        ClientUseCase.objects.create(client=self.client_obj, use_case=self.use_case)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ClientUseCase.objects.create(client=self.client_obj, use_case=self.use_case)

    def test_deleting_use_case_in_use_is_blocked(self):
        ClientUseCase.objects.create(client=self.client_obj, use_case=self.use_case)
        with self.assertRaises(Exception):
            with transaction.atomic():
                self.use_case.delete()
        self.assertTrue(UseCase.objects.filter(pk=self.use_case.pk).exists())

    def test_form_excludes_use_cases_already_linked_to_this_client(self):
        ClientUseCase.objects.create(client=self.client_obj, use_case=self.use_case)
        other_use_case = UseCase.objects.create(code="UC-002", name="Password Spraying")
        form = ClientUseCaseForm(client=self.client_obj)
        self.assertNotIn(self.use_case, form.fields["use_case"].queryset)
        self.assertIn(other_use_case, form.fields["use_case"].queryset)

    def test_status_queryset_limited_to_client_use_case_scope(self):
        matching = Status.objects.create(
            name="Coberto", scope=[StatusScope.CLIENT_USE_CASE], category=StatusCategory.COVERED
        )
        Status.objects.create(name="Recebendo", scope=[StatusScope.CLIENT_LOG_SOURCE])
        form = ClientUseCaseForm(client=self.client_obj)
        self.assertIn(matching, form.fields["status"].queryset)
        self.assertEqual(form.fields["status"].queryset.count(), 1)

    def test_deleting_use_case_in_use_shows_a_friendly_message_instead_of_500(self):
        call_command("setup_roles")
        admin_user = User.objects.create_user("admin_ucdel", password="x")
        admin_user.groups.add(Group.objects.get(name="ADMIN"))
        self.client.force_login(admin_user)
        ClientUseCase.objects.create(client=self.client_obj, use_case=self.use_case)

        response = self.client.post(
            reverse("catalog:usecase_delete", kwargs={"pk": self.use_case.pk})
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(UseCase.objects.filter(pk=self.use_case.pk).exists())
        messages = list(response.wsgi_request._messages)
        self.assertTrue(any("ainda está em uso" in str(m) for m in messages))


class CoverageCalculationTests(TestCase):
    """
    "X% of applicable use cases are covered" - NOT_APPLICABLE items must
    never enter the denominator, per the spec's explicit requirement that
    coverage metrics stay explainable.
    """

    def setUp(self):
        self.client_obj = Client.objects.create(name="Acme Corp")
        self.covered_status = Status.objects.create(
            name="Coberto", scope=[StatusScope.CLIENT_USE_CASE], category=StatusCategory.COVERED
        )
        self.partial_status = Status.objects.create(
            name="Parcial", scope=[StatusScope.CLIENT_USE_CASE], category=StatusCategory.PARTIAL
        )
        self.not_applicable_status = Status.objects.create(
            name="Não Aplicável", scope=[StatusScope.CLIENT_USE_CASE], category=StatusCategory.NOT_APPLICABLE
        )

    def _use_case(self, code):
        return UseCase.objects.create(code=code, name=code)

    def test_not_applicable_is_excluded_from_denominator(self):
        ClientUseCase.objects.create(
            client=self.client_obj, use_case=self._use_case("UC-001"), status=self.covered_status
        )
        ClientUseCase.objects.create(
            client=self.client_obj, use_case=self._use_case("UC-002"), status=self.not_applicable_status
        )
        result = compute_use_case_coverage(self.client_obj)
        self.assertEqual(result["applicable"], 1)
        self.assertEqual(result["covered"], 1)
        self.assertEqual(result["percentage"], 100)

    def test_partial_counts_as_applicable_but_not_covered(self):
        ClientUseCase.objects.create(
            client=self.client_obj, use_case=self._use_case("UC-001"), status=self.covered_status
        )
        ClientUseCase.objects.create(
            client=self.client_obj, use_case=self._use_case("UC-002"), status=self.partial_status
        )
        result = compute_use_case_coverage(self.client_obj)
        self.assertEqual(result["applicable"], 2)
        self.assertEqual(result["covered"], 1)
        self.assertEqual(result["percentage"], 50)

    def test_no_applicable_use_cases_returns_no_percentage(self):
        result = compute_use_case_coverage(self.client_obj)
        self.assertEqual(result["applicable"], 0)
        self.assertIsNone(result["percentage"])

    def test_use_case_without_status_does_not_count_as_applicable(self):
        ClientUseCase.objects.create(client=self.client_obj, use_case=self._use_case("UC-001"))
        result = compute_use_case_coverage(self.client_obj)
        self.assertEqual(result["applicable"], 0)


class ImplementationTemplateTests(TestCase):
    def setUp(self):
        self.client_obj = Client.objects.create(name="Acme Corp")
        self.template = ImplementationTemplate.objects.create(name="Windows Server")
        self.log_source = LogSource.objects.create(name="Windows Security")
        self.use_case = UseCase.objects.create(code="UC-001", name="Brute Force")
        self.severity = None
        TemplateLogSource.objects.create(template=self.template, log_source=self.log_source)
        TemplateUseCase.objects.create(template=self.template, use_case=self.use_case)

    def test_applying_template_creates_client_links(self):
        result = apply_template_to_client(self.template, self.client_obj)
        self.assertEqual(result["log_sources"], 1)
        self.assertEqual(result["use_cases"], 1)
        self.assertTrue(
            ClientLogSource.objects.filter(client=self.client_obj, log_source=self.log_source).exists()
        )
        self.assertTrue(
            ClientUseCase.objects.filter(client=self.client_obj, use_case=self.use_case).exists()
        )

    def test_applying_template_twice_does_not_duplicate(self):
        apply_template_to_client(self.template, self.client_obj)
        result = apply_template_to_client(self.template, self.client_obj)
        self.assertEqual(result["log_sources"], 0)
        self.assertEqual(result["use_cases"], 0)
        self.assertEqual(ClientLogSource.objects.filter(client=self.client_obj).count(), 1)
        self.assertEqual(ClientUseCase.objects.filter(client=self.client_obj).count(), 1)

    def test_applying_template_does_not_overwrite_existing_manual_link(self):
        existing = ClientLogSource.objects.create(
            client=self.client_obj, log_source=self.log_source, notes="preenchido manualmente"
        )
        apply_template_to_client(self.template, self.client_obj)
        existing.refresh_from_db()
        self.assertEqual(existing.notes, "preenchido manualmente")


class TemplatePermissionTests(TestCase):
    def setUp(self):
        call_command("setup_roles")
        self.client_obj = Client.objects.create(name="Acme Corp")
        self.template = ImplementationTemplate.objects.create(name="Windows Server")

    def test_viewer_cannot_apply_template(self):
        user = User.objects.create_user("viewer3", password="x")
        user.groups.add(Group.objects.get(name="VIEWER"))
        self.client.force_login(user)
        response = self.client.post(
            reverse("catalog:apply_template", kwargs={"client_pk": self.client_obj.pk}),
            {"template": self.template.pk},
        )
        self.assertEqual(response.status_code, 403)

    def test_soc_manager_can_apply_template(self):
        user = User.objects.create_user("manager2", password="x")
        user.groups.add(Group.objects.get(name="SOC_MANAGER"))
        self.client.force_login(user)
        response = self.client.post(
            reverse("catalog:apply_template", kwargs={"client_pk": self.client_obj.pk}),
            {"template": self.template.pk},
        )
        self.assertEqual(response.status_code, 302)
