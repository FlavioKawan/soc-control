from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse


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
