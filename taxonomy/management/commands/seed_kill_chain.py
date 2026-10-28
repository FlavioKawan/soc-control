"""
Seeds the Cyber Kill Chain (Lockheed Martin) as a Framework, exactly like
MITRE ATT&CK would be seeded by hand - this is reference content, not a
hardcoded business rule. Safe to re-run (get_or_create per stage).

Tag a Rule with one of these stages the same way you'd tag it with a MITRE
technique: via the "Técnicas/Controles" field on the Rule form.
"""

from django.core.management.base import BaseCommand

from taxonomy.models import Framework, FrameworkControl

STAGES = [
    ("KC1", "Reconhecimento", "Coleta de informações sobre o alvo antes do ataque (OSINT, varreduras, enumeração)."),
    ("KC2", "Armamento", "Preparação do artefato malicioso (exploit + payload empacotados)."),
    ("KC3", "Entrega", "Transmissão do artefato ao alvo (phishing, mídia removível, download, etc.)."),
    ("KC4", "Exploração", "Execução do código malicioso ao explorar uma vulnerabilidade ou o usuário."),
    ("KC5", "Instalação", "Persistência do atacante no ambiente (backdoor, serviço, agendamento)."),
    ("KC6", "Comando e Controle", "Canal de comunicação entre o atacante e o host comprometido (C2)."),
    ("KC7", "Ações sobre o Objetivo", "Objetivo final do atacante: exfiltração, destruição, ransomware, etc."),
]


class Command(BaseCommand):
    help = "Creates the Cyber Kill Chain framework and its 7 stages, if they don't already exist."

    def handle(self, *args, **options):
        framework, _ = Framework.objects.get_or_create(
            name="Cyber Kill Chain",
            defaults={
                "description": "Modelo de 7 fases (Lockheed Martin) do ciclo de um ataque, "
                                "usado para mapear em qual etapa cada regra atua.",
            },
        )
        for code, name, description in STAGES:
            FrameworkControl.objects.get_or_create(
                framework=framework,
                code=code,
                defaults={"name": name, "description": description},
            )
        self.stdout.write(self.style.SUCCESS("Cyber Kill Chain (7 etapas) pronta em Frameworks."))
