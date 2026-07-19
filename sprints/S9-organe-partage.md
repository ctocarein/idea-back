# SPRINT 9 — L'organe partagé : le détecteur nourrit le porteur · backend

> 🎯 **Objectif :** brancher le détecteur dans le flux diagnostic, pour que la chaîne de
> contradictions **déjà construite** cesse d'être alimentée par le vide.
> 🧪 **Démo :** un récit contradictoire fait chuter la confiance de la dimension concernée et
> affiche au porteur les **deux passages en conflit** ; un récit honnête n'est pas pénalisé.

**Capacité backend : 22 pts.**

## Pourquoi ce sprint coûte peu et rapporte beaucoup

Toute la chaîne aval **existe déjà et n'a jamais servi** :

| Existant | Fichier | Effet réel |
|---|---|---|
| Collecte des items `CONTRADICTION` | [`evaluation.py:97`](../app/project_memory/evaluation.py) | expose les constats |
| `needs_clarification` inclut `bool(contradictions)` | [`evaluation.py:109`](../app/project_memory/evaluation.py) | remplit `missing_information` |
| `contradiction_gap = 0.5` | [`evaluation.py:157`](../app/project_memory/evaluation.py) | **priorité des questions**, rien d'autre |
| Remontée dans `ProjectDimensionState.contradictions` | [`repository.py:119`](../app/project_memory/repository.py) | persiste l'état |

Aucun code n'écrit jamais de `ProjectMemoryItem(item_type=CONTRADICTION)`. **Le détecteur
n'était pas absent — il n'avait pas de capteur.** Ce sprint pose le capteur.

> ⚠️ **Correction d'une erreur d'analyse.** Il a d'abord été écrit ici que `contradiction_gap`
> faisait chuter la confiance de moitié, et donc que S9 réparait la non-discrimination du Radar.
> **C'est faux**, et le test `test_la_confiance_NE_depend_PAS_des_contradictions` l'épingle
> désormais. `_axis_confidence` ne lit QUE l'étendue entre passes de scoring ; `contradiction_gap`
> vit dans `select_adaptive_questions` et ne pilote que l'ordre des questions.
>
> **Conséquence : un dossier contredit conserve une confiance élevée.** Le défaut mesuré
> (96,6 % de confiance sur un dossier auto-contradictoire) **reste entier après S9.**

## Board

### ⬜ To Do
- **IDX-MEM-01 ★** Passe contexte + contradictions dans `run_diagnostic` `[5]` — ajouter au `asyncio.gather` existant ([`handlers.py:100`](../app/diagnostics/handlers.py)) : les passes sont indépendantes, **la latence reste celle d'un appel**.
- **IDX-MEM-02 ★** Persistance `ProjectMemoryItem(CONTRADICTION)` `[5]` — via le projector, avec provenance `NARRATIVE` et les deux citations en `source_excerpt` / `attributes`.
- **IDX-MEM-03** Exposition côté porteur `[5]` — contradictions visibles dans le workspace et le bilan, **toujours avec les deux passages**. Ton de coach, pas de police : « un jury verra ça en trente secondes ».
  - ⚠️ **Extension de contrat nécessaire.** La projection actuelle ne produit que `{"id", "statement"}` ([`evaluation.py:97`](../app/project_memory/evaluation.py)) — **les deux citations manquent**, alors qu'elles sont tout le produit. Il faut porter `quote_a` / `quote_b` jusqu'à `DimensionEvaluationOut.contradictions`, et prévenir le front : c'est un ajout de champs, pas une rupture.
- **IDX-MEM-04** Tolérance `[2]` — l'échec de la passe contradictions ne fait **pas** tomber le diagnostic ; même politique que les passes de scoring (`return_exceptions=True`).
- **IDX-MEM-05** Tests `[5]` — récit contradictoire connu ⇒ confiance abaissée et contradictions présentes ; **récit propre ⇒ strictement inchangé** (protection contre le faux positif côté porteur, où il coûte la confiance de l'utilisateur).

## ⚠️ Anticipation obligatoire
**Aucune migration n'est attendue.** `ProjectMemoryItem`, `MemoryItemType.CONTRADICTION`,
`EvidenceState` et `ProjectDimensionState.contradictions` existent déjà en base (migration
`0020_project_memory`). Vérifier avant de créer une `0021` — le réflexe serait de dupliquer
un modèle qui est déjà là.

Règle de conception : **on alimente la chaîne existante, on ne la réécrit pas.** Si un
comportement semble manquer, relire `evaluation.py` avant d'ajouter du code.

## DoD du sprint
- [x] Les contradictions détectées sont persistées en mémoire projet, sans doublon au re-scoring.
- [x] Le porteur voit les deux passages en conflit, cités mot pour mot (extension de contrat livrée).
- [x] Une dimension contredite réclame une clarification et **passe en tête des questions adaptatives** — effet mesuré, pas supposé.
- [x] Un dossier honnête n'est pas pénalisé (aucun faux positif côté porteur).
- [x] La chaîne existante n'a pas été réécrite, seulement alimentée.
- [x] Un échec de la passe contradictions laisse le diagnostic aboutir.

### ⬜ Suite directe
- **IDX-MEM-06** Décider si une contradiction doit peser sur la confiance `[3]` — aujourd'hui elle
  ne pèse pas, et le Radar reste donc non discriminant. Deux options : (a) **assumer** — la V2 §9
  veut score, confiance et contradictions comme signaux *séparés*, et mélanger les deux brouille
  le sens de « confiance » (= accord entre passes) ; (b) **plafonner** la confiance d'une dimension
  contredite (`min(confidence, 0.5)`), au motif qu'on ne peut pas être sûr d'un axe dont les
  affirmations se contredisent. **(b) change une valeur déjà exposée au front** : à mesurer et à
  annoncer, jamais à glisser en douce.

---

## 🚫 Hors périmètre — bloqué sous condition

Ces chantiers **ne démarrent pas** tant que le feu vert correspondant n'est pas obtenu.
Ils sont listés ici pour qu'aucun ne se lance un soir de motivation.

| Chantier | Feu vert requis |
|---|---|
| Couche institutionnelle (organisations, programmes, cohortes, file d'exceptions) | Un client payant, et H1.1 ∧ H3.1 ∧ H2.1 au vert |
| Entitlements, quotas, intégration de paiement | H4.1 ∧ H4.2 au vert (intention d'achat mesurée, puis encaissement réel) |
| Multi-projet côté porteur | H4.1 au vert — le back le supporte déjà, seul le signal manque |
| Migration du golden set, calibration experte (H0.2 / H0.3) | L'audit a prouvé que le tri est bien la douleur |
| Correctif température / ensemble du scoring | Après S9 — la chute de confiance par contradiction traite déjà une partie du symptôme |

Registre complet des hypothèses et de leurs seuils de mort : voir l'artefact « Registre
d'hypothèses Ideaxion ».
