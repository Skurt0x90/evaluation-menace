from models.config import load

def acteurs_pertinents(reponses, scores):
    kb      = load("knowledge_base.json")
    scoring = load("scoring.json")
    axes    = {k: v for k, v in scoring["axes"].items() if not k.startswith("_")}

    # liste les acteurs si l'axe (sabotage, vol de données, espionnage) > 2 sinon pas pertinent
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
