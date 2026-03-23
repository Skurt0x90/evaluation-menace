"""
models/pdf.py
Génération du rapport PDF.

Ne dépend pas de Flask — reçoit les données en paramètres,
retourne le chemin du fichier généré.
"""

import os
import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY


REPORTS_DIR = os.path.join(os.path.dirname(__file__), "..", "reports")
os.makedirs(REPORTS_DIR, exist_ok=True)

GREY = colors.HexColor("#dddddd")


def _styles():
    st = getSampleStyleSheet()
    return {
        "title": st["Title"],
        "h1":    ParagraphStyle("H1", parent=st["Normal"], fontSize=11,
                                fontName="Helvetica-Bold", spaceBefore=14, spaceAfter=4),
        "body":  ParagraphStyle("BD", parent=st["Normal"], fontSize=9,
                                leading=13, alignment=TA_JUSTIFY, spaceAfter=3),
        "foot":  ParagraphStyle("FT", parent=st["Normal"], fontSize=7,
                                alignment=TA_CENTER, spaceBefore=8),
        "cell":  ParagraphStyle("CE", parent=st["Normal"], fontSize=9, leading=12),
        "bold":  ParagraphStyle("CB", parent=st["Normal"], fontSize=9,
                                leading=12, fontName="Helvetica-Bold"),
        "small": ParagraphStyle("CS", parent=st["Normal"], fontSize=8, leading=11),
    }


def _p(text, style):
    return Paragraph(str(text), style)


def _table(data, widths):
    t = Table(data, colWidths=widths)
    t.setStyle(TableStyle([
        ("FONTNAME",      (0, 0), (-1, 0),  "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, -1), 9),
        ("GRID",          (0, 0), (-1, -1), 0.5, colors.black),
        ("BACKGROUND",    (0, 0), (-1, 0),  GREY),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
    ]))
    return t


def generer_pdf(nom, reponses, scores, acteurs, cfg_questions, cfg_scoring):
    """
    Génère le rapport PDF et retourne son chemin.

    Paramètres :
        nom           : nom du périmètre analysé
        reponses      : dict des réponses (q_id -> valeur int)
        scores        : dict retourné par calculer_scores()
        acteurs       : liste retournée par acteurs_pertinents()
        cfg_questions : contenu de questions.json (dict)
        cfg_scoring   : contenu de scoring.json (dict)
    """
    date = datetime.datetime.now().strftime("%Y%m%d")
    filepath  = os.path.join(REPORTS_DIR, f"rapport_{date}_{nom}.pdf")

    axes = {k: v for k, v in cfg_scoring["axes"].items() if not k.startswith("_")}

    doc = SimpleDocTemplate(filepath, pagesize=A4,
              rightMargin=2*cm, leftMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)

    s = _styles()

    def cell(text, style=None):
        return _p(text, style or s["cell"])

    story = []

    # En-tête
    story.append(Paragraph(f"<b>APPRÉCIATION DE LA MENACE CYBER — {nom}</b>", s["title"]))
    story.append(Paragraph("",s["body"]))
    story.append(Paragraph(
        f"Analyse du {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}"
        " — Méthode S/E/I", s["body"]))
    story.append(Spacer(1, 10))

    # Résultat global — menace brute vs risque résiduel
    story.append(Paragraph("Résultat", s["h1"]))
    ng = scores["global"]
    story.append(_table([
        [cell("Menace brute", s["bold"]),
         cell("Réducteur maturité", s["bold"]),
         cell("Risque résiduel", s["bold"])],
        [cell(f"{ng['label_brut']} ({ng['niveau_brut']}/4)"),
         cell(f"{scores['_reducteur_maturite']:.2f}  [0.55–1.0]"),
         cell(f"{ng['label']} ({ng['niveau']}/4)", s["bold"])],
    ], [5.5*cm, 5*cm, 6.5*cm]))
    story.append(Spacer(1, 5))
    story.append(Paragraph(
        f"Mult. surface : {scores['_mult_surface']:.2f}"
        f"  |  Mult. contexte : {scores['_mult_contexte']:.2f}", s["body"]))
    story.append(Spacer(1, 8))

    # Détail par axe
    story.append(Paragraph("Détail par axe", s["h1"]))
    rows = [[cell("Axe", s["bold"]), cell("Score brut", s["bold"]), cell("Réducteur", s["bold"]),
             cell("Risque résiduel", s["bold"]), cell("Niveau résiduel", s["bold"])]]
    for axe, info in axes.items():
        a = scores[axe]
        rows.append([
            cell(info["label"]),
            cell(f"{a['score_brut']:.2f}  ({a['label_brut']})"),
            cell(f"{scores['_reducteur_maturite']:.2f}"),
            cell(f"{a['score']:.2f}"),
            cell(f"{a['label']} ({a['niveau']}/4)"),
        ])
    story.append(_table(rows, [3.5*cm, 4*cm, 2.5*cm, 2.8*cm, 4.2*cm]))
    story.append(Spacer(1, 8))

    # Acteurs pertinents
    if acteurs:
        story.append(Paragraph("Acteurs de la menace pertinents", s["h1"]))
        rows_a = [[cell("Acteur", s["bold"]), cell("Origine / Type", s["bold"]),
                   cell("Finalités", s["bold"]), cell("TTPs", s["bold"])]]
        for a in acteurs:
            rows_a.append([
                cell(a["code"], s["bold"]),
                cell(f"{a.get('origine', '')} ({a.get('type', '')})", s["small"]),
                cell(", ".join(a.get("finalites_matchees", [])), s["small"]),
                cell(", ".join(a.get("ttps_labels", [])[:3]), s["small"]),
            ])
        story.append(_table(rows_a, [2.5*cm, 5*cm, 3.5*cm, 6*cm]))
        story.append(Spacer(1, 8))

    # Réponses détaillées
    story.append(Paragraph("Réponses détaillées", s["h1"]))
    rows_r = [[cell("Bloc", s["bold"]), cell("Question", s["bold"]),
               cell("Val.", s["bold"]), cell("Réponse", s["bold"])]]
    for bloc in cfg_questions["blocs"]:
        for q in bloc["questions"]:
            val = reponses.get(q["id"], 1)
            lbl = next((o["label"] for o in q["options"] if o["valeur"] == val), "")
            rows_r.append([
                cell(f"Bloc {bloc['id']}"),
                cell(q["texte"]),
                cell(str(val)),
                cell(lbl),
            ])
    story.append(_table(rows_r, [1.5*cm, 6.5*cm, 1*cm, 8*cm]))
    story.append(Spacer(1, 10))

    # Limites
    story.append(Paragraph("Limites", s["h1"]))
    for l in [
        "Le risque résiduel est calculé par Score_brut × Réducteur_maturité"
        " — il suppose que les mesures déclarées sont réellement opérationnelles.",
        "Ne remplace pas un audit complet, un test d'intrusion ou une homologation.",
        "Les acteurs sont issus de knowledge_base.json à mettre à jour selon CTI sectoriel.",
    ]:
        story.append(Paragraph(f"• {l}", s["body"]))

    story.append(Paragraph("Document généré automatiquement pour usage interne", s["foot"]))

    doc.build(story)
    return filepath