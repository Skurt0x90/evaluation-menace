# Cyber Threat Assessment

Outil d'appréciation rapide de la menace cyber basé sur une méthode multiplicative à trois blocs. Axes Vol de données / Sabotage / Réputation.

Toute la connaissance est externalisée dans des fichiers JSON — questions, poids, seuils, acteurs CTI — modifiables sans toucher au code.

---

## Principe de la méthode

```
Score(axe) = Valeur_cible × Mult_surface × Mult_contexte
```

| Composante | Plage | Rôle |
|---|---|---|
| **Mult_surface** | [0.1 – 1.0] | Gate keeper — un système isolé (air-gap) écrase le score final quelle que soit la valeur de la cible |
| **Valeur_cible** | [1.0 – 4.0] | Score intrinsèque par axe — attractivité pour un adversaire |
| **Mult_contexte** | [0.8 – 1.2] | Nuance conjoncturelle — amplifie ou atténue sans créer de menace |

Le niveau global est calculé par **maximum conservateur** des trois axes.

Les niveaux de sortie : `FAIBLE` / `MODÉRÉ` / `ÉLEVÉ` / `CRITIQUE`

> Références méthodologiques : EBIOS Risk Manager (ANSSI 2018), Diamond Model (Caltagirone et al.), MITRE ATT&CK

---

## Structure du projet

```
threat-assessment/
├── app.py                      
├── static/
│   └── style.css              
├── templates/
│   ├── index.html
│   ├── questionnaire.html
│   └── resultats.html
├── config/                     # Tout ce qui est modifiable sans toucher au code
│   ├── questions.json          # Blocs A/B/C, textes, options, poids par axe
│   ├── weights.json            # Poids surface et contexte
│   ├── scoring.json            # Seuils niveaux, plages multiplicateurs, agrégation
│   ├── knowledge_base.json     # Acteurs CTI, TTPs, incidents de référence
│   └── examples.json          # Exemples préconfigurés
└── reports/                    # Rapports PDF générés (créé automatiquement)
```

---

## Installation

```bash
git clone https://github.com/votre-username/threat-assessment
cd threat-assessment

pip install flask reportlab

python app.py
```

Ouvre automatiquement `http://localhost:5000` dans le navigateur.

Le serveur bind sur `127.0.0.1` uniquement — inaccessible depuis le réseau.

---


## Entreprise (`threat_enterprise/`)

| Axe | Ce qu'il mesure |
|---|---|
| 🔍 Vol de données | Exfiltration de propriété intellectuelle, données clients, secrets commerciaux |
| ⚡ Sabotage | Ransomware, interruption de service, destruction de données |
| 📡 Réputation | Leak, bad buzz orchestré, atteinte à l'image |

Questions orientées SI d'entreprise : criticité métier, conformité NIS2/PCI-DSS/OIV, interconnexions supply chain, exposition concurrentielle, profil C-level.

Acteurs CTI : LockBit, Cl0p, BlackCat, APT10, APT28, Sandworm, KillNet.

**Exemples inclus :** PME de services locaux → `FAIBLE` / ESN fournisseur IT secteurs critiques → `CRITIQUE`

---

## Modifier la méthode sans coder

Tout se passe dans `config/`. Aucun redémarrage requis — les fichiers sont relus à chaque requête.

### Changer les questions ou les libellés

`config/questions.json`

```json
{
  "id": "sa_connectivite",
  "texte": "Quel est le niveau de connectivité réseau ?",
  "aide": "Accès internet, VPN, services exposés...",
  "options": [
    {"valeur": 1, "label": "Air-gap total"},
    {"valeur": 4, "label": "Fortement exposé"}
  ]
}
```

### Ajuster les poids

`config/weights.json` — modifier les valeurs numériques. La connectivité réseau pèse 50% dans le multiplicateur surface par défaut, car c'est la variable la plus discriminante.

### Recalibrer les seuils

`config/scoring.json` — changer `seuil_max` pour déplacer la frontière entre niveaux. Passer l'agrégation de `"max"` à `"moyenne"` si une approche moins conservatrice est souhaitée.

### Mettre à jour les acteurs CTI

`config/knowledge_base.json` — ajouter un groupe :

```json
"NouvelActeur": {
  "nom_complet": "Nom complet",
  "origine": "Pays — agence",
  "tier": 1,
  "type": "apt",
  "finalites": ["espionnage"],
  "secteurs_cibles": ["défense", "énergie"],
  "ttps_labels": ["Spear-phishing", "C2 HTTP/S"],
  "incidents_notables": ["Incident 2024"],
  "actif": true
}
```

---

## Ce que la méthode couvre et ne couvre pas

| ✓ Couvert | ✗ Hors périmètre |
|---|---|
| Vraisemblance de la menace par finalité adversariale | Analyse d'impact opérationnel ou financier |
| Différenciation fine entre périmètres selon leur exposition réelle | Risque résiduel post-mesures de sécurité |
| Contexte géopolitique comme nuance (pas comme source) | Homologation RGS / IGI 1300 |
| Identification des acteurs CTI pertinents | Substitution à un flux CTI gouvernemental (ANSSI/SGDSN) |
| Export PDF reproductible et archivable | Audit de sécurité ou test d'intrusion |

---

## Licence

MIT — libre d'utilisation, de modification et de redistribution.
