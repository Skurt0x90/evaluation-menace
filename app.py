"""
Appréciation de la menace cyber pour un contexte entreprise.

Axes : Vol de données / Sabotage / Réputation

Formule score brut  : Score = Valeur_cible x Mult_surface x Mult_contexte
Formule risque net  : Risque_residuel = Score_brut x Reducteur_maturite

Questions bloc D permettent de réduire le risque :
une entreprise bien protégée abaisse son risque résiduel même face à une
menace brute élevée.
"""

import os
import json
import datetime
import socket
import threading
import webbrowser

from flask import Flask, render_template, request, redirect, url_for, send_file, session
from models.pdf_creator import generer_pdf
from models.config import load, get_questions_flat
from models.knowledge import acteurs_pertinents
from models.scoring import calculer_scores

app = Flask(__name__)
app.secret_key = "threat-enterprise-secret"

CONFIG_DIR  = os.path.join(os.path.dirname(__file__), "config")
REPORTS_DIR = os.path.join(os.path.dirname(__file__), "reports")
os.makedirs(REPORTS_DIR, exist_ok=True)



# ==============================================================================
# Routes Flask
# ==============================================================================

@app.route("/")
def index():
    try:
        exemples = load("examples.json").get("exemples", [])
    except (FileNotFoundError, KeyError, ValueError):
        exemples = []
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
    filepath = generer_pdf(
        nom, reponses, scores, acteurs,
        cfg_questions=load("questions.json"),
        cfg_scoring=load("scoring.json"),
    )
    return send_file(filepath, as_attachment=True,
                     download_name=f"rapport_{nom.replace(' ', '_')[:40]}.pdf")


@app.route("/analyses/<ex_id>")
def charger_exemple(ex_id):
    # pour chaque fichier dans reports on get le report et on l'affiche
    exemples = load("examples.json").get("exemples", [])
    ex = next((e for e in exemples if e["id"] == ex_id), None)
    if not ex:
        return redirect(url_for("index"))
    session["nom"]      = ex["nom"]
    session["reponses"] = ex["reponses"]
    return redirect(url_for("resultats"))


if __name__ == "__main__":
    print("=" * 50)
    print("  THREAT ASSESSMENT — ENTREPRISE")
    print("=" * 50)

    HOST = "127.0.0.1"
    PORT = 5000

    print(f"\n  http://{HOST}:{PORT}")
    print(f"  Accessible uniquement depuis cette machine.\n")

    threading.Timer(1, lambda: webbrowser.open(f"http://{HOST}:{PORT}")).start()
    app.run(host=HOST, port=PORT, debug=False)
