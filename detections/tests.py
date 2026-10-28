import datetime
import io

from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from catalog.models import ClientLogSource, ClientUseCase, LogSource, UseCase
from clients.models import Client
from taxonomy.choices import StatusCategory, StatusScope
from taxonomy.models import Framework, FrameworkControl, Severity, Status, Technology

from .forms import RuleForm
from .models import DEFAULT_RULE_COLUMNS, Rule, RuleColumnPreference
from .services import (
    import_rules_from_csv,
    rule_is_possibly_inoperative,
    rule_is_review_overdue,
    use_case_coverage_inconsistencies,
)


class RuleModelTests(TestCase):
    def setUp(self):
        self.client_obj = Client.objects.create(name="Acme Corp")
        self.technology = Technology.objects.create(name="Wazuh")

    def test_internal_id_is_globally_unique(self):
        Rule.objects.create(internal_id="SOC-WIN-001", name="Brute Force", client=self.client_obj, technology=self.technology)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Rule.objects.create(internal_id="SOC-WIN-001", name="Dup", client=self.client_obj, technology=self.technology)

    def test_rule_can_relate_to_multiple_use_cases(self):
        rule = Rule.objects.create(internal_id="SOC-WIN-001", name="Brute Force", client=self.client_obj, technology=self.technology)
        uc1 = UseCase.objects.create(code="UC-001", name="Brute Force")
        uc2 = UseCase.objects.create(code="UC-007", name="Password Spraying")
        rule.use_cases.set([uc1, uc2])
        self.assertEqual(rule.use_cases.count(), 2)


class RuleFormScopeTests(TestCase):
    def test_status_field_only_offers_rule_scoped_statuses(self):
        rule_status = Status.objects.create(name="Ativa", scope=[StatusScope.RULE])
        Status.objects.create(name="Coberto", scope=[StatusScope.CLIENT_USE_CASE])
        form = RuleForm()
        self.assertIn(rule_status, form.fields["status"].queryset)
        self.assertEqual(form.fields["status"].queryset.count(), 1)


class ReviewOverdueTests(TestCase):
    def setUp(self):
        self.client_obj = Client.objects.create(name="Acme Corp")
        self.technology = Technology.objects.create(name="Wazuh")

    def _rule(self, next_review_at):
        return Rule.objects.create(
            internal_id="SOC-WIN-001", name="Brute Force", client=self.client_obj,
            technology=self.technology, next_review_at=next_review_at,
        )

    def test_past_date_is_overdue(self):
        rule = self._rule(timezone.localdate() - datetime.timedelta(days=1))
        self.assertTrue(rule_is_review_overdue(rule))

    def test_future_date_is_not_overdue(self):
        rule = self._rule(timezone.localdate() + datetime.timedelta(days=1))
        self.assertFalse(rule_is_review_overdue(rule))

    def test_no_date_is_not_overdue(self):
        rule = self._rule(None)
        self.assertFalse(rule_is_review_overdue(rule))


class PossiblyInoperativeTests(TestCase):
    def setUp(self):
        self.client_obj = Client.objects.create(name="Acme Corp")
        self.technology = Technology.objects.create(name="Wazuh")
        self.log_source = LogSource.objects.create(name="Windows Security")
        self.active_status = Status.objects.create(name="Ativa", scope=[StatusScope.RULE], category=StatusCategory.ACTIVE)
        self.testing_status = Status.objects.create(name="Em Teste", scope=[StatusScope.RULE], category=StatusCategory.TESTING)

    def _rule(self, status, log_source=None):
        return Rule.objects.create(
            internal_id="SOC-WIN-001", name="Brute Force", client=self.client_obj,
            technology=self.technology, status=status, log_source=log_source,
        )

    def test_inactive_rule_is_never_flagged(self):
        rule = self._rule(self.testing_status, self.log_source)
        self.assertFalse(rule_is_possibly_inoperative(rule))

    def test_active_rule_without_log_source_is_not_flagged(self):
        rule = self._rule(self.active_status, log_source=None)
        self.assertFalse(rule_is_possibly_inoperative(rule))

    def test_active_rule_with_no_client_log_source_link_is_flagged(self):
        rule = self._rule(self.active_status, self.log_source)
        self.assertTrue(rule_is_possibly_inoperative(rule))

    def test_active_rule_with_not_receiving_link_is_flagged(self):
        not_receiving = Status.objects.create(
            name="Sem Log", scope=[StatusScope.CLIENT_LOG_SOURCE], category=StatusCategory.NOT_RECEIVING
        )
        ClientLogSource.objects.create(client=self.client_obj, log_source=self.log_source, status=not_receiving)
        rule = self._rule(self.active_status, self.log_source)
        self.assertTrue(rule_is_possibly_inoperative(rule))

    def test_active_rule_with_receiving_link_is_not_flagged(self):
        receiving = Status.objects.create(
            name="Recebendo", scope=[StatusScope.CLIENT_LOG_SOURCE], category=StatusCategory.RECEIVING
        )
        ClientLogSource.objects.create(client=self.client_obj, log_source=self.log_source, status=receiving)
        rule = self._rule(self.active_status, self.log_source)
        self.assertFalse(rule_is_possibly_inoperative(rule))

    def test_link_without_status_classified_yet_is_not_flagged(self):
        ClientLogSource.objects.create(client=self.client_obj, log_source=self.log_source, status=None)
        rule = self._rule(self.active_status, self.log_source)
        self.assertFalse(rule_is_possibly_inoperative(rule))


class CoverageInconsistencyTests(TestCase):
    def setUp(self):
        self.client_obj = Client.objects.create(name="Acme Corp")
        self.technology = Technology.objects.create(name="Wazuh")
        self.use_case = UseCase.objects.create(code="UC-001", name="Brute Force")
        self.covered_status = Status.objects.create(
            name="Coberto", scope=[StatusScope.CLIENT_USE_CASE], category=StatusCategory.COVERED
        )
        self.active_rule_status = Status.objects.create(
            name="Ativa", scope=[StatusScope.RULE], category=StatusCategory.ACTIVE
        )

    def test_covered_without_any_active_rule_is_inconsistent(self):
        ClientUseCase.objects.create(client=self.client_obj, use_case=self.use_case, status=self.covered_status)
        results = use_case_coverage_inconsistencies(self.client_obj)
        self.assertEqual(len(results), 1)

    def test_covered_with_active_rule_is_not_inconsistent(self):
        ClientUseCase.objects.create(client=self.client_obj, use_case=self.use_case, status=self.covered_status)
        rule = Rule.objects.create(
            internal_id="SOC-WIN-001", name="Brute Force", client=self.client_obj,
            technology=self.technology, status=self.active_rule_status,
        )
        rule.use_cases.add(self.use_case)
        results = use_case_coverage_inconsistencies(self.client_obj)
        self.assertEqual(len(results), 0)

    def test_not_covered_is_never_inconsistent(self):
        not_covered = Status.objects.create(
            name="Não Coberto", scope=[StatusScope.CLIENT_USE_CASE], category=StatusCategory.NOT_COVERED
        )
        ClientUseCase.objects.create(client=self.client_obj, use_case=self.use_case, status=not_covered)
        self.assertEqual(len(use_case_coverage_inconsistencies(self.client_obj)), 0)


class CsvImportTests(TestCase):
    def setUp(self):
        self.client_obj = Client.objects.create(name="Acme Corp")
        self.technology = Technology.objects.create(name="Wazuh")

    def _csv(self, text):
        return io.BytesIO(text.encode("utf-8"))

    def test_valid_row_creates_rule(self):
        csv_text = "rule_id,name,client,technology\nSOC-WIN-001,Brute Force,Acme Corp,Wazuh\n"
        report = import_rules_from_csv(self._csv(csv_text))
        self.assertEqual(report["created"], 1)
        self.assertEqual(report["errors"], [])
        self.assertTrue(Rule.objects.filter(internal_id="SOC-WIN-001").exists())

    def test_missing_required_header_is_reported_as_error(self):
        csv_text = "rule_id,name\nSOC-WIN-001,Brute Force\n"
        report = import_rules_from_csv(self._csv(csv_text))
        self.assertEqual(report["created"], 0)
        self.assertTrue(report["errors"])

    def test_unknown_client_is_reported_as_error_and_skipped(self):
        csv_text = "rule_id,name,client,technology\nSOC-WIN-001,Brute Force,Nao Existe,Wazuh\n"
        report = import_rules_from_csv(self._csv(csv_text))
        self.assertEqual(report["created"], 0)
        self.assertEqual(len(report["errors"]), 1)
        self.assertFalse(Rule.objects.exists())

    def test_unknown_optional_severity_is_a_warning_not_an_error(self):
        csv_text = "rule_id,name,client,technology,severity\nSOC-WIN-001,Brute Force,Acme Corp,Wazuh,Inexistente\n"
        report = import_rules_from_csv(self._csv(csv_text))
        self.assertEqual(report["created"], 1)
        self.assertEqual(report["errors"], [])
        self.assertTrue(report["warnings"])

    def test_same_rule_id_twice_updates_instead_of_duplicating(self):
        csv_text = "rule_id,name,client,technology\nSOC-WIN-001,Brute Force,Acme Corp,Wazuh\n"
        import_rules_from_csv(self._csv(csv_text))
        csv_text_updated = "rule_id,name,client,technology\nSOC-WIN-001,Brute Force v2,Acme Corp,Wazuh\n"
        report = import_rules_from_csv(self._csv(csv_text_updated))
        self.assertEqual(report["created"], 0)
        self.assertEqual(report["updated"], 1)
        self.assertEqual(Rule.objects.count(), 1)
        self.assertEqual(Rule.objects.get().name, "Brute Force v2")

    def test_one_bad_row_does_not_abort_the_rest_of_the_file(self):
        csv_text = (
            "rule_id,name,client,technology\n"
            "SOC-WIN-001,Brute Force,Nao Existe,Wazuh\n"
            "SOC-WIN-002,Password Spray,Acme Corp,Wazuh\n"
        )
        report = import_rules_from_csv(self._csv(csv_text))
        self.assertEqual(report["created"], 1)
        self.assertEqual(len(report["errors"]), 1)
        self.assertTrue(Rule.objects.filter(internal_id="SOC-WIN-002").exists())

    def test_oversized_file_is_capped_instead_of_processed_in_full(self):
        """
        Found by pentesting: nothing stopped a single upload from running
        tens of thousands of individual row lookups in one request,
        tying up a worker. MAX_CSV_ROWS stops it early with a clear error.
        """
        from .services import MAX_CSV_ROWS

        header = "rule_id,name,client,technology\n"
        rows = "".join(f"SOC-{i},Rule {i},Acme Corp,Wazuh\n" for i in range(MAX_CSV_ROWS + 50))
        report = import_rules_from_csv(self._csv(header + rows))
        self.assertEqual(report["created"], MAX_CSV_ROWS)
        self.assertTrue(any("mais de" in e["message"] for e in report["errors"]))


class ColumnPreferenceTests(TestCase):
    def setUp(self):
        call_command("setup_roles")
        self.user = User.objects.create_user("analyst1", password="x")
        self.user.groups.add(Group.objects.get(name="SOC_MANAGER"))
        self.client.force_login(self.user)

    def test_no_preference_saved_falls_back_to_default_columns(self):
        response = self.client.get(reverse("detections:rule_list"))
        self.assertEqual(response.context["visible_columns"], DEFAULT_RULE_COLUMNS)

    def test_saving_preference_persists_for_the_user(self):
        self.client.post(reverse("detections:rule_columns"), {"columns": ["internal_id", "status"]})
        pref = RuleColumnPreference.objects.get(user=self.user)
        self.assertEqual(pref.visible_columns, ["internal_id", "status"])

    def test_empty_selection_falls_back_to_default(self):
        self.client.post(reverse("detections:rule_columns"), {"columns": []})
        pref = RuleColumnPreference.objects.get(user=self.user)
        self.assertEqual(pref.visible_columns, DEFAULT_RULE_COLUMNS)


class RulePermissionTests(TestCase):
    def setUp(self):
        call_command("setup_roles")
        self.client_obj = Client.objects.create(name="Acme Corp")
        self.technology = Technology.objects.create(name="Wazuh")
        self.rule = Rule.objects.create(
            internal_id="SOC-WIN-001", name="Brute Force", client=self.client_obj, technology=self.technology
        )

    def test_soc_manager_has_full_crud(self):
        user = User.objects.create_user("manager", password="x")
        user.groups.add(Group.objects.get(name="SOC_MANAGER"))
        for perm in ["view_rule", "add_rule", "change_rule", "delete_rule"]:
            self.assertTrue(user.has_perm(f"detections.{perm}"))

    def test_analyst_cannot_delete(self):
        user = User.objects.create_user("analyst", password="x")
        user.groups.add(Group.objects.get(name="ANALYST"))
        self.assertTrue(user.has_perm("detections.add_rule"))
        self.assertFalse(user.has_perm("detections.delete_rule"))

    def test_viewer_cannot_import(self):
        user = User.objects.create_user("viewer", password="x")
        user.groups.add(Group.objects.get(name="VIEWER"))
        self.client.force_login(user)
        response = self.client.get(reverse("detections:rule_import"))
        self.assertEqual(response.status_code, 403)

    def test_anonymous_redirected_to_login(self):
        response = self.client.get(reverse("detections:rule_list"))
        self.assertEqual(response.status_code, 302)


class RuleFilterTests(TestCase):
    def setUp(self):
        call_command("setup_roles")
        self.user = User.objects.create_superuser("admin3", "admin3@example.com", "x")
        self.client.force_login(self.user)
        self.client_a = Client.objects.create(name="Acme Corp")
        self.client_b = Client.objects.create(name="Globex")
        self.technology = Technology.objects.create(name="Wazuh")
        self.rule_a = Rule.objects.create(
            internal_id="SOC-WIN-001", name="Brute Force", client=self.client_a, technology=self.technology
        )
        self.rule_b = Rule.objects.create(
            internal_id="SOC-WIN-002", name="Password Spray", client=self.client_b, technology=self.technology
        )

    def test_filter_by_client(self):
        response = self.client.get(reverse("detections:rule_list"), {"client": self.client_a.pk})
        rules = list(response.context["rules"])
        self.assertEqual(rules, [self.rule_a])

    def test_text_search_matches_name(self):
        response = self.client.get(reverse("detections:rule_list"), {"q": "Password"})
        rules = list(response.context["rules"])
        self.assertEqual(rules, [self.rule_b])

    def test_review_overdue_filter(self):
        self.rule_a.next_review_at = timezone.localdate() - datetime.timedelta(days=1)
        self.rule_a.save()
        response = self.client.get(reverse("detections:rule_list"), {"review_status": "overdue"})
        rules = list(response.context["rules"])
        self.assertEqual(rules, [self.rule_a])


class StageFilterTests(TestCase):
    """?stage=<FrameworkControl id> (Dashboard's layer widget) must match
    a rule tagged on the control itself, or on any descendant (e.g. a rule
    tagged with a MITRE ATT&CK technique when ?stage= is its tactic)."""

    def setUp(self):
        self.user = User.objects.create_superuser("admin10", "admin10@example.com", "x")
        self.client.force_login(self.user)
        self.client_obj = Client.objects.create(name="Acme Corp")
        self.technology = Technology.objects.create(name="Wazuh")
        self.framework = Framework.objects.create(name="MITRE ATT&CK")

    def _rule(self, internal_id):
        return Rule.objects.create(
            internal_id=internal_id, name=internal_id, client=self.client_obj, technology=self.technology
        )

    def test_stage_matches_rules_tagged_on_the_control_itself(self):
        stage = FrameworkControl.objects.create(framework=self.framework, code="KC1", name="Reconhecimento")
        rule = self._rule("SOC-001")
        rule.framework_controls.add(stage)

        response = self.client.get(reverse("detections:rule_list"), {"stage": stage.pk})
        self.assertEqual(list(response.context["rules"]), [rule])

    def test_stage_matches_rules_tagged_on_a_descendant_control(self):
        tactic = FrameworkControl.objects.create(framework=self.framework, code="TA06", name="Credential Access")
        technique = FrameworkControl.objects.create(
            framework=self.framework, code="T1110", name="Brute Force", parent=tactic
        )
        rule = self._rule("SOC-001")
        rule.framework_controls.add(technique)

        response = self.client.get(reverse("detections:rule_list"), {"stage": tactic.pk})
        self.assertEqual(list(response.context["rules"]), [rule])

    def test_unknown_stage_id_returns_no_rules_instead_of_everything(self):
        self._rule("SOC-001")
        response = self.client.get(reverse("detections:rule_list"), {"stage": 999999})
        self.assertEqual(list(response.context["rules"]), [])


class MalformedQueryParamTests(TestCase):
    """
    A crafted/garbage value in a pk-lookup querystring param must never
    produce an unhandled 500 - found by pentesting ?stage=abc.
    """

    def setUp(self):
        self.user = User.objects.create_superuser("admin9", "admin9@example.com", "x")
        self.client.force_login(self.user)

    def test_non_numeric_stage_does_not_crash(self):
        response = self.client.get(reverse("detections:rule_list"), {"stage": "abc"})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("active_stage", response.context or {})

    def test_non_numeric_stage_in_detail_lookup_does_not_crash(self):
        response = self.client.get(reverse("detections:rule_list"), {"stage": "'; DROP TABLE x; --"})
        self.assertEqual(response.status_code, 200)


class OpenRedirectTests(TestCase):
    """The ?next= on the column-preference POST must only honor a safe,
    same-host relative URL - found by pentesting next=https://evil.example."""

    def setUp(self):
        self.user = User.objects.create_superuser("admin10", "admin10@example.com", "x")
        self.client.force_login(self.user)

    def test_external_next_url_is_ignored(self):
        response = self.client.post(
            reverse("detections:rule_columns"),
            {"columns": ["internal_id"], "next": "https://evil.example/phish"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("detections:rule_list"))

    def test_relative_next_url_is_honored(self):
        response = self.client.post(
            reverse("detections:rule_columns"),
            {"columns": ["internal_id"], "next": "/regras/?client=1"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/regras/?client=1")

    def test_protocol_relative_next_url_is_rejected(self):
        """//evil.example looks relative but browsers treat it as absolute."""
        response = self.client.post(
            reverse("detections:rule_columns"),
            {"columns": ["internal_id"], "next": "//evil.example/phish"},
        )
        self.assertEqual(response["Location"], reverse("detections:rule_list"))
