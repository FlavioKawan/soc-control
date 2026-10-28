"""
Seeds the MITRE ATT&CK tactics (Enterprise matrix) as a Framework - the
other "fixed" layer widget alongside Cyber Kill Chain (see
seed_kill_chain.py; both are picked up by name via
taxonomy/services.py::LAYER_FRAMEWORK_NAMES).

Only the 14 tactics are seeded - stable, rarely-changing reference data,
same spirit as the Kill Chain's 7 stages. Techniques are *not* seeded
here on purpose: there are hundreds, they change release to release, and
this project already lets you add them by hand as controls nested under
a tactic (Frameworks > MITRE ATT&CK > Novo controle, campo "Pai").

`code` is a sequential TA01..TA14 label, not the official MITRE TA00xx
numbering - same reasoning as Kill Chain's KC1..KC7: FrameworkControl has
no separate "display order" field, so the code has to double as one, and
has to sort in attack-lifecycle order. The real MITRE id is kept in the
description for reference. Safe to re-run (get_or_create per tactic).
"""

from django.core.management.base import BaseCommand

from taxonomy.models import Framework, FrameworkControl

TACTICS = [
    ("TA01", "Reconnaissance", "Coleta de informações para planejar operações futuras (ATT&CK TA0043)."),
    ("TA02", "Resource Development", "Criação/aquisição de recursos para apoiar as operações (ATT&CK TA0042)."),
    ("TA03", "Initial Access", "Formas de obter o primeiro ponto de apoio na rede (ATT&CK TA0001)."),
    ("TA04", "Execution", "Execução de código controlado pelo atacante (ATT&CK TA0002)."),
    ("TA05", "Persistence", "Manutenção de acesso mesmo após reinícios ou troca de credenciais (ATT&CK TA0003)."),
    ("TA06", "Privilege Escalation", "Obtenção de permissões de nível mais alto (ATT&CK TA0004)."),
    ("TA07", "Defense Evasion", "Evitar ser detectado durante o ataque (ATT&CK TA0005)."),
    ("TA08", "Credential Access", "Roubo de credenciais: senhas, hashes, tokens (ATT&CK TA0006)."),
    ("TA09", "Discovery", "Reconhecimento do ambiente já comprometido (ATT&CK TA0007)."),
    ("TA10", "Lateral Movement", "Movimentação entre sistemas na rede (ATT&CK TA0008)."),
    ("TA11", "Collection", "Coleta de dados de interesse para o objetivo do atacante (ATT&CK TA0009)."),
    ("TA12", "Command and Control", "Comunicação com os sistemas comprometidos (ATT&CK TA0011)."),
    ("TA13", "Exfiltration", "Extração de dados do ambiente da vítima (ATT&CK TA0010)."),
    ("TA14", "Impact", "Manipulação, interrupção ou destruição de sistemas e dados (ATT&CK TA0040)."),
]


class Command(BaseCommand):
    help = "Creates the MITRE ATT&CK framework and its 14 tactics, if they don't already exist."

    def handle(self, *args, **options):
        framework, _ = Framework.objects.get_or_create(
            name="MITRE ATT&CK",
            defaults={
                "description": "Táticas (fases) do MITRE ATT&CK Enterprise - adicione as técnicas "
                                "específicas como controles-filho de cada tática (campo \"Pai\").",
                "url": "https://attack.mitre.org/",
            },
        )
        for code, name, description in TACTICS:
            FrameworkControl.objects.get_or_create(
                framework=framework,
                code=code,
                defaults={"name": name, "description": description},
            )
        self.stdout.write(self.style.SUCCESS("MITRE ATT&CK (14 táticas) pronto em Frameworks."))
