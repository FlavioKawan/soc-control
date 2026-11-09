import io
import math
from xml.sax.saxutils import escape

from django.template.loader import render_to_string
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from weasyprint import HTML

# Shared palette - matches the dashboard's chart/badge colors (dashboard/services.py
# FALLBACK_PALETTE and the coverage cards) so a client sees the same visual language
# in the app, the internal report below and the client-facing report's HTML template.
_COLOR_PRIMARY = "#4f46e5"
_COLOR_SUCCESS = "#22c55e"
_COLOR_WARNING = "#f59e0b"
_COLOR_DANGER = "#ef4444"
_COLOR_MUTED = "#6b7280"
_COLOR_MUTED_LIGHT = "#94a3b8"
_COLOR_BORDER = "#e3e5ec"
_COLOR_BG_LIGHT = "#f8f9fc"

_STYLES = getSampleStyleSheet()
# Keeps a section title on the same page as the table that follows it.
_STYLES["Heading2"].keepWithNext = True
_STYLES["Heading3"].keepWithNext = True
_CELL_STYLE = ParagraphStyle("cell", parent=_STYLES["Normal"], fontSize=8, leading=10)

_DONUT_RADIUS = 54
_DONUT_CIRCUMFERENCE = 2 * math.pi * _DONUT_RADIUS


def render_client_report_pdf(report):
    """Renders the dict from reports.services.build_client_report() as a PDF (bytes).

    The internal report: plain reportlab tables, no charts. Kept deliberately
    simple - it's read by the SOC itself, not handed to a client, so the visual
    investment went into render_client_facing_report_pdf() instead.
    """
    client = report["client"]
    coverage = report["coverage"]

    elements = [
        Paragraph(f"Relatório de Cobertura — {client.name}", _STYLES["Title"]),
        Paragraph(f"Gerado em {report['generated_at']:%d/%m/%Y %H:%M}", _STYLES["Normal"]),
        Spacer(1, 0.5 * cm),
    ]

    if coverage["applicable"]:
        coverage_text = (
            f"{coverage['percentage']}% ({coverage['covered']} de {coverage['applicable']} aplicáveis)"
        )
    else:
        coverage_text = "Sem casos de uso aplicáveis cadastrados"

    summary_rows = [
        ["Regras cadastradas", str(len(report["rules"]))],
        ["Regras ativas", str(report["active_rules_count"])],
        ["Gaps em aberto", f"{report['open_gaps_count']} de {len(report['gaps'])}"],
        ["Cobertura de casos de uso", coverage_text],
    ]
    elements.append(_kv_table(summary_rows))
    elements.append(Spacer(1, 0.6 * cm))

    elements.append(Paragraph("Regras", _STYLES["Heading2"]))
    if report["rules"]:
        rule_header = ["ID", "Nome", "Tecnologia", "Severidade", "Status"]
        rule_rows = [
            [
                rule.internal_id,
                _cell(rule.name),
                str(rule.technology),
                str(rule.severity) if rule.severity else "-",
                str(rule.status) if rule.status else "-",
            ]
            for rule in report["rules"]
        ]
        elements.append(
            _data_table(rule_header, rule_rows, col_widths=[2.3 * cm, 6.5 * cm, 3 * cm, 2.6 * cm, 2.6 * cm])
        )
    else:
        elements.append(Paragraph("Nenhuma regra cadastrada para este cliente.", _STYLES["Normal"]))
    elements.append(Spacer(1, 0.6 * cm))

    elements.append(Paragraph("Gaps", _STYLES["Heading2"]))
    if report["gaps"]:
        gap_header = ["Código", "Título", "Status", "Criticidade", "Aberto em"]
        gap_rows = [
            [
                gap.code,
                _cell(gap.title),
                str(gap.status) if gap.status else "-",
                str(gap.criticality) if gap.criticality else "-",
                gap.opened_at.strftime("%d/%m/%Y") if gap.opened_at else "-",
            ]
            for gap in report["gaps"]
        ]
        elements.append(
            _data_table(gap_header, gap_rows, col_widths=[2.3 * cm, 7 * cm, 2.6 * cm, 2.6 * cm, 2.5 * cm])
        )
    else:
        elements.append(Paragraph("Nenhum gap cadastrado para este cliente.", _STYLES["Normal"]))

    return _build_pdf(elements, title=f"Relatório - {client.name}")


def render_client_facing_report_pdf(report):
    """Renders the dict from reports.services.build_client_facing_report() as a PDF
    (bytes) via an HTML/CSS template (reports/templates/reports/client_facing_report.html)
    rendered through WeasyPrint - real charts (coverage donut, criticality bars),
    gradients and card layout that plain reportlab tables can't give us.

    The internal report (render_client_report_pdf above) stays on reportlab: nobody
    asked for that one's look to change, and it has no charts to justify the switch.
    """
    html = render_to_string("reports/client_facing_report.html", _client_facing_context(report))
    return HTML(string=html).write_pdf()


def _client_facing_context(report):
    coverage = report["coverage"]
    percentage = coverage["percentage"] if coverage["applicable"] else None
    pending_actions = len(report["client_gaps"]) + len(report["problem_log_sources"])

    stats = [
        {
            "value": f"{percentage}%" if percentage is not None else "-",
            "label": "Cobertura de casos de uso",
            "color": _coverage_color(percentage),
        },
        {
            "value": len(report["active_rules"]),
            "label": "Detecções ativas",
            "color": _COLOR_PRIMARY,
        },
        {
            "value": f"{report['log_sources_receiving']}/{report['log_sources_total']}",
            "label": "Fontes de log recebendo dados",
            "color": _ratio_color(report["log_sources_receiving"], report["log_sources_total"]),
        },
        {
            "value": report["open_gaps_count"],
            "label": "Pendências em aberto",
            "color": _zero_is_good_color(report["open_gaps_count"]),
        },
        {
            "value": pending_actions,
            "label": "Ações pendentes do seu lado",
            "color": _zero_is_good_color(pending_actions),
        },
    ]

    return {
        "client": report["client"],
        "report": report,
        "donut": _donut_chart(percentage),
        "stats": stats,
        "narrative": _narrative(report),
        "criticality_bars": _criticality_bars(report["open_gaps_by_criticality"]),
        "framework_bars": _framework_bars(report["frameworks"]),
        "severity_bars": _severity_bars(report["active_rules"]),
        "frameworks": _frameworks_context(report["frameworks"]),
    }


def _narrative(report):
    """One auto-written paragraph summarizing the report's own numbers, for the
    cover page - cheap "analyst read it for you" feel, deterministic from the
    same dict the rest of the report renders from (no extra queries)."""
    coverage = report["coverage"]
    sentences = []

    if coverage["applicable"]:
        sentences.append(
            f"Sua cobertura de casos de uso está em {coverage['percentage']}%, com "
            f"{coverage['covered']} de {coverage['applicable']} casos de uso aplicáveis cobertos."
        )
    else:
        sentences.append("Nenhum caso de uso aplicável está cadastrado para este ambiente ainda.")

    active_count = len(report["active_rules"])
    rule_noun = "detecção ativa" if active_count == 1 else "detecções ativas"
    sentences.append(f"O SOC mantém {active_count} {rule_noun} monitorando o ambiente.")

    layer_coverage = report["layer_coverage"]
    if layer_coverage:
        total_layers = sum(len(item["layers"]) for item in layer_coverage)
        covered_layers = sum(1 for item in layer_coverage for layer in item["layers"] if layer["covered"])
        sentences.append(
            f"Em relação às táticas de ataque conhecidas, você está protegido em {covered_layers} de "
            f"{total_layers} camadas (Cyber Kill Chain e MITRE ATT&CK)."
        )

    open_gaps = report["open_gaps_count"]
    if open_gaps:
        gap_noun = "pendência em aberto" if open_gaps == 1 else "pendências em aberto"
        crit_detail = ""
        if report["open_gaps_by_criticality"]:
            top_name, _ = report["open_gaps_by_criticality"][0]
            crit_detail = f', a maior parte classificada como "{top_name}"'
        sentences.append(f"Há {open_gaps} {gap_noun}{crit_detail}.")
    else:
        sentences.append("Não há pendências em aberto no momento.")

    pending_actions = len(report["client_gaps"]) + len(report["problem_log_sources"])
    if pending_actions:
        if pending_actions == 1:
            sentences.append("1 ação pendente depende do seu lado para avançar.")
        else:
            sentences.append(f"{pending_actions} ações pendentes dependem do seu lado para avançar.")

    return " ".join(sentences)


def _framework_bars(frameworks):
    """% of controls covered per framework - the same numbers as the detailed
    'Cobertura por framework' tables further down, rolled up into a one-line-per-
    framework bar chart for the cover page."""
    return [
        {
            "name": item["framework"].name,
            "count": item["covered_count"],
            "pct": round(item["covered_count"] / item["total"] * 100) if item["total"] else 0,
        }
        for item in frameworks
    ]


def _severity_bars(active_rules):
    """How many active rules fall under each SOC severity, ordered by the
    Severity catalog's own `weight` (taxonomy/02-modelo-de-dados.md §3.1) so
    "Crítica" always leads regardless of which has the most rules."""
    buckets = {}
    for rule in active_rules:
        severity = rule.severity
        key = severity.pk if severity else None
        if key not in buckets:
            buckets[key] = {
                "name": severity.name if severity else "Sem severidade",
                "color": severity.color if severity else _COLOR_MUTED_LIGHT,
                "weight": severity.weight if severity else -1,
                "count": 0,
            }
        buckets[key]["count"] += 1

    items = sorted(buckets.values(), key=lambda item: -item["weight"])
    max_count = max((item["count"] for item in items), default=0)
    for item in items:
        item["pct"] = round(item["count"] / max_count * 100) if max_count else 0
        del item["weight"]
    return items


def _donut_chart(percentage):
    if percentage is None:
        return {"percentage": None, "dasharray": f"0 {_DONUT_CIRCUMFERENCE:.1f}", "color": _COLOR_MUTED_LIGHT}
    filled = _DONUT_CIRCUMFERENCE * percentage / 100
    return {
        "percentage": percentage,
        "dasharray": f"{filled:.1f} {_DONUT_CIRCUMFERENCE:.1f}",
        "color": _coverage_color(percentage),
    }


def _coverage_color(percentage):
    if percentage is None:
        return _COLOR_MUTED_LIGHT
    if percentage >= 80:
        return _COLOR_SUCCESS
    if percentage >= 50:
        return _COLOR_WARNING
    return _COLOR_DANGER


def _ratio_color(numerator, denominator):
    if not denominator:
        return _COLOR_MUTED_LIGHT
    if numerator >= denominator:
        return _COLOR_SUCCESS
    if numerator == 0:
        return _COLOR_DANGER
    return _COLOR_WARNING


def _zero_is_good_color(count):
    return _COLOR_SUCCESS if count == 0 else _COLOR_DANGER


def _criticality_bars(pairs):
    """pairs: report['open_gaps_by_criticality'], e.g. [("Crítica", 3), ("Alta", 1)] -
    turns counts into bar widths (% of the largest one) for the executive summary's
    horizontal bar chart."""
    if not pairs:
        return []
    max_count = max(count for _, count in pairs)
    return [{"name": name, "count": count, "pct": round(count / max_count * 100)} for name, count in pairs]


def _frameworks_context(frameworks):
    """Adds a covered/label pair per control (for the badge in the template) without
    mutating the FrameworkControl instances build_client_facing_report() returned."""
    return [
        {
            "framework": item["framework"],
            "total": item["total"],
            "covered_count": item["covered_count"],
            "lists_all": item["lists_all"],
            "controls": [
                {"code": control.code, "name": control.name, **_control_badge(control)}
                for control in item["controls"]
            ],
        }
        for item in frameworks
    ]


def _control_badge(control):
    if not control.active_rules_count:
        return {"covered": False, "label": "Não coberto"}
    noun = "detecção" if control.active_rules_count == 1 else "detecções"
    return {"covered": True, "label": f"Coberto ({control.active_rules_count} {noun})"}


def _build_pdf(elements, title):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=1.8 * cm,
        rightMargin=1.8 * cm,
        topMargin=1.8 * cm,
        bottomMargin=1.8 * cm,
        title=title,
    )
    doc.build(elements)
    return buffer.getvalue()


def _cell(text):
    """Wraps long free text in a Paragraph so Table actually wraps it instead of overflowing the page.
    Escaped because Paragraph parses markup - a "<" typed in a title would otherwise break the build."""
    return Paragraph(escape(text) if text else "-", _CELL_STYLE)


def _kv_table(rows):
    table = Table(rows, colWidths=[6 * cm, 10 * cm])
    table.setStyle(
        TableStyle(
            [
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor(_COLOR_BORDER)),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


def _data_table(header, rows, col_widths):
    table = Table([header] + rows, colWidths=col_widths, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(_COLOR_PRIMARY)),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor(_COLOR_BORDER)),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor(_COLOR_BG_LIGHT)]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    return table
