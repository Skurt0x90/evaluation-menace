from models.config import load

def _load_config():
    return {
        "weights": load("weights.json"),
        "scoring": load("scoring.json"),
        "questions": load("questions.json"),
    }

def _calculate_multiplier(reponses, key):
    cfg = _load_config()
    weights = cfg["weights"][key]
    scoring = cfg["scoring"][f"multiplicateur_{key}"]
    score = sum(reponses.get(qid, 1) * p for qid, p in weights.items())
    mult = scoring["min"] + (score / 4.0) * (scoring["max"] - scoring["min"])
    return round(min(max(mult, scoring["min"]), scoring["max"]), 3)

def _calculate_surface_multiplier(reponses):
    return _calculate_multiplier(reponses, "surface")

def _calculate_context_multiplier(reponses):
    return _calculate_multiplier(reponses, "contexte")

def _calculate_maturity_reducer(reponses):
    cfg = _load_config()
    bloc_d = next((b for b in cfg["questions"]["blocs"] if b["id"] == "D"), None)
    if not bloc_d or not bloc_d["questions"]:
        return 1.0

    total = sum(reponses.get(q["id"], 1) for q in bloc_d["questions"])
    avg = total / len(bloc_d["questions"])

    r_cfg = cfg["scoring"]["reducteur_maturite"]
    r_min, r_max = r_cfg["min"], r_cfg["max"]
    reducer = r_max - ((avg - 1) / 3.0) * (r_max - r_min)
    return round(min(max(reducer, r_min), r_max), 3)

def _calculate_axis_value(reponses, axe):
    cfg = _load_config()
    total, weight = 0.0, 0.0
    for bloc in cfg["questions"]["blocs"]:
        if bloc["id"] != "B":
            continue
        for q in bloc["questions"]:
            p = q.get("axe_poids", {}).get(axe, 0.0)
            if p > 0:
                total += reponses.get(q["id"], 1) * p
                weight += 4.0 * p
    return 1.0 if weight == 0 else round(1.0 + (total / weight) * 3.0, 3)

def _determine_level(score, niveaux):
    for k in sorted((k for k in niveaux if not k.startswith("_")), key=int):
        if score <= niveaux[k]["seuil_max"]:
            return int(k)
    return 4

def _aggregate_levels(levels, method):
    if method == "max":
        return max(levels)
    return min(max(round(sum(levels) / len(levels)), 1), 4)

def _build_axis_score(reponses, axe, ms, mc, rm):
    cfg = _load_config()
    valeur = _calculate_axis_value(reponses, axe)
    score_brut = round(min(max(valeur * ms * mc, cfg["scoring"]["score_final"]["min"]),
                           cfg["scoring"]["score_final"]["max"]), 2)
    score_net = round(min(max(score_brut * rm, cfg["scoring"]["score_final"]["min"]),
                          cfg["scoring"]["score_final"]["max"]), 2)

    niveaux = cfg["scoring"]["niveaux"]
    n_brut = _determine_level(score_brut, niveaux)
    n_net = _determine_level(score_net, niveaux)

    return {
        "score": score_net,
        "score_brut": score_brut,
        "score_valeur": valeur,
        "niveau": n_net,
        "niveau_brut": n_brut,
        "label": niveaux[str(n_net)]["label"],
        "label_brut": niveaux[str(n_brut)]["label"],
        "couleur": niveaux[str(n_net)]["couleur"],
        "couleur_brut": niveaux[str(n_brut)]["couleur"],
    }

def calculer_scores(reponses):
    cfg = _load_config()
    ms = _calculate_surface_multiplier(reponses)
    mc = _calculate_context_multiplier(reponses)
    rm = _calculate_maturity_reducer(reponses)

    scores = {
        "_mult_surface": ms,
        "_mult_contexte": mc,
        "_reducteur_maturite": rm,
    }

    axes = {k: v for k, v in cfg["scoring"]["axes"].items() if not k.startswith("_")}
    niveaux_bruts = []
    niveaux_residuels = []

    for axe in axes:
        axis_score = _build_axis_score(reponses, axe, ms, mc, rm)
        scores[axe] = axis_score
        niveaux_bruts.append(axis_score["niveau_brut"])
        niveaux_residuels.append(axis_score["niveau"])

    method = cfg["scoring"]["agregation_globale"]["methode"]
    n_brut_global = _aggregate_levels(niveaux_bruts, method)
    n_net_global = _aggregate_levels(niveaux_residuels, method)

    scores["global"] = {
        "niveau": n_net_global,
        "niveau_brut": n_brut_global,
        "label": cfg["scoring"]["niveaux"][str(n_net_global)]["label"],
        "label_brut": cfg["scoring"]["niveaux"][str(n_brut_global)]["label"],
        "couleur": cfg["scoring"]["niveaux"][str(n_net_global)]["couleur"],
        "couleur_brut": cfg["scoring"]["niveaux"][str(n_brut_global)]["couleur"],
    }

    return scores
