# GRILLE RADAR v2 — spec & gabarit (à remplir en atelier)

**Référentiel d'évaluation du diagnostic — 4 piliers × 3 dimensions = 12 dimensions, notées /10.**
Document de cadrage. *Aucune implémentation ici* : c'est la matière qui alimentera `scoring_grids`
(grille versionnée `v2`). Le moteur (`app/scoring/engine.py`) est déjà piloté par la grille → adopter
v2 = **bump de version + remplissage**, pas une réécriture.

> Statut : structure + questions centrales **figées** (ateliers) ; **ancres et poids à compléter**.

---

## 1. Structure

Score global **/10** = agrégation pondérée des 12 dimensions. Chaque pilier porte une **question
directrice** ; chaque dimension une **question centrale** (ce que l'IA évalue, ce que l'humain affine).

| Pilier | Question directrice | Dimensions |
| :--- | :--- | :--- |
| **P1 · SENS DU PROJET** | Le projet répond-il à un vrai problème avec une solution pertinente ? | D1, D2, D3 |
| **P2 · VIABILITÉ** | Le projet peut-il tenir économiquement ? | D4, D5, D6 |
| **P3 · SCALABILITÉ** | Le projet peut-il grandir sans se casser ? | D7, D8, D9 |
| **P4 · EXÉCUTION** | L'équipe peut-elle exécuter et livrer ? | D10, D11, D12 |

## 2. Les 12 dimensions (codes + questions centrales)

| Code | Dimension | Pilier | Question centrale |
| :--- | :--- | :--- | :--- |
| **D1** | Problème | SENS | Le problème est-il réel, intense, fréquent, et conscient ? |
| **D2** | Solution | SENS | La solution résout-elle le problème de façon crédible et faisable ? |
| **D3** | Proposition de valeur | SENS | La promesse est-elle claire, différenciante et mémorisable ? |
| **D4** | Marché | VIABILITÉ | Le marché est-il assez grand, en croissance, et accessible ? |
| **D5** | Concurrence & Benchmark | VIABILITÉ | Le paysage concurrentiel est-il connu et l'avantage est-il défendable ? |
| **D6** | Modèle économique | VIABILITÉ | Les revenus sont-ils crédibles, récurrents, et la marge est-elle saine ? |
| **D7** | Traction & Preuves | SCALABILITÉ | Y a-t-il des signaux clients, des revenus, des témoignages ? |
| **D8** | Potentiel de croissance | SCALABILITÉ | Le modèle peut-il scaler sans proportionner les coûts ? |
| **D9** | Stratégie Go-to-Market | SCALABILITÉ | Le plan d'acquisition client est-il clair, réaliste et financé ? |
| **D10** | Équipe & Compétences | EXÉCUTION | Les fondateurs ont-ils la légitimité, la complémentarité et la résilience ? |
| **D11** | Niveau d'avancement | EXÉCUTION | Où en est le projet concrètement ? Qu'est-ce qui est fait ? Qu'est-ce qui manque ? |
| **D12** | Risques & Freins | EXÉCUTION | Les risques majeurs sont-ils identifiés et un plan de mitigation existe-t-il ? |

---

## 3. Mapping v1 → v2 (continuité)

| v1 (6 axes / 3 lentilles, /100) | v2 (12 dims / 4 piliers, /10) |
| :--- | :--- |
| essence: probleme, valeur | **SENS** : D1 Problème, **D2 Solution (nouveau)**, D3 Proposition de valeur |
| viabilite: marche, modele | **VIABILITÉ** : D4 Marché, **D5 Concurrence & Benchmark (était un *insight*)**, D6 Modèle éco |
| scalabilite: equipe, croissance | **SCALABILITÉ** : **D7 Traction (était insight)**, D8 Potentiel de croissance, **D9 GTM (nouveau)** |
| — | **EXÉCUTION (pilier nouveau)** : D10 Équipe, **D11 Avancement (était insight)**, **D12 Risques (était insight)** |

**Conséquence couche « insights »** : benchmark/concurrence (→D5), traction (→D7), avancement (→D11),
risques (→D12) **deviennent des dimensions notées** (note + justification courte). La couche narrative
se **réduit** au **résumé**, aux **forces transverses** et aux **recommandations**.

`project.stage` (auto-déclaré à l'onboarding) recoupe **D11** : décider lequel fait foi (proposé :
`stage` = déclaratif porteur ; **D11** = évaluation, fait foi pour le score).

---

## 4. Décisions à trancher (avant implémentation v2)

1. **Échelle** : note **/10**. Interne en `0-10` entier, ou `0-100` affiché `/10`, ou `0-10` à 1 décimale ?
   *(Reco : stocker en `0-10` entier par dimension ; global `/10` à 1 décimale.)*
2. **Pondération** : poids **par dimension** et/ou **par pilier**, **modulés par catégorie** (`category_weights`
   existe déjà). *(Reco : poids par dimension, surcharge par catégorie ; piliers = moyenne de leurs 3 dims.)*
3. **Score global** : moyenne pondérée des 12 dims → `/10`. Confirmer la formule.
4. **Ancres ×12** : rubrique 4 paliers par dimension (cf. §5) — **le vrai travail d'atelier**.
5. **Contrat front** : 6 axes/3 lentilles → 4 piliers/12 dims. Réalignement front (types OpenAPI) à planifier.
6. **Robustesse** : ensemble (N passes), validation stricte, ScoreRun, golden set → **inchangés**, mais le
   golden set devra être renoté sur 12 dims /10.

---

## 5. Décisions arbitrées (suite au mockup de rapport)

- **Échelle** : note **/10 entière** par dimension ; agrégats (pilier, global) **/10 à 1 décimale**.
- **Paliers d'ancres** : 4 niveaux couvrant 0-10 → **0-3 / 4-6 / 7-8 / 9-10** (contigus).
- **Bandes d'affichage** (3 couleurs, distinctes des ancres) : **Faible 0-4** (rouge) · **Moyen 5-7** (ambre)
  · **Fort 8-10** (vert/teal). *(Le mockup montre 7,5 = Fort ; seuil exact à confirmer en atelier.)*
- **Identité** : structure du mockup, **couleurs charte « Aube »** (indigo/corail/gold/teal) ;
  la charte évoluera pour formaliser ce style « document » (cf. `RAPPORT_PREDIAGNOSTIC.md`).

## 5bis. Ancres — PREMIÈRE PROPOSITION (à valider en atelier)

Dérivées des questions centrales. Format par dimension : `0-3 · 4-6 · 7-8 · 9-10`.

| Dim | 0-3 (faible) | 4-6 (moyen) | 7-8 (bon) | 9-10 (excellent) |
| :--- | :--- | :--- | :--- | :--- |
| **D1** Problème | Supposé, rare ou non prouvé | Réel mais ponctuel / peu conscient | Réel, fréquent, cible claire | Douleur aiguë, fréquente, reconnue |
| **D2** Solution | Floue ou non faisable | Plausible, faisabilité non démontrée | Crédible et faisable | Éprouvée, adéquation claire |
| **D3** Prop. de valeur | Confuse / indifférenciée | Claire mais peu différenciante | Claire et différenciante | Nette, différenciante, mémorable |
| **D4** Marché | Indéfini ou trop étroit | Identifié, accès difficile/stagnant | Significatif, en croissance, accessible | Grand, en croissance, accès prouvé |
| **D5** Concurrence & Benchmark | Ignorée / avantage inexistant | Partiellement connue, avantage fragile | Maîtrisée, avantage réel | Cartographiée, avantage défendable |
| **D6** Modèle économique | Absent / irréaliste | Plausible, unit economics non prouvées | Revenus crédibles, marge raisonnable | Récurrents prouvés, marge saine |
| **D7** Traction & Preuves | Aucune preuve (théorique) | Signaux faibles (intérêt déclaré) | Premiers clients/revenus / usage réel | Traction mesurable et croissante |
| **D8** Potentiel de croissance | Non scalable (coûts proportionnels) | Scalabilité limitée/coûteuse | Bon levier de scalabilité | Forte scalabilité / effet réseau |
| **D9** Stratégie GTM | Aucun plan d'acquisition | Vague ou non chiffré | Clair et réaliste | Chiffré, financé, amorcé |
| **D10** Équipe & Compétences | Compétences clés manquantes | Partielle / peu complémentaire | Crédible et complémentaire | Complète, légitime, éprouvée |
| **D11** Niveau d'avancement | Idée sur le papier | Prototype/MVP en cours | Produit lancé, premiers usages | En marché avec traction établie |
| **D12** Risques & Freins | Ignorés ou niés | Partiellement identifiés, sans plan | Identifiés, mitigation amorcée | Majeurs identifiés + plan crédible |

> **D12 note le LUCIDITÉ** (risques identifiés + plan), pas l'absence de risque : un projet conscient
> de ses risques avec un plan score haut, même s'il en a beaucoup.

## 5ter. Sous-questions guidantes — PROPOSITION (à valider)

Ce que l'IA cherche / ce qu'on peut demander au porteur, par dimension.

| Dim | Sous-questions guidantes |
| :--- | :--- |
| **D1** Problème | Qui vit ce problème, à quelle fréquence ? · Quelle preuve qu'il est ressenti (pas supposé) ? |
| **D2** Solution | Comment résout-elle concrètement le problème ? · Est-elle techniquement/opérationnellement faisable ? |
| **D3** Prop. de valeur | Quelle promesse unique en une phrase ? · En quoi diffère-t-elle des alternatives ? |
| **D4** Marché | Taille et croissance du marché cible ? · Le segment initial est-il accessible ? |
| **D5** Concurrence & Benchmark | Qui sont les concurrents directs/indirects ? · Quel avantage défendable (barrière) ? |
| **D6** Modèle économique | Comment et combien facture-t-il ? · Marges et récurrence crédibles ? |
| **D7** Traction & Preuves | Quels signaux réels (clients, revenus, usage, témoignages) ? · Mesurables et croissants ? |
| **D8** Potentiel de croissance | Les coûts croissent-ils moins vite que les revenus ? · Quels leviers (effet réseau, automatisation) ? |
| **D9** Stratégie GTM | Par quels canaux acquérir les 1ers clients ? · Coût d'acquisition connu et finançable ? |
| **D10** Équipe & Compétences | Les compétences clés sont-elles couvertes ? · Complémentarité et résilience dans la durée ? |
| **D11** Niveau d'avancement | Qu'est-ce qui est réellement fait/lancé ? · Qu'est-ce qui manque pour l'étape suivante ? |
| **D12** Risques & Freins | Quels sont les 3 risques majeurs ? · Existe-t-il un plan de mitigation par risque ? |

## 5quater. Poids par catégorie — PROPOSITION (à valider)

Tout poids non listé = **1.0**. Idée : survaloriser ce qui fait/défait un projet *dans son secteur*.

| Catégorie | Dimensions survalorisées (poids) |
| :--- | :--- |
| **fintech** | D6 Modèle éco ×1.5 · D12 Risques ×1.3 · D5 Concurrence ×1.2 *(régulation, confiance, monétisation)* |
| **agritech** | D7 Traction ×1.3 · D4 Marché ×1.2 · D9 GTM ×1.2 *(terrain, accès producteurs)* |
| **edtech** | D7 Traction ×1.3 · D3 Valeur ×1.2 · D8 Croissance ×1.2 *(engagement, rétention)* |
| **sante** | D12 Risques ×1.4 · D10 Équipe ×1.3 · D2 Solution ×1.2 *(faisabilité, conformité)* |
| **commerce** | D6 Modèle éco ×1.3 · D7 Traction ×1.2 · D9 GTM ×1.2 *(unit economics, exécution)* |
| **autre** | — (poids égaux) |

> Toutes les valeurs de §5bis/5ter/5quater sont une **première passe** : elles donnent une base de
> travail concrète à l'atelier, qui les challenge et les fige.

---

## 6. Forme cible dans `scoring_grids` (pour mémoire, non implémenté)

```jsonc
{
  "version": "v2",
  "scale_max": 10,
  "pillars": [
    { "key": "sens", "label": "Sens du projet", "question": "…répond-il à un vrai problème… ?" }
    // viabilite, scalabilite, execution
  ],
  "axes": [
    {
      "key": "d1", "label": "Problème", "pillar": "sens",
      "central_question": "Le problème est-il réel, intense, fréquent, et conscient ?",
      "guiding_questions": ["…"],
      "anchors": [ { "min": 0, "max": 3, "label": "…" }, … ]   // sur /10
    }
    // d2 … d12
  ],
  "category_weights": { "fintech": { "d6": 1.5, "d5": 1.2 }, … }
}
```

Changements de schéma vs v1 : champ de groupement `lens` → `pillar` (4 au lieu de 3), ajout
`central_question`, `scale_max=10`. Le reste (ancres, poids, agrégation) est déjà supporté.

---

*Gabarit grille Radar v2 — à compléter en atelier réseau, puis seedé comme `scoring_grids` version `v2`.*
*Confidentiel — Ideaxion.*
