from models.config import load

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
    Score maturité élevé = réducteur 0.4 (forte réduction)
    Score maturité faible = réducteur 1.0 (pas de réduction)
    """
    blocs = load("questions.json")["blocs"]
    bloc_d = next((b for b in blocs if b["id"] == "D"), None)
    if not bloc_d:
        return 1.0 

    questions_d = bloc_d["questions"]
    if not questions_d:
        return 1.0

    total = sum(reponses.get(q["id"], 1) for q in questions_d)
    moyenne = total / len(questions_d)

    cfg = load("scoring.json")["reducteur_maturite"]
    r_min = cfg["min"]  # 0.40 maturité élevée
    r_max = cfg["max"]  # 1.00 maturité nulle

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
            "score":          score_net,    # risque résiduel
            "score_brut":     score_brut,   # risque brut
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
