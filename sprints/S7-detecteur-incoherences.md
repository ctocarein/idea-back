# SPRINT 7 — Détecteur d'incohérences industrialisé · backend

> 🎯 **Objectif :** passer du banc d'essai à un outil capable de traiter un **lot réel de 30 dossiers**.
> 🧪 **Démo :** une commande, 30 dossiers réels en entrée, un JSON de constats dédupliqués en sortie —
> et les contrôles propres du corpus toujours vierges.

**Capacité backend : 27 pts.** Base de mesure : [`calibration/contradiction_corpus.json`](../calibration/contradiction_corpus.json)
· banc : [`app/scoring/contradiction_bench.py`](../app/scoring/contradiction_bench.py).

**État mesuré** (corpus 7 cas, 3 runs, modèle `mistral-small-latest`, prompt `inconsistency-v1`) :

| Version | Détections moy. | Faux positifs moy. |
|---|---|---|
| `v2cfr` — baseline gelée, clés françaises | 11,0 | 0,3 |
| `v2c` — clés anglaises, avant correctif méthode | 10,0 | 1,0 |
| `v2c` — **production actuelle** | 8,3 | **0,0** |

⚖️ **Arbitrage ouvert.** Le réglage actuel (0 faux positif) est le bon pour un produit
*automatisé*. Pour le scénario A, où un humain relit chaque constat, il est probablement TROP
strict : un faux positif coûte deux secondes au relecteur, une contradiction manquée coûte la
valeur du produit. **La sévérité devrait être un réglage, pas une constante.**

Détection pays/devise opérationnelle · ~3 appels LLM par dossier · les faux positifs restants se
concentrent sur `livraison-logistique`, types `market` et `regulatory`.

⚠️ Le « 0 faux positif » annoncé initialement provenait de **2 runs seulement** et était
partiellement chanceux : la mesure à 3 runs donne 0,3 pour la baseline. Toute annonce de
performance doit citer son nombre de runs.

## Board

### ✅ Done
- **IDX-INCOH-02 ★** Déduplication déterministe `[3]` — [`app/inconsistencies/dedup.py`](../app/inconsistencies/dedup.py). Même paire de citations ⇒ un seul constat ; type le plus **vérifiable** conservé (`arithmetic` > `temporal` > `regulatory` > `market` > `capacity` > `internal`), gravité maximale du groupe retenue, types fusionnés tracés dans `merged_types`. Tolère l'inversion A/B, la troncature et les variantes d'accent. Module pur, 17 tests hors-ligne. **Vérifié sur le cas réel** : le triple signalement de C9 s'effondre en un constat, C10 est préservée.

- **IDX-INCOH-01 ★** Promotion des prompts validés `[3]` — [`app/llm/prompt.py`](../app/llm/prompt.py) : `build_context_prompt` et `build_inconsistency_prompt`, versions figées (`context-v1`, `inconsistency-v1`), clés JSON anglicisées. Le banc **importe** ces prompts : il mesure donc la production, pas une copie. Acquis non prévus : [`verification.py`](../app/inconsistencies/verification.py) (ancrage des citations, neutralise aussi les citations hallucinées) et la baseline gelée `v2cfr`, rejouable à tout moment.
  - 📌 **Leçon** : renommer la liste `contradictions` en `findings` a triplé les faux positifs. « contradictions » contraint sémantiquement — on ne peut pas y ranger une vérification qui passe ; « findings » accueille n'importe quelle observation. **Le nom d'un champ JSON est une garde fonctionnelle.** Verrouillé par test.

- **IDX-INCOH-03 ★** Service d'orchestration `[8]` — [`app/inconsistencies/service.py`](../app/inconsistencies/service.py). `InconsistencyService.analyze()` enchaîne contexte → 2 passes parallèles → ancrage → déduplication ; `analyze_batch()` borne la concurrence et **isole les échecs par dossier**. `summarize()` produit l'en-tête du rapport (dont le décompte des dossiers propres). 15 tests hors-ligne + fumée sur 7 dossiers réels : **21 appels, 0 échec, contexte adapté** (Côte d'Ivoire, Cameroun, France, Sénégal).
- **IDX-INCOH-07** Faux positifs ramenés à **0,0** `[3]` — cause identifiée : le modèle **rendait compte de sa méthode** (« le calcul est cohérent », « ce repère ne s'applique pas au B2B ») dans la liste des constats. Correctif : toute consigne sur laquelle il peut rendre compte s'accompagne désormais d'un « et n'en dis rien ». ⚠️ Coût en rappel : 10,0 → 8,3 (cf. arbitrage ci-dessus).

### ⬜ To Do
- **IDX-INCOH-08** Sévérité réglable `[3]` — exposer un mode `strict` / `assisté` : le premier vise 0 faux positif (produit automatisé), le second privilégie le rappel (audit relu par un humain). Mesurer les deux réglages sur 3 runs.
- **IDX-INCOH-04** Ingestion de lot `[5]` — [`ingestion.py`](../app/inconsistencies/ingestion.py). CSV (séparateur sniffé, encodages `utf-8`/`cp1252`/`latin-1`, colonne du récit détectée par alias) et répertoire `.txt`/`.md` ; normalisation préservant les paragraphes ; référence anonyme stable optionnelle. **Rien ne disparaît en silence** : récit vide, trop court ou ligne mal échappée sont écartés AVEC motif.
  - 📌 Garde ajoutée après incident de test : un CSV **mal échappé** (récit contenant le séparateur, sans guillemets) tronquait le récit **en silence**. Désormais recollé si le récit est la dernière colonne, écarté avec motif sinon. Un audit facturé ne peut pas rendre moins de constats parce qu'un texte a été amputé sans que personne ne le voie.
- **IDX-INCOH-05** CLI `run_batch` `[3]` — [`run_batch.py`](../app/inconsistencies/run_batch.py). `--resume` relit la sortie et ne retraite que l'absent ou l'échoué (vérifié : 0 appel sur un lot déjà traité). Sortie JSON portant versions de prompt, modèle, contexte par dossier, constats écartés et dossiers non analysables.
- **IDX-INCOH-06** Tests `[5]` — 63 tests hors-ligne sur le domaine (dédup, ancrage, orchestration, ingestion) + corpus de non-régression.

## ⚠️ Anticipation obligatoire
Le corpus de calibration est le **garde-fou**, pas une formalité. Toute évolution de prompt se
**remesure avant promotion**. Et surtout :

> **Zéro faux positif sur les contrôles propres est un critère BLOQUANT, pas un indicateur.**
> Rater une contradiction est un manque à gagner ; en inventer une est un accident industriel.
> Une régression sur les contrôles interdit la mise en service, quel que soit le gain de rappel.

## DoD du sprint
- [x] Lot traité en une seule commande — validé de bout en bout sur un CSV réaliste (`cp1252`, séparateur `;`, colonne « Presentation du projet 2024 »).
- [x] Aucun doublon : deux constats ne partagent jamais la même paire de passages.
- [x] Contrôles propres toujours vierges — **les 2 seuls dossiers sans constat du lot sont exactement les 2 contrôles**.
- [x] Un dossier en échec n'interrompt pas le lot (testé ; un incident réseau réel s'est produit pendant le run et a été absorbé par le retry).
- [x] Coût LLM mesuré et journalisé : **3 appels par dossier** (cf. H2.3 du registre).

**Sprint 7 terminé.** Reste ouvert et non bloquant : `IDX-INCOH-08` (sévérité réglable).
