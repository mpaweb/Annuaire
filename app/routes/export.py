"""
Export — CSV / Excel / PDF pour contacts et ROC.
"""

import csv
import io
from datetime import datetime
from flask import Blueprint, request, send_file, jsonify
from flask_login import login_required, current_user
from reportlab.lib.pagesizes import A3, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.enums import TA_LEFT, TA_CENTER
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment
from app import db
from app.models import Contact, Roc, AuditLog

export_bp = Blueprint("export", __name__)


def _log(action: str, detail: str = "") -> None:
    entry = AuditLog(
        username=current_user.username,
        action="EXPORT",
        table_name=action,
        detail=detail,
        ip_address=request.remote_addr or "",
    )
    db.session.add(entry)
    db.session.commit()


def _get_data(table: str) -> tuple[list, list]:
    """Retourne (headers, rows) selon la table demandée."""
    if table == "contacts":
        headers = ["Société", "Nom", "Prénom", "Fonction", "Email",
                   "Téléphone", "Téléphone 2", "Notes"]
        rows = [
            [c.societe, c.nom, c.prenom, c.fonction,
             c.email, c.telephone, c.telephone2, c.notes]
            for c in Contact.query.order_by(Contact.societe).all()
        ]
    else:
        headers = ["Nom Client", "ROC", "Trinity", "Infogérance",
                   "Astreinte", "Type Contrat", "Date Anniversaire Contrat"]
        rows = [
            [r.nom_client, r.roc, r.trinity, r.infogerance,
             r.astreinte, r.type_contrat, r.date_anniversaire_contrat]
            for r in Roc.query.order_by(Roc.nom_client).all()
        ]
    return headers, rows


# ── CSV ───────────────────────────────────────────────────────────────────────

@export_bp.route("/<table>/csv")
@login_required
def export_csv(table: str):
    if table not in ("contacts", "rocs"):
        return jsonify({"error": "Table invalide."}), 400

    headers, rows = _get_data(table)
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";")
    writer.writerow(headers)
    writer.writerows(rows)
    buf.seek(0)

    _log(table, f"CSV — {len(rows)} lignes")
    fname = f"annuaire_{table}_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    return send_file(
        io.BytesIO(buf.getvalue().encode("utf-8-sig")),
        mimetype="text/csv",
        as_attachment=True,
        download_name=fname,
    )


# ── Excel ─────────────────────────────────────────────────────────────────────

@export_bp.route("/<table>/xlsx")
@login_required
def export_xlsx(table: str):
    if table not in ("contacts", "rocs"):
        return jsonify({"error": "Table invalide."}), 400

    headers, rows = _get_data(table)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = table.capitalize()

    # En-tête
    header_fill = PatternFill("solid", fgColor="1E3A5F")
    header_font = Font(bold=True, color="FFFFFF", size=11)
    for col_idx, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_idx, value=h)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")

    # Données
    alt_fill = PatternFill("solid", fgColor="EEF2FF")
    for row_idx, row in enumerate(rows, 2):
        fill = alt_fill if row_idx % 2 == 0 else None
        for col_idx, val in enumerate(row, 1):
            cell = ws.cell(row=row_idx, column=col_idx, value=val or "")
            if fill:
                cell.fill = fill

    # Largeurs auto
    col_widths = [22, 15, 15, 20, 30, 16, 16, 40] if table == "contacts" \
        else [25, 12, 12, 20, 20, 18, 24]
    for i, w in enumerate(col_widths, 1):
        ws.column_dimensions[ws.cell(row=1, column=i).column_letter].width = w

    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    _log(table, f"Excel — {len(rows)} lignes")
    fname = f"annuaire_{table}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    return send_file(
        buf,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=fname,
    )


# ── PDF ───────────────────────────────────────────────────────────────────────

@export_bp.route("/<table>/pdf")
@login_required
def export_pdf(table: str):
    if table not in ("contacts", "rocs"):
        return jsonify({"error": "Table invalide."}), 400

    headers, rows = _get_data(table)
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=landscape(A3),
        leftMargin=12*mm, rightMargin=12*mm,
        topMargin=12*mm, bottomMargin=12*mm,
    )

    styles = getSampleStyleSheet()
    cell_style = ParagraphStyle("cell", parent=styles["Normal"],
                                fontSize=7, leading=9)
    head_style = ParagraphStyle("head", parent=styles["Normal"],
                                fontSize=8, leading=10,
                                textColor=colors.white, fontName="Helvetica-Bold")

    usable = landscape(A3)[0] - 24*mm
    weights = [3, 2, 2, 2.5, 4, 2, 2, 4] if table == "contacts" \
        else [3.5, 2, 2, 2.5, 2.5, 2, 3]
    total_w = sum(weights)
    col_widths = [usable * (w / total_w) for w in weights]

    # Titre
    title_style = ParagraphStyle("title", parent=styles["Heading1"],
                                 fontSize=14, spaceAfter=4)
    sub_style   = ParagraphStyle("sub", parent=styles["Normal"],
                                 fontSize=9, textColor=colors.grey, spaceAfter=8)

    table_label = "Contacts" if table == "contacts" else "ROC"
    story = [
        Paragraph(f"Annuaire Neoedge — {table_label}", title_style),
        Paragraph(
            f"Exporté le {datetime.now().strftime('%d/%m/%Y à %H:%M')} "
            f"par {current_user.full_name or current_user.username} — "
            f"{len(rows)} enregistrement(s)",
            sub_style,
        ),
        Spacer(1, 4),
    ]

    # Tableau
    head_row = [Paragraph(h, head_style) for h in headers]
    data_rows = [head_row] + [
        [Paragraph(str(v or ""), cell_style) for v in row]
        for row in rows
    ]

    tbl = Table(data_rows, colWidths=col_widths, repeatRows=1)
    tbl.setStyle(TableStyle([
        ("BACKGROUND",  (0, 0), (-1, 0), colors.HexColor("#1E3A5F")),
        ("TEXTCOLOR",   (0, 0), (-1, 0), colors.white),
        ("FONTNAME",    (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",    (0, 0), (-1, 0), 8),
        ("FONTSIZE",    (0, 1), (-1, -1), 7),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.white, colors.HexColor("#EEF2FF")]),
        ("GRID",        (0, 0), (-1, -1), 0.3, colors.HexColor("#CCCCCC")),
        ("VALIGN",      (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",  (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING",(0, 0), (-1, -1), 4),
    ]))
    story.append(tbl)
    doc.build(story)
    buf.seek(0)

    _log(table, f"PDF — {len(rows)} lignes")
    fname = f"annuaire_{table}_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
    return send_file(buf, mimetype="application/pdf",
                     as_attachment=True, download_name=fname)
