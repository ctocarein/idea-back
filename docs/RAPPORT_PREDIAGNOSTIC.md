# RAPPORT DE PRÉ-DIAGNOSTIC — contrat de sortie

**Le livrable du diagnostic gratuit (segment « comprendre »). 3 pages, généré par le moteur
« I.D.E.A », noté sur la grille Radar v2 (12 dimensions).** Document de cadrage — *pas de code*.

> Dérivé du mockup `deepseek_…html`. La grille (12 dims, /10) vit dans `GRILLE_RADAR_V2.md`.
> Deux couches : **les 12 scores = cœur robuste** (ensemble, ancres, ScoreRun) ; **tout le reste =
> couche structurée best-effort, affinée par l'humain** (analyste).

---

## 1. Identité & design

- **Moteur** : « I.D.E.A » — *Intelligence Diagnostic Engine Assistant*. Tagline : *Ideaxion = Idée + (Action × Exécution)*.
- **Structure** : reprise du mockup (cover · analyse · verdict). **Couleurs : charte « Aube »** (décision : structure mockup + palette Aube, la charte évoluera pour formaliser ce style « document »).

**Recoloration mockup → tokens Aube** (`CHARTE_FRONTEND.md`) :

| Mockup | → Token Aube |
| :--- | :--- |
| navy `#1E3A5F` (primary) | `--ink` `#1C1633` (titres, header) |
| amber `#F59E0B` (accent) | `--gold` `#F4B740` |
| green `#10B981` (Fort) | `--teal` `#1FB0A0` |
| orange `#F97316` (Moyen) | `--gold` `#F4B740` |
| red `#EF4444` (Faible) | `--danger` `#E0473B` |
| — (sceau / signature) | dégradé `--dawn` (corail→gold), **réservé au sceau/Radar** |

Action/accent ponctuel = `--coral`. Le dégradé d'aube reste rare (en-tête/sceau).

---

## 2. Structure (3 pages)

1. **Couverture** : logo, nom du projet, porteur, méta (date · secteur · stade · montant recherché), pied « I.D.E.A · non contractuel ».
2. **Analyse** : description (problème/solution/client/modèle) · **Radar 12 axes** (score /10, niveau, barre) · **score global /10** + label verdict · **forces** · **risques** (matrice).
3. **Verdict & reco** : **paysage concurrentiel** · **niveau d'avancement** (métriques) · **verdict I.D.E.A** (statut + analyse) · **recommandations priorisées** · **prochaines étapes** · mentions RGPD.

---

## 3. Modèle de données du rapport (le contrat)

Ce que le diagnostic doit produire (et stocker sur `Report`). `[SCORÉ]` = cœur robuste ;
`[STRUCTURÉ]` = couche qualitative best-effort (affinable analyste).

```jsonc
{
  "meta": {                                  // connu / saisi
    "project_title": "…", "founder": "…", "date": "JJ/MM/AAAA",
    "sector": "fintech", "stage": "prototype", "funding_sought": 8000000
  },

  "description": {                           // [STRUCTURÉ] extrait IA de la saisie porteur
    "problem": "…", "solution": "…", "target_client": "…", "business_model": "…"
  },

  "radar": {                                 // [SCORÉ] grille v2 — cœur robuste
    "grid_version": "v2", "scale_max": 10,
    "dimensions": { "d1": 8, "d2": 7, "...": "…", "d12": 6 },   // /10
    "pillars": { "sens": 8.0, "viabilite": 7.3, "scalabilite": 6.2, "execution": 5.7 },
    "global": 6.8,                           // /10, 1 décimale
    "verdict_level": "Potentiel sous conditions"   // échelle de label (cf. §4)
  },

  "strengths": [ { "text": "…", "dimension": "d3" } ],            // [STRUCTURÉ]

  "risks": [                                 // [STRUCTURÉ] MATRICE prob × gravité
    { "text": "…", "probability": "high|medium|low", "severity": "critical|high|medium|low" }
  ],

  "competition": [                           // [STRUCTURÉ] table concurrents
    { "name": "…", "type": "direct|indirect", "description": "…", "threat": "high|medium|low" }
  ],

  "progress": {                              // [STRUCTURÉ] métriques d'avancement
    "stage": "…", "team_size": 3, "customers": 12, "revenue": 0, "funding": 0
  },

  "verdict": {                               // [STRUCTURÉ]
    "status": "go|conditional|nogo",         // 🟢 / 🟡 / 🔴
    "label": "Projet à potentiel sous conditions",
    "analysis": "<6-8 lignes, factuel et équilibré>"
  },

  "recommendations": [                       // [STRUCTURÉ] PRIORISÉES
    { "priority": 1, "title": "…", "description": "…" }
  ],

  "next_steps": [                            // [STRUCTURÉ]
    { "deadline": "1 semaine", "action": "…" }
  ],

  "mentions": {                              // légal
    "engine": "I.D.E.A", "model": "<deepseek/mistral réel>", "non_contractual": true,
    "rgpd_contact": "rgpd@ideaxion.com"
  }
}
```

> ⚠️ La mention « modèle » doit refléter le **vrai** provider (DeepSeek/Mistral — coût/résidence),
> pas « GPT-4o » comme dans le mockup.

---

## 4. Échelles & labels

- **Dimension** : 0-10 entier. Bandes d'affichage : **Faible 0-4** (`--danger`) · **Moyen 5-7** (`--gold`) · **Fort 8-10** (`--teal`). *(seuil Fort à confirmer : mockup montre 7,5.)*
- **Global** : /10 à 1 décimale, + **label verdict** (échelle à valider en atelier) :
  `0-3,9` → Non viable en l'état · `4-6,4` → Fragile, à retravailler · `6,5-7,9` → Potentiel sous conditions · `8-10` → Prometteur.
- **Risques** : probabilité ∈ {élevée, moyenne, faible} × gravité ∈ {critique, élevée, moyenne, faible}.

---

## 5. Régime de fiabilité (cohérence avec la robustesse)

| Bloc | Régime | Production |
| :--- | :--- | :--- |
| 12 scores + agrégats | **robuste** | grille ancrée → N passes → consensus → validation stricte → ScoreRun |
| description, forces, risques, concurrence, avancement, verdict, recos, next steps | **best-effort** | appel(s) LLM dédié(s), schéma tolérant, **affiné par l'analyste** |

Dégradation : la couche structurée peut manquer (LLM partiel) sans empêcher le bilan scoré.
L'analyste édite/valide la couche structurée (futur `PATCH …/insights`, `source=human`, audité).

---

## 6. Implications (pour quand on codera)

1. **Grille v2** seedée (`scoring_grids` version `v2`, 12 dims ancrées, `scale_max=10`, champ `pillar`).
2. **Report enrichi** : étendre le schéma `DiagnosticInsights` → `DiagnosticReport` (description, risks-matrix, competition, progress, verdict, recommendations[priorité], next_steps).
3. **Prompts** : un prompt scoring (12 dims) + un prompt rapport (couche structurée) — versionnés.
4. **PDF** : template 3 pages recoloré Aube (le mien actuel = base à enrichir).
5. **Front** : réalignement 6 axes/3 lentilles → 12 dims/4 piliers (types OpenAPI).
6. **Charte** : ajouter le style « document/rapport » à `CHARTE_FRONTEND.md` (décision d'évolution).

*Contrat de pré-diagnostic — à valider, puis implémenter en grille v2. Confidentiel — Ideaxion.*
