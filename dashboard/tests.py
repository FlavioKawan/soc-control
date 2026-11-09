from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from clients.models import Client
from detections.models import Rule
from taxonomy.models import Framework, FrameworkControl, Technology

from .services import build_dashboard


class LayerWidgetsTests(TestCase):
    """build_dashboard()'s "layer_widgets" backs the Dashboard's Kill
    Chain/MITRE ATT&CK tabs - one entry per name in
    taxonomy.services.LAYER_FRAMEWORK_NAMES, always in that order."""

    def setUp(self):
        self.client_obj = Client.objects.create(name="Acme Corp")
        self.technology = Technology.objects.create(name="Wazuh")

    def _rule(self, internal_id, **kwargs):
        return Rule.objects.create(
            internal_id=internal_id, name=internal_id, client=self.client_obj,
            technology=self.technology, **kwargs,
        )

    def test_widgets_follow_the_fixed_order_regardless_of_creation_order(self):
        Framework.objects.create(name="MITRE ATT&CK")
        Framework.objects.create(name="Cyber Kill Chain")

        widgets = build_dashboard()["layer_widgets"]
        self.assertEqual([w["key"] for w in widgets], ["kill_chain", "mitre_attack"])

    def test_widget_has_no_layers_when_its_framework_does_not_exist(self):
        widgets = build_dashboard()["layer_widgets"]
        self.assertIsNone(widgets[0]["layers"])
        self.assertTrue(widgets[0]["seed_hint"])

    def test_widget_counts_rules_tagged_on_a_descendant_control(self):
        framework = Framework.objects.create(name="MITRE ATT&CK")
        tactic = FrameworkControl.objects.create(framework=framework, code="TA06", name="Credential Access")
        technique = FrameworkControl.objects.create(
            framework=framework, code="T1110", name="Brute Force", parent=tactic
        )
        self._rule("SOC-001").framework_controls.add(technique)

        [layer] = next(w for w in build_dashboard()["layer_widgets"] if w["key"] == "mitre_attack")["layers"]
        self.assertEqual(layer["count"], 1)

    def test_widget_respects_the_client_filter(self):
        framework = Framework.objects.create(name="Cyber Kill Chain")
        stage = FrameworkControl.objects.create(framework=framework, code="KC1", name="Reconhecimento")
        self._rule("SOC-001").framework_controls.add(stage)
        other_client = Client.objects.create(name="Globex")
        Rule.objects.create(
            internal_id="X-1", name="X", client=other_client, technology=self.technology
        ).framework_controls.add(stage)

        [layer] = next(w for w in build_dashboard(client=other_client)["layer_widgets"] if w["key"] == "kill_chain")["layers"]
        self.assertEqual(layer["count"], 1)


class LayerMaturityTests(TestCase):
    """Combined Kill Chain + MITRE ATT&CK coverage, as one percentage -
    only meaningful in the "all clients" view (comparing a single client
    against itself would be redundant with its own layer tabs)."""

    def setUp(self):
        self.client_obj = Client.objects.create(name="Acme Corp")
        self.technology = Technology.objects.create(name="Wazuh")

    def _rule(self, internal_id, **kwargs):
        return Rule.objects.create(
            internal_id=internal_id, name=internal_id, client=self.client_obj,
            technology=self.technology, **kwargs,
        )

    def test_none_without_any_layer_framework(self):
        self.assertIsNone(build_dashboard()["layer_maturity"])

    def test_combines_both_frameworks_into_one_percentage(self):
        kill_chain = Framework.objects.create(name="Cyber Kill Chain")
        covered_stage = FrameworkControl.objects.create(framework=kill_chain, code="KC1", name="Reconhecimento")
        FrameworkControl.objects.create(framework=kill_chain, code="KC2", name="Entrega")
        mitre = Framework.objects.create(name="MITRE ATT&CK")
        FrameworkControl.objects.create(framework=mitre, code="TA06", name="Credential Access")
        self._rule("SOC-001").framework_controls.add(covered_stage)

        # 1 of 2 Kill Chain stages + 0 of 1 MITRE tactic = 1 of 3 layers.
        maturity = build_dashboard()["layer_maturity"]
        self.assertEqual((maturity["covered"], maturity["total"], maturity["percentage"]), (1, 3, 33))

    def test_hidden_when_a_specific_client_is_selected(self):
        Framework.objects.create(name="Cyber Kill Chain")
        self.assertIsNone(build_dashboard(client=self.client_obj)["layer_maturity"])


class ClientLayerRankingTests(TestCase):
    def setUp(self):
        self.technology = Technology.objects.create(name="Wazuh")
        self.framework = Framework.objects.create(name="Cyber Kill Chain")
        self.stage_a = FrameworkControl.objects.create(framework=self.framework, code="KC1", name="Reconhecimento")
        self.stage_b = FrameworkControl.objects.create(framework=self.framework, code="KC2", name="Entrega")

    def test_ranking_orders_clients_by_coverage_percentage(self):
        best = Client.objects.create(name="Acme (2/2)")
        worst = Client.objects.create(name="Globex (1/2)")
        Rule.objects.create(
            internal_id="A-1", name="A-1", client=best, technology=self.technology
        ).framework_controls.add(self.stage_a)
        Rule.objects.create(
            internal_id="A-2", name="A-2", client=best, technology=self.technology
        ).framework_controls.add(self.stage_b)
        Rule.objects.create(
            internal_id="B-1", name="B-1", client=worst, technology=self.technology
        ).framework_controls.add(self.stage_a)

        ranking = build_dashboard()["client_ranking"]
        self.assertEqual([row["client"] for row in ranking[:2]], [best, worst])
        self.assertEqual((ranking[0]["covered"], ranking[0]["percentage"]), (2, 100))
        self.assertEqual((ranking[1]["covered"], ranking[1]["percentage"]), (1, 50))

    def test_client_with_no_tagged_rules_scores_zero(self):
        Client.objects.create(name="Acme")
        ranking = build_dashboard()["client_ranking"]
        self.assertEqual(ranking[0]["percentage"], 0)

    def test_ranking_respects_the_technology_filter(self):
        client_obj = Client.objects.create(name="Acme")
        other_technology = Technology.objects.create(name="Splunk")
        Rule.objects.create(
            internal_id="A-1", name="A-1", client=client_obj, technology=other_technology
        ).framework_controls.add(self.stage_a)

        ranking = build_dashboard(technology=self.technology)["client_ranking"]
        self.assertEqual(ranking[0]["covered"], 0)

    def test_hidden_when_a_specific_client_is_selected(self):
        client_obj = Client.objects.create(name="Acme")
        self.assertIsNone(build_dashboard(client=client_obj)["client_ranking"])


class MalformedFilterParamTests(TestCase):
    """
    Pentest finding: ?client=abc and ?technology=abc crashed with an
    unhandled 500 (ValueError from the ORM trying to cast the pk).
    """

    def setUp(self):
        self.user = User.objects.create_superuser("admin11", "admin11@example.com", "x")
        self.client.force_login(self.user)

    def test_non_numeric_client_does_not_crash(self):
        response = self.client.get(reverse("dashboard"), {"client": "abc"})
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context["selected_client"])

    def test_non_numeric_technology_does_not_crash(self):
        response = self.client.get(reverse("dashboard"), {"technology": "abc"})
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context["selected_technology"])

    def test_sql_injection_payload_in_client_param_does_not_crash(self):
        response = self.client.get(reverse("dashboard"), {"client": "1; DROP TABLE clients_client;"})
        self.assertEqual(response.status_code, 200)


class ClientIsolationTests(TestCase):
    """
    Pentest finding (docs/05-operacao-e-testes.md §8): the Dashboard has no
    permission_required at all, so every logged-in ANALYST/VIEWER saw
    cards/charts/ranking aggregated over every client. build_dashboard's
    allowed_clients restricts those aggregates to the user's own clients.
    """

    def setUp(self):
        call_command("setup_roles")
        self.mine = Client.objects.create(name="Acme Corp")
        self.other = Client.objects.create(name="Globex")
        technology = Technology.objects.create(name="Wazuh")
        framework = Framework.objects.create(name="Cyber Kill Chain")
        stage = FrameworkControl.objects.create(framework=framework, code="KC1", name="Reconhecimento")
        rule_mine = Rule.objects.create(internal_id="SOC-001", name="Brute Force", client=self.mine, technology=technology)
        rule_mine.framework_controls.add(stage)
        rule_other = Rule.objects.create(internal_id="SOC-002", name="Brute Force", client=self.other, technology=technology)
        rule_other.framework_controls.add(stage)

        self.analyst = User.objects.create_user("analyst", password="x")
        self.analyst.groups.add(Group.objects.get(name="ANALYST"))
        self.mine.assigned_users.add(self.analyst)

    def test_build_dashboard_excludes_unassigned_clients_when_restricted(self):
        allowed = Client.objects.filter(pk=self.mine.pk)
        data = build_dashboard(allowed_clients=allowed)
        self.assertEqual(data["cards"]["total_rules"], 1)

    def test_build_dashboard_ranks_only_among_allowed_clients(self):
        allowed = Client.objects.filter(pk=self.mine.pk)
        ranking = build_dashboard(allowed_clients=allowed)["client_ranking"]
        self.assertEqual([row["client"] for row in ranking], [self.mine])

    def test_dashboard_view_scopes_client_dropdown_and_cards_for_an_analyst(self):
        self.client.force_login(self.analyst)
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(list(response.context["clients"]), [self.mine])
        self.assertEqual(response.context["cards"]["total_rules"], 1)
