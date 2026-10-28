from django.contrib.auth.models import User
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
