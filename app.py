"""
Threat Assessment — Enterprise Edition
Appréciation de la menace cyber pour un contexte entreprise.

Axes : Vol de données / Sabotage / Réputation

Formule score brut  : Score = Valeur_cible x Mult_surface x Mult_contexte
Formule risque net  : Risque_residuel = Score_brut x Reducteur_maturite

Le Bloc D (maturité) produit un réducteur [0.4–1.0] inspiré ISO 27005 :
une entreprise bien protégée abaisse son risque résiduel même face à une
menace brute élevée.

Lancer : python app.py  ->  http://localhost:5000
"""

import os
import json
import datetime
import socket
import threading
import webbrowser

from flask import Flask, render_template, request, redirect, url_for, send_file, session

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY

app = Flask(__name__)
app.secret_key = "threat-enterprise-secret"

CONFIG_DIR  = os.path.join(os.path.dirname(__file__), "config")
REPORTS_DIR = os.path.join(os.path.dirname(__file__), "reports")
os.makedirs(REPORTS_DIR, exist_ok=True)


# ==============================================================================
# Chargement des fichiers de config
# On relit à chaque appel pour permettre les modifications à chaud.
# ==============================================================================

def load(filename):
    with open(os.path.join(CONFIG_DIR, filename), encoding="utf-8") as f:
        return json.load(f)


def get_questions_flat():
    blocs = load("questions.json")["blocs"]
    result = []
    for bloc in blocs:
        for q in bloc["questions"]:
            result.append({**q, "_bloc_id": bloc["id"]})
    return result


# ==============================================================================
# Logique de scoring
# ==============================================================================

def mult_surface(reponses):
    weights = load("weights.json")["surface"]
    scoring = load("scoring.json")["multiplicateur_surface"]
    score   = sum(reponses.get(qid, 1) * p for qid, p in weights.items())
    mult    = scoring["min"] + (score / 4.0) * (scoring["max"] - scoring["min"])
    return round(min(max(mult, scoring["min"]), scoring["max"]), 3)


def score_valeur(reponses, axe):
    blocs = load("questions.json")["blocs"]
    total, poids = 0.0, 0.0
    for bloc in blocs:
        if bloc["id"] != "B":
            continue
        for q in bloc["questions"]:
            p = q.get("axe_poids", {}).get(axe, 0.0)
            if p > 0:
                total += reponses.get(q["id"], 1) * p
                poids += 4.0 * p
    if poids == 0:
        return 1.0
    return round(1.0 + (total / poids) * 3.0, 3)


def mult_contexte(reponses):
    weights = load("weights.json")["contexte"]
    scoring = load("scoring.json")["multiplicateur_contexte"]
    score   = sum(reponses.get(qid, 1) * p for qid, p in weights.items())
    mult    = scoring["min"] + (score / 4.0) * (scoring["max"] - scoring["min"])
    return round(min(max(mult, scoring["min"]), scoring["max"]), 3)


def reducteur_maturite(reponses):
    """
    Calcule le réducteur de maturité depuis le Bloc D.
    Inspiré ISO 27005 section 9 : les mesures de traitement du risque
    abaissent le risque résiduel.

    Score maturité élevé (bonne sécurité) → réducteur proche de 0.4 (forte réduction)
    Score maturité faible (peu de mesures) → réducteur proche de 1.0 (pas de réduction)
    """
    blocs = load("questions.json")["blocs"]
    bloc_d = next((b for b in blocs if b["id"] == "D"), None)
    if not bloc_d:
        return 1.0  # pas de bloc D = pas de réduction

    questions_d = bloc_d["questions"]
    if not questions_d:
        return 1.0

    # Moyenne des réponses du bloc D (1=mauvais, 4=bon)
    total = sum(reponses.get(q["id"], 1) for q in questions_d)
    moyenne = total / len(questions_d)

    # Normalisation : maturité max (4) → réducteur min (0.4), maturité min (1) → réducteur max (1.0)
    cfg = load("scoring.json")["reducteur_maturite"]
    r_min = cfg["min"]  # 0.40 — meilleure maturité possible
    r_max = cfg["max"]  # 1.00 — aucune mesure en place

    reducteur = r_max - ((moyenne - 1) / 3.0) * (r_max - r_min)
    return round(min(max(reducteur, r_min), r_max), 3)


def niveau_from_score(score, niveaux):
    for k in sorted((k for k in niveaux if not k.startswith("_")), key=int):
        if score <= niveaux[k]["seuil_max"]:
            return int(k)
    return 4


def calculer_scores(reponses):
    scoring = load("scoring.json")
    niveaux = scoring["niveaux"]
    axes    = {k: v for k, v in scoring["axes"].items() if not k.startswith("_")}

    ms = mult_surface(reponses)
    mc = mult_contexte(reponses)
    rm = reducteur_maturite(reponses)

    scores = {
        "_mult_surface":      ms,
        "_mult_contexte":     mc,
        "_reducteur_maturite": rm,
    }

    niveaux_bruts    = []
    niveaux_residuels = []

    for axe in axes:
        valeur     = score_valeur(reponses, axe)
        score_brut = round(min(max(valeur * ms * mc,
                                   scoring["score_final"]["min"]),
                               scoring["score_final"]["max"]), 2)
        # Risque résiduel = score brut réduit par la maturité
        score_net  = round(min(max(score_brut * rm,
                                   scoring["score_final"]["min"]),
                               scoring["score_final"]["max"]), 2)

        n_brut = niveau_from_score(score_brut, niveaux)
        n_net  = niveau_from_score(score_net,  niveaux)

        scores[axe] = {
            "score":          score_net,    # risque résiduel — affiché en principal
            "score_brut":     score_brut,   # menace brute avant réduction
            "score_valeur":   valeur,
            "niveau":         n_net,
            "niveau_brut":    n_brut,
            "label":          niveaux[str(n_net)]["label"],
            "label_brut":     niveaux[str(n_brut)]["label"],
            "couleur":        niveaux[str(n_net)]["couleur"],
            "couleur_brut":   niveaux[str(n_brut)]["couleur"],
        }
        niveaux_bruts.append(n_brut)
        niveaux_residuels.append(n_net)

    methode = scoring["agregation_globale"]["methode"]

    def agreger(niveaux_list):
        if methode == "max":
            return max(niveaux_list)
        return min(max(round(sum(niveaux_list) / len(niveaux_list)), 1), 4)

    n_brut_global = agreger(niveaux_bruts)
    n_net_global  = agreger(niveaux_residuels)

    scores["global"] = {
        "niveau":      n_net_global,
        "niveau_brut": n_brut_global,
        "label":       niveaux[str(n_net_global)]["label"],
        "label_brut":  niveaux[str(n_brut_global)]["label"],
        "couleur":     niveaux[str(n_net_global)]["couleur"],
        "couleur_brut":niveaux[str(n_brut_global)]["couleur"],
    }
    return scores


# ==============================================================================
# Acteurs pertinents
# ==============================================================================

def acteurs_pertinents(reponses, scores):
    kb      = load("knowledge_base.json")
    scoring = load("scoring.json")
    axes    = {k: v for k, v in scoring["axes"].items() if not k.startswith("_")}

    # Axes avec un niveau >= 2 (on ne liste des acteurs que sur les axes exposés)
    axes_exposes = [axe for axe in axes if scores[axe]["niveau"] >= 2]
    if not axes_exposes:
        return []

    # Tier max selon la réponse "capacités adversaires"
    cap = reponses.get("ctx_capacites_adversaires", 1)
    tier_max = 1 if cap >= 4 else 2 if cap >= 3 else 2

    resultat = []
    for code, a in kb.get("acteurs", {}).items():
        if not isinstance(a, dict) or not a.get("actif", True):
            continue
        if a.get("tier", 3) > tier_max:
            continue
        overlap = set(a.get("finalites", [])) & set(axes_exposes)
        if overlap:
            resultat.append({**a, "code": code, "finalites_matchees": list(overlap)})

    return resultat[:4]


# ==============================================================================
# Export PDF — sobre, tableaux simples
# ==============================================================================

def generer_pdf(nom, reponses, scores, acteurs):
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    filepath  = os.path.join(REPORTS_DIR, f"rapport_{timestamp}.pdf")

    cfg_q   = load("questions.json")
    scoring = load("scoring.json")
    axes    = {k: v for k, v in scoring["axes"].items() if not k.startswith("_")}

    doc = SimpleDocTemplate(filepath, pagesize=A4,
              rightMargin=2*cm, leftMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)

    st   = getSampleStyleSheet()
    h1   = ParagraphStyle("H1", parent=st["Normal"], fontSize=11, fontName="Helvetica-Bold",
                           spaceBefore=14, spaceAfter=4)
    body = ParagraphStyle("BD", parent=st["Normal"], fontSize=9, leading=13,
                           alignment=TA_JUSTIFY, spaceAfter=3)
    foot = ParagraphStyle("FT", parent=st["Normal"], fontSize=7,
                           alignment=TA_CENTER, spaceBefore=8)

    # Style pour le contenu des cellules — wrapping activé
    cell_style  = ParagraphStyle("CE", parent=st["Normal"], fontSize=9, leading=12)
    cell_bold   = ParagraphStyle("CB", parent=st["Normal"], fontSize=9, leading=12,
                                  fontName="Helvetica-Bold")
    cell_small  = ParagraphStyle("CS", parent=st["Normal"], fontSize=8, leading=11)

    GREY = colors.HexColor("#dddddd")

    def p(text, style=None):
        # Convertit une string en Paragraph pour le wrapping automatique
        return Paragraph(str(text), style or cell_style)

    def table(data, widths):
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

    story = []

    # En-tête
    story.append(Paragraph("<b>APPRÉCIATION DE LA MENACE CYBER — ENTREPRISE</b>", st["Title"]))
    story.append(Paragraph(f"Périmètre : {nom}", body))
    story.append(Paragraph(
        f"Analyse du {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')} — Méthode S/E/I v2 (avec maturité ISO 27005)", body))
    story.append(Spacer(1, 10))

    # Résultat global — brut et résiduel côte à côte
    story.append(Paragraph("Résultat", h1))
    ng = scores["global"]
    story.append(table([
        [p("Menace brute (avant maturité)", cell_bold),
         p("Réducteur maturité (Bloc D)", cell_bold),
         p("Risque résiduel (après maturité)", cell_bold)],
        [p(f"{ng['label_brut']} ({ng['niveau_brut']}/4)"),
         p(f"{scores['_reducteur_maturite']:.2f}  [0.4–1.0]"),
         p(f"{ng['label']} ({ng['niveau']}/4)", cell_bold)],
    ], [5.5*cm, 5*cm, 6.5*cm]))
    story.append(Spacer(1, 5))
    story.append(Paragraph(
        f"Mult. surface : {scores['_mult_surface']:.2f}  |  Mult. contexte : {scores['_mult_contexte']:.2f}",
        body))
    story.append(Spacer(1, 8))

    # Détail par axe — brut et résiduel
    story.append(Paragraph("Détail par axe", h1))
    rows = [[p("Axe", cell_bold), p("Score brut", cell_bold), p("Réducteur", cell_bold),
             p("Risque résiduel", cell_bold), p("Niveau résiduel", cell_bold)]]
    for axe, info in axes.items():
        a = scores[axe]
        rows.append([
            p(info["label"]),
            p(f"{a['score_brut']:.2f}  ({a['label_brut']})"),
            p(f"{scores['_reducteur_maturite']:.2f}"),
            p(f"{a['score']:.2f}"),
            p(f"{a['label']} ({a['niveau']}/4)"),
        ])
    story.append(table(rows, [3.5*cm, 4*cm, 2.5*cm, 2.8*cm, 4.2*cm]))
    story.append(Spacer(1, 8))

    # Acteurs
    if acteurs:
        story.append(Paragraph("Acteurs de la menace pertinents", h1))
        rows_a = [[p("Acteur", cell_bold), p("Origine / Type", cell_bold),
                   p("Finalités", cell_bold), p("TTPs", cell_bold)]]
        for a in acteurs:
            rows_a.append([
                p(a["code"], cell_bold),
                p(f"{a.get('origine', '')} ({a.get('type', '')})", cell_small),
                p(", ".join(a.get("finalites_matchees", [])), cell_small),
                p(", ".join(a.get("ttps_labels", [])[:3]), cell_small),
            ])
        story.append(table(rows_a, [2.5*cm, 5*cm, 3.5*cm, 6*cm]))
        story.append(Spacer(1, 8))

    # Réponses détaillées
    story.append(Paragraph("Réponses détaillées", h1))
    rows_r = [[p("Bloc", cell_bold), p("Question", cell_bold),
               p("Val.", cell_bold), p("Réponse", cell_bold)]]
    for bloc in cfg_q["blocs"]:
        for q in bloc["questions"]:
            val = reponses.get(q["id"], 1)
            lbl = next((o["label"] for o in q["options"] if o["valeur"] == val), "")
            rows_r.append([
                p(f"Bloc {bloc['id']}"),
                p(q["texte"]),
                p(str(val)),
                p(lbl),
            ])
    story.append(table(rows_r, [1.5*cm, 6.5*cm, 1*cm, 8*cm]))
    story.append(Spacer(1, 10))

    # Limites
    story.append(Paragraph("Limites", h1))
    for l in [
        "Le risque résiduel est calculé par Score_brut × Réducteur_maturité — il suppose que les mesures déclarées sont réellement opérationnelles.",
        "Ne remplace pas un audit ISO 27005 complet, un test d'intrusion ou une homologation.",
        "Les acteurs sont issus de knowledge_base.json — à mettre à jour selon la veille CTI.",
    ]:
        story.append(Paragraph(f"• {l}", body))

    story.append(Paragraph("Document généré automatiquement — Usage interne", foot))

    doc.build(story)
    return filepath


# ==============================================================================
# Routes Flask
# ==============================================================================

@app.route("/")
def index():
    exemples = load("examples.json").get("exemples", [])
    return render_template("index.html", exemples=exemples)


@app.route("/questionnaire", methods=["GET", "POST"])
def questionnaire():
    if request.method == "POST":
        nom      = request.form.get("nom_deploiement", "Périmètre inconnu")
        reponses = {}
        for q in get_questions_flat():
            val = request.form.get(q["id"])
            reponses[q["id"]] = int(val) if val else 1
        session["nom"]      = nom
        session["reponses"] = reponses
        return redirect(url_for("resultats"))

    nom   = request.args.get("nom", "")
    blocs = load("questions.json")["blocs"]
    return render_template("questionnaire.html", blocs=blocs, nom=nom)


@app.route("/resultats")
def resultats():
    nom      = session.get("nom", "Inconnu")
    reponses = session.get("reponses", {})
    if not reponses:
        return redirect(url_for("index"))

    scores  = calculer_scores(reponses)
    acteurs = acteurs_pertinents(reponses, scores)
    scoring = load("scoring.json")
    axes    = {k: v for k, v in scoring["axes"].items() if not k.startswith("_")}
    blocs   = load("questions.json")["blocs"]

    details = []
    for bloc in blocs:
        for q in bloc["questions"]:
            val = reponses.get(q["id"], 1)
            lbl = next((o["label"] for o in q["options"] if o["valeur"] == val), "")
            details.append({
                "bloc_id":    bloc["id"],
                "bloc_titre": bloc["titre"],
                "texte":      q["texte"],
                "valeur":     val,
                "label":      lbl,
            })

    return render_template("resultats.html",
        nom=nom, scores=scores, details=details,
        acteurs=acteurs, axes=axes,
        date=datetime.datetime.now().strftime("%d/%m/%Y %H:%M"))


@app.route("/telecharger_pdf")
def telecharger_pdf():
    nom      = session.get("nom", "Inconnu")
    reponses = session.get("reponses", {})
    if not reponses:
        return redirect(url_for("index"))
    scores  = calculer_scores(reponses)
    acteurs = acteurs_pertinents(reponses, scores)
    filepath = generer_pdf(nom, reponses, scores, acteurs)
    return send_file(filepath, as_attachment=True,
                     download_name=f"rapport_{nom.replace(' ', '_')[:40]}.pdf")


@app.route("/exemple/<ex_id>")
def charger_exemple(ex_id):
    exemples = load("examples.json").get("exemples", [])
    ex = next((e for e in exemples if e["id"] == ex_id), None)
    if not ex:
        return redirect(url_for("index"))
    session["nom"]      = ex["nom"]
    session["reponses"] = ex["reponses"]
    return redirect(url_for("resultats"))


# ==============================================================================
# Vérifications sécurité au démarrage
# ==============================================================================

def check_isolation():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.5)
        if s.connect_ex(("0.0.0.0", 5000)) == 0:
            print("[SECURITE] Port 5000 déjà exposé — arrêt.")
            raise SystemExit(1)
        s.close()
    except OSError:
        pass


def check_internet():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1)
        s.connect(("8.8.8.8", 53))
        s.close()
        print("[INFO] Internet accessible — l'outil ne fait aucune requête sortante.")
    except OSError:
        print("[INFO] Pas d'accès internet — isolation réseau confirmée.")


if __name__ == "__main__":
    print("=" * 50)
    print("  THREAT ASSESSMENT — ENTREPRISE")
    print("=" * 50)

    check_isolation()
    check_internet()

    HOST = "127.0.0.1"
    PORT = 5000

    print(f"\n  http://{HOST}:{PORT}")
    print(f"  Accessible uniquement depuis cette machine.\n")

    threading.Timer(1, lambda: webbrowser.open(f"http://{HOST}:{PORT}")).start()
    app.run(host=HOST, port=PORT, debug=False)
