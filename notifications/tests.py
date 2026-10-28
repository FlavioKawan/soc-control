from datetime import timedelta

from django.contrib.auth.models import Group, User
from django.core import mail
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from clients.models import Client
from detections.models import Rule
from gaps.models import Gap
from taxonomy.choices import StatusCategory, StatusScope
from taxonomy.models import Status, Technology

from .services import STALE_GAP_DAYS, build_digest, overdue_rules, stale_gaps


class OverdueRulesTests(TestCase):
    def setUp(self):
        self.client_obj = Client.objects.create(name="Acme Corp")
        self.technology = Technology.objects.create(name="Wazuh")

    def test_rule_with_past_review_date_is_overdue(self):
        rule = Rule.objects.create(
            internal_id="SOC-001", name="Brute Force", client=self.client_obj, technology=self.technology,
            next_review_at=timezone.localdate() - timedelta(days=1),
        )
        self.assertIn(rule, overdue_rules())

    def test_rule_with_future_review_date_is_not_overdue(self):
        rule = Rule.objects.create(
            internal_id="SOC-002", name="Port Scan", client=self.client_obj, technology=self.technology,
            next_review_at=timezone.localdate() + timedelta(days=1),
        )
        self.assertNotIn(rule, overdue_rules())

    def test_rule_without_review_date_is_not_overdue(self):
        rule = Rule.objects.create(
            internal_id="SOC-003", name="No Date", client=self.client_obj, technology=self.technology,
        )
        self.assertNotIn(rule, overdue_rules())


class StaleGapsTests(TestCase):
    def setUp(self):
        self.client_obj = Client.objects.create(name="Acme Corp")

    def test_open_gap_untouched_past_threshold_is_stale(self):
        gap = Gap.objects.create(code="GAP-001", client=self.client_obj, title="DNS logs ausentes")
        # updated_at has auto_now=True, so it must be set via a queryset
        # update() - a normal .save() would just stamp it back to "now".
        Gap.objects.filter(pk=gap.pk).update(updated_at=timezone.now() - timedelta(days=STALE_GAP_DAYS + 1))
        self.assertIn(gap, stale_gaps())

    def test_recently_touched_open_gap_is_not_stale(self):
        gap = Gap.objects.create(code="GAP-002", client=self.client_obj, title="Gap recente")
        self.assertNotIn(gap, stale_gaps())

    def test_closed_gap_is_never_stale_even_if_old(self):
        closed = Status.objects.create(name="Concluído", scope=[StatusScope.GAP], category=StatusCategory.CLOSED)
        gap = Gap.objects.create(
            code="GAP-003", client=self.client_obj, title="Gap antigo fechado", status=closed
        )
        Gap.objects.filter(pk=gap.pk).update(updated_at=timezone.now() - timedelta(days=STALE_GAP_DAYS + 10))
        self.assertNotIn(gap, stale_gaps())


class BuildDigestTests(TestCase):
    def test_returns_none_when_nothing_to_report(self):
        self.assertIsNone(build_digest("http://localhost:8088"))

    def test_includes_overdue_rule_in_body(self):
        client_obj = Client.objects.create(name="Acme Corp")
        technology = Technology.objects.create(name="Wazuh")
        Rule.objects.create(
            internal_id="SOC-001", name="Brute Force", client=client_obj, technology=technology,
            next_review_at=timezone.localdate() - timedelta(days=1),
        )
        body = build_digest("http://localhost:8088")
        self.assertIn("SOC-001", body)
        self.assertIn("http://localhost:8088/regras/", body)


class SendDigestCommandTests(TestCase):
    def setUp(self):
        call_command("setup_roles")
        self.client_obj = Client.objects.create(name="Acme Corp")
        self.technology = Technology.objects.create(name="Wazuh")

    def test_no_pending_items_sends_no_email(self):
        call_command("send_digest")
        self.assertEqual(len(mail.outbox), 0)

    def test_sends_email_to_admin_and_manager_with_email_set(self):
        Rule.objects.create(
            internal_id="SOC-001", name="Brute Force", client=self.client_obj, technology=self.technology,
            next_review_at=timezone.localdate() - timedelta(days=1),
        )
        admin = User.objects.create_user("admin", email="admin@example.com", password="x")
        admin.groups.add(Group.objects.get(name="ADMIN"))
        manager_no_email = User.objects.create_user("manager", password="x")
        manager_no_email.groups.add(Group.objects.get(name="SOC_MANAGER"))
        analyst = User.objects.create_user("analyst", email="analyst@example.com", password="x")
        analyst.groups.add(Group.objects.get(name="ANALYST"))

        call_command("send_digest")

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["admin@example.com"])
        self.assertIn("SOC-001", mail.outbox[0].body)
