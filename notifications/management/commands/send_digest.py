"""
Sends an e-mail digest of rule reviews that are overdue and gaps that
haven't moved in a while - today those only show up as a badge somebody has
to notice by opening the system. Meant to run on a schedule (host crontab or
any external scheduler calling `docker compose exec web python manage.py
send_digest`) - no in-app scheduler/worker, same principle the rest of the
project follows ("sem Celery/Redis a menos que uma necessidade real
apareça").
"""

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.core.management.base import BaseCommand

from notifications.services import build_digest


class Command(BaseCommand):
    help = "E-mails ADMIN/SOC_MANAGER users a digest of overdue rule reviews and stale gaps."

    def handle(self, *args, **options):
        body = build_digest(settings.SITE_URL)
        if not body:
            self.stdout.write("Nada para notificar - nenhuma revisão vencida ou gap parado.")
            return

        recipients = list(
            get_user_model()
            .objects.filter(groups__name__in=["ADMIN", "SOC_MANAGER"], is_active=True)
            .exclude(email="")
            .values_list("email", flat=True)
            .distinct()
        )
        if not recipients:
            self.stdout.write(
                self.style.WARNING(
                    "Nenhum usuário ADMIN/SOC_MANAGER com e-mail cadastrado - nada enviado."
                )
            )
            return

        send_mail(
            subject="SOC Control - pendências de revisão e gaps parados",
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=recipients,
        )
        self.stdout.write(self.style.SUCCESS(f"Digest enviado para {len(recipients)} destinatário(s)."))
