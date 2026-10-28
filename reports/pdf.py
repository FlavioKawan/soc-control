import io
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

_STYLES = getSampleStyleSheet()
# Keeps a section title on the same page as the table that follows it.
_STYLES["Heading2"].keepWithNext = True
_STYLES["Heading3"].keepWithNext = True
_CELL_STYLE = ParagraphStyle("cell", parent=_STYLES["Normal"], fontSize=8, leading=10)
_NOTE_STYLE = ParagraphStyle("note", parent=_STYLES["Normal"], fontSize=8, textColor=colors.HexColor("#6b7280"))


def render_client_report_pdf(report):
    """Renders the dict from reports.services.build_client_report() as a PDF (bytes)."""
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
    """Renders the dict from reports.services.build_client_facing_report() as a PDF (bytes)."""
    client = report["client"]
    elements = [
        Paragraph(f"Relatório de Segurança — {escape(client.name)}", _STYLES["Title"]),
        Paragraph(f"Gerado em {report['generated_at']:%d/%m/%Y %H:%M}", _STYLES["Normal"]),
        Spacer(1, 0.5 * cm),
    ]

    elements += _executive_summary(report)
    elements += _client_actions(report)
    elements += _use_case_coverage(report["use_case_links"])
    elements += _framework_coverage(report["frameworks"])

    elements.append(Paragraph("Detecções ativas", _STYLES["Heading2"]))
    if report["active_rules"]:
        rows = [
            [_cell(rule.name), _str_or_dash(rule.severity), _str_or_dash(rule.log_source)]
            for rule in report["active_rules"]
        ]
        elements.append(
            _data_table(["Detecção", "Severidade", "Fonte de log"], rows, col_widths=[9.4 * cm, 3 * cm, 5 * cm])
        )
    else:
        elements.append(Paragraph("Nenhuma detecção ativa no momento.", _STYLES["Normal"]))
    elements.append(Spacer(1, 0.6 * cm))

    elements.append(Paragraph("Itens em tratamento pelo SOC e terceiros", _STYLES["Heading2"]))
    if report["other_gaps"]:
        rows = [
            [gap.code, _cell(gap.title), _str_or_dash(gap.responsible_party),
             _str_or_dash(gap.criticality), _str_or_dash(gap.status)]
            for gap in report["other_gaps"]
        ]
        elements.append(
            _data_table(
                ["Código", "Item", "Responsável", "Criticidade", "Situação"],
                rows,
                col_widths=[2.3 * cm, 7 * cm, 2.8 * cm, 2.6 * cm, 2.7 * cm],
            )
        )
    else:
        elements.append(Paragraph("Nenhum item em aberto.", _STYLES["Normal"]))

    return _build_pdf(elements, title=f"Relatório de Segurança - {client.name}")


def _executive_summary(report):
    coverage = report["coverage"]
    if coverage["applicable"]:
        coverage_text = f"{coverage['percentage']}% ({coverage['covered']} de {coverage['applicable']} casos de uso)"
    else:
        coverage_text = "Sem casos de uso aplicáveis cadastrados"

    gaps_text = str(report["open_gaps_count"])
    if report["open_gaps_by_criticality"]:
        gaps_text += " (" + ", ".join(f"{escape(name)}: {count}" for name, count in report["open_gaps_by_criticality"]) + ")"

    pending_actions = len(report["client_gaps"]) + len(report["problem_log_sources"])
    rows = [
        ["Cobertura de casos de uso", coverage_text],
        ["Detecções ativas", str(len(report["active_rules"]))],
        ["Fontes de log recebendo dados", f"{report['log_sources_receiving']} de {report['log_sources_total']}"],
        ["Pendências em aberto", Paragraph(gaps_text, _CELL_STYLE)],
        ["Ações pendentes do seu lado", str(pending_actions)],
    ]
    return [Paragraph("Resumo executivo", _STYLES["Heading2"]), _kv_table(rows), Spacer(1, 0.6 * cm)]


def _client_actions(report):
    elements = [Paragraph("Ações pendentes do seu lado", _STYLES["Heading2"])]
    if not report["client_gaps"] and not report["problem_log_sources"]:
        elements += [Paragraph("Nenhuma ação pendente no momento.", _STYLES["Normal"]), Spacer(1, 0.6 * cm)]
        return elements

    if report["client_gaps"]:
        elements.append(Paragraph("Pendências sob sua responsabilidade", _STYLES["Heading3"]))
        rows = [
            [gap.code, _cell(gap.title), _str_or_dash(gap.criticality), _cell(gap.recommendation),
             f"{gap.days_open} dias" if gap.days_open is not None else "-"]
            for gap in report["client_gaps"]
        ]
        elements.append(
            _data_table(
                ["Código", "Pendência", "Criticidade", "Recomendação", "Em aberto há"],
                rows,
                col_widths=[2.1 * cm, 4.6 * cm, 2.4 * cm, 6 * cm, 2.3 * cm],
            )
        )
        elements.append(Spacer(1, 0.3 * cm))

    if report["problem_log_sources"]:
        elements.append(Paragraph("Fontes de log sem dados ou não integradas", _STYLES["Heading3"]))
        rows = [
            [_cell(str(link.log_source)), _str_or_dash(link.status),
             link.last_event_at.strftime("%d/%m/%Y %H:%M") if link.last_event_at else "-",
             str(link.affected_rules_count)]
            for link in report["problem_log_sources"]
        ]
        elements.append(
            _data_table(
                ["Fonte de log", "Situação", "Último evento", "Detecções afetadas"],
                rows,
                col_widths=[6.4 * cm, 3.5 * cm, 3.7 * cm, 3.8 * cm],
            )
        )
        elements.append(
            Paragraph(
                "Enquanto a fonte não enviar dados, as detecções que dependem dela não conseguem alertar.",
                _NOTE_STYLE,
            )
        )
    elements.append(Spacer(1, 0.6 * cm))
    return elements


def _use_case_coverage(use_case_links):
    elements = [Paragraph("Cobertura por caso de uso", _STYLES["Heading2"])]
    if use_case_links:
        rows = [
            [_cell(f"{link.use_case.code} — {link.use_case.name}"), _cell(link.use_case.protects),
             _str_or_dash(link.criticality), _str_or_dash(link.status)]
            for link in use_case_links
        ]
        elements.append(
            _data_table(
                ["Caso de uso", "O que protege", "Criticidade", "Situação"],
                rows,
                col_widths=[5.6 * cm, 6.4 * cm, 2.6 * cm, 2.8 * cm],
            )
        )
    else:
        elements.append(Paragraph("Nenhum caso de uso aplicável cadastrado.", _STYLES["Normal"]))
    elements.append(Spacer(1, 0.6 * cm))
    return elements


def _framework_coverage(frameworks):
    elements = [Paragraph("Cobertura por framework", _STYLES["Heading2"])]
    if not frameworks:
        elements += [Paragraph("Nenhum framework cadastrado.", _STYLES["Normal"]), Spacer(1, 0.6 * cm)]
        return elements

    for item in frameworks:
        elements.append(
            Paragraph(
                f"{escape(item['framework'].name)}: {item['covered_count']} de {item['total']} controles cobertos",
                _STYLES["Heading3"],
            )
        )
        if item["controls"]:
            rows = [
                [control.code, _cell(control.name),
                 _control_status(control.active_rules_count)]
                for control in item["controls"]
            ]
            elements.append(
                _data_table(["Código", "Controle", "Situação"], rows, col_widths=[2.6 * cm, 9.6 * cm, 5.2 * cm])
            )
        else:
            elements.append(Paragraph("Nenhum controle coberto por detecções ativas.", _STYLES["Normal"]))
        if not item["lists_all"] and item["controls"]:
            elements.append(Paragraph("Listados apenas os controles cobertos.", _NOTE_STYLE))
        elements.append(Spacer(1, 0.3 * cm))
    elements.append(Spacer(1, 0.3 * cm))
    return elements


def _control_status(active_rules_count):
    if not active_rules_count:
        return "Não coberto"
    noun = "detecção" if active_rules_count == 1 else "detecções"
    return f"Coberto ({active_rules_count} {noun})"


def _str_or_dash(value):
    return _cell(str(value)) if value else "-"


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
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e3e5ec")),
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
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4f46e5")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8f9fc")]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    return table
