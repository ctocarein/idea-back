# SPEC BACKEND — Pitch Simulator « Le Comité » (Sprint 4)

> Contrat backend du simulateur de pitch. Traduit l'UX V2.0 (comité virtuel multi-personnalités,
> imprévus, double évaluation, post-mortem) en API. **Figé avant code.** Le front anime ; le backend
> fournit les données, le scoring et le post-mortem.

Voir aussi : [GRILLE_RADAR_V2.md](GRILLE_RADAR_V2.md) (le scoring dont on réutilise la robustesse),
[RAPPORT_PREDIAGNOSTIC.md](RAPPORT_PREDIAGNOSTIC.md) (report + PDF réutilisés pour le post-mortem),
[BACKLOG.md](BACKLOG.md).

---

## 1. Principes directeurs (non négociables)

1. **Fond = credential / Forme = coaching.** Le score **Fond** (contenu, grille ancrée, `PitchRun`
   rejouable) est *le credential portable* opposable à un jury/incubateur. Le score **Forme**
   (délivrance) est une couche **expérientielle/coaching**, étiquetée « indicatif », **jamais** le
   credential. Architecturalement séparés. Cf. [[vision-actif-strategique]].
2. **RGPD & biométrie.** L'analyse d'émotion vocale / posture / regard = **données biométriques** →
   consentement explicite, minimisation, rétention courte, et **étiquetée « indice » et non verdict**
   (la reconnaissance d'émotion est scientifiquement contestée). **Hors MVP** (Mode Caméra = Premium).
3. **Déterministe + LLM.** Comme le scoring : cœur déterministe robuste (grille ancrée, proxies de
   Forme calculés) + couche LLM (jugement de contenu, questions des juges). Provider **bon marché**
   + **mock déterministe** pour dev/tests.
4. **Le coût suit le revenu.** Gratuit = **texte, Mode Slides, tour-par-tour** (cheap). Audio
   (Whisper), realtime (TTS/WebRTC), Mode Caméra (biométrie) = **derrière le paywall**.
5. **Le porteur reste l'auteur.** Le simulateur évalue, questionne, donne structure et exemples ; il
   **ne rédige pas** le pitch. Même garde-fou que l'Academy.

---

## 2. Périmètre par couches

| Couche | Contenu | Sprint |
| :-- | :-- | :-- |
| **4A — « Le Comité »** ✅ | Mode Slides **texte**, tour-par-tour : comités+personas, parsing deck, slides typées, narration→réactions, imprévus (config), score **Fond** + **Forme-texte**, **post-mortem + PDF**, progression | **S4 (livré)** |
| **PITCH-06 — « Comité silencieux »** | Refonte de l'orchestration vers le **modèle canonique** (§14) : phases, prise de parole ordonnée, expert métier, questions variées, tour libre, délibération verbatim | **prochain (texte)** |
| **4B — « La Voix »** | Upload audio (DOC-01) → Whisper (seam STT + mock) → métriques de délivrance déterministes (débit, tics, timing) → Forme défendable | Premium |
| **V2 — « La Salle »** | Realtime WebRTC + voix TTS par juge + **Mode Caméra** (Hume/MediaPipe) RGPD-gated + replay vidéo | V2 (épic séparée) |

> ⚠️ **4A livré avec le modèle « interruption pendant le pitch »** (PITCH-03). Le **§14 (comité
> silencieux)** est désormais **canonique** et le remplace — voir la machine à phases et l'orchestrateur.
> §3-9 décrivent le socle 4A (toujours valable : scoring, deck, post-mortem) ; §14 décrit l'interaction cible.

---

## 3. Machine à états de la session

```
CONFIGURED ──start──> IN_PROGRESS ──finish──> DELIBERATING ──(job)──> COMPLETED
                          │                                              
                          └────────────── abandon ──────────────> ABANDONED (terminal)
```

- `IN_PROGRESS` couvre pitch ↔ questions/imprévus (le front pilote les tours).
- `DELIBERATING` : `finish` déclenche un **job async** (délibération + scoring), comme le diagnostic.
- `COMPLETED` : `PitchRun` + post-mortem disponibles. Aucune transition implicite ; saut illégal → 422.

---

## 4. Modèle de données

```python
# Constantes (comme la grille) — pas en base au MVP
PitchCommittee:  key (incubateur|concours|investisseur), label,
                 personas: [{name, role, personality, style, obsession_axis}]

# Versionné, ancré — MÊME robustesse que ScoringGrid
PitchRubric:     version, is_active, scale_max=10, axes[ {key, label, kind: fond|forme|bio,
                 source: llm|deterministic|biometric, central_question, anchors[] , weight} ]

PitchDeck:       id, owner_id, project_id?, title, created_at
PitchSlide:      id, deck_id, kind: main|backup|synthesis, position, title,
                 extracted_text, image_key?  # texte extrait du PDF/PPTX (parsing)

PitchSession:    id, owner_id, project_id?, committee_key, mode: slides|camera,
                 rubric_version, config: {imprevus:bool, hard_questions:bool, silence:bool,
                 duration_min:int}, status, started_at, finished_at

PitchTurn:       id, session_id, t_offset_s, actor: porteur|<juge_name>|systeme,
                 type: narration|question|interruption|imprevu|answer|slide_shown|deliberation,
                 content, slide_id?, meta(jsonb)     # ← LA timeline du post-mortem

PitchRun:        id, session_id, rubric_version, source: llm|human|replay,
                 fond_scores{axis:0-10}, forme_scores{axis:0-10},
                 overall_fond, overall_forme, overall_global,
                 strengths[], weaknesses[], jury_questions[], confidence, needs_review
```

Tables nouvelles : `pitch_decks`, `pitch_slides`, `pitch_sessions`, `pitch_turns`, `pitch_runs`,
`pitch_rubrics`. (Migration : baseline `create_all` régénérée, comme S3.)

---

## 5. Comités & personas (placeholder v1, affiné en atelier)

### Comité Incubateur (4 juges)
| Juge | Personnalité | Obsession (axe) | Style |
| :-- | :-- | :-- | :-- |
| Mme Diallo | Directrice, visionnaire | Impact / mission / équipe | Encourageante, exigeante sur le fond |
| M. Morel | Serial entrepreneur, cynique | Faisabilité / marché | Déstabilise, coupe la parole |
| Mme Chen | Experte financière | Business model / chiffres | Froide, exige des preuves |
| M. Koné | Investisseur impatient | Croissance / traction | Veut l'essentiel, coupe le blabla |

### Comité Concours (3 experts)
Expert Innovation (problème/solution) · Expert Marché (marché/concurrence) · Expert Impact (équipe/mission).

### Comité Investisseur (2 VC + 1 Business Angel)
VC Growth (scalabilité/traction) · VC Deeptech (différenciation/défensibilité) · Business Angel (équipe/exécution).

> Chaque persona porte une **obsession = un axe du radar**. C'est le lien entre **faiblesse détectée
> et juge qui attaque** (§7).

---

## 6. Les 10 axes du Radar de Pitch

| # | Axe | Famille | Source | MVP 4A |
| :-- | :-- | :-- | :-- | :-- |
| 1 | Clarté du problème | Fond | LLM | ✅ |
| 2 | Solution | Fond | LLM | ✅ |
| 3 | Marché (chiffres crédibles) | Fond | LLM | ✅ |
| 4 | Business model | Fond | LLM | ✅ |
| 5 | Traction / preuves | Fond | LLM | ✅ |
| 6 | Équipe | Fond | LLM | ✅ |
| 7 | Gestion des questions | Fond | LLM | ✅ |
| 8 | Résilience sous pression | Fond | LLM (+ Hume en V2) | ✅ (texte) |
| 9 | Impact émotionnel (ton/voix) | **Forme/bio** | Hume AI | ⛔ → Premium/V2 |
| 10 | Posture & regard | **Forme/bio** | MediaPipe | ⛔ → V2 (caméra) |

**MVP = 8/10 axes Fond.** Les 2 axes biométriques renvoient `null` avec mention « Mode Caméra (Premium) ».
Chaque axe a des **paliers ancrés** (0-2 / 3-5 / 6-8 / 9-10) — placeholder v1 dans `constants.py`.

---

## 7. Scoring : Fond, Forme, et le moteur de scénario

### 7.1 Fond (LLM, ancré, robuste)
À `finish` : on assemble le **transcript** (narrations + réponses, issus des `PitchTurn`) + le **texte
des slides** → prompt ancré → score /10 par axe Fond. **`PitchRun` rejouable** (rubric_version,
provider stockés). Réutilise la machinerie `app/scoring` (validation, ensemble optionnel).

### 7.2 Forme-texte (déterministe, défendable, « indicatif »)
Calculée sur le transcript, **sans biométrie** :
- **concision** : longueur vs `duration_min` cible ;
- **tics / hésitations** : compte de mots de remplissage (« euh », « en fait », « du coup »…) ;
- **complétude des réponses** : réponse aux questions des juges vs esquive ;
- **structure** : présence problème→solution→marché→ask.

### 7.3 Moteur de scénario (imprévus NON aléatoires)
Cœur de l'innovation : **les imprévus sont déclenchés par les faiblesses détectées**.
- Pendant les tours, chaque `narration` de slide est **pré-notée** (LLM léger ou heuristique) sur les
  axes que la slide adresse → l'axe le plus faible désigne **le juge dont c'est l'obsession** (§5) qui
  **interrompt** avec une question ciblée.
- Imprévus configurables (`config.imprevus`) : `interruption`, `doute`, `pression_temps`,
  `question_piege`, `silence`, `contradiction_interne`, `investor_surprise`.
- Déterminisme des tests : sélection par **hash du contexte** (pas de `random`), comme le mock LLM.

---

## 8. Post-mortem (réutilise `report.py` + PDF)

Généré par le job de `finish`. Contenu :
- **Score Global** + **Fond / Forme** (barres) + verdict (Qualifié/…).
- **Radar de Pitch** (10 axes, 8 remplis en MVP).
- **Timeline** = les `PitchTurn` annotés (moments clés : faiblesses, bonnes réponses).
- **3 forces / 3 faiblesses** (du `PitchRun`).
- **Progression** : courbe des sessions précédentes (requête historique).
- **Comparaison anonymisée** : agrégat des porteurs au même stade (instrumentation).
- **Plan d'entraînement** : dérivé des axes faibles → **routage** vers Academy / prochaine session /
  **opportunités** (réutilise le moteur `next_actions` + OPP).
- **PDF** téléchargeable (réutilise `render_*` WeasyPrint) + **« Partager mon score »** (le credential).

---

## 9. Endpoints (mapping écrans UX)

| Méthode | Route | Écran | Rôle |
| :-- | :-- | :-- | :-- |
| GET | `/pitchsim/committees` | 1 | comités + personas |
| POST | `/pitchsim/decks` (+ DOC-01 upload) | 1 | crée un deck, **parse** les slides |
| GET | `/pitchsim/decks/{id}` | 1/2 | slides typées (main/backup/synthèse) |
| POST | `/pitchsim/sessions` | 1→2 | crée la session (mode, comité, deck, config) + briefing |
| POST | `/pitchsim/sessions/{id}/slide` | 2/3 | narration d'une slide → réactions juges (+ interruption ?) + indicateurs partiels |
| POST | `/pitchsim/sessions/{id}/answer` | 3/4 | réponse (+ `shown_slide_id`) → feedback juge + relance |
| POST | `/pitchsim/sessions/{id}/imprevu` | 2/5 | « imprévu forcé » (entraînement) |
| POST | `/pitchsim/sessions/{id}/finish` | 6 | délibération + scoring (**job async**) |
| GET | `/pitchsim/sessions/{id}/report` | 7 | post-mortem (scores, radar, timeline, plan) |
| GET | `/pitchsim/sessions/{id}/report/pdf` | 7 | PDF |
| GET | `/pitchsim/sessions?project_id=` | 7 | historique / progression |
| POST | `/pitchsim/sessions/{id}/abandon` | 2 | abandon |

Permission : `PITCHSIM_RUN` (déjà au catalogue rôle FOUNDER). Garde d'ownership sur session/deck.

---

## 10. Parsing du deck (seule vraie dépendance nouvelle)

« L'IA voit les slides » ⇒ extraire **le texte par slide** :
- **PDF** : `pypdf` (texte par page).
- **PPTX** : `python-pptx` (texte par slide + titres).
- Upload = **DOC-01** (presigned MinIO) ; parsing déclenché à `POST /decks` (sync si petit, sinon job).
- Vignettes images : **rendues par le front** (ou job `pdf2image` en V2) — hors MVP backend.
- Extra dépendances `[project.optional-dependencies] pitch = ["pypdf", "python-pptx"]`.

---

## 11. Réutilisation de l'existant (l'archi paie)

| Besoin | Réutilise |
| :-- | :-- |
| Upload deck / audio | **DOC-01** (`app/documents`) |
| Délibération + scoring async | **worker/jobs** (pattern diagnostic) |
| Score ancré rejouable | **`app/scoring`** (grille → `PitchRubric`, run → `PitchRun`) |
| Post-mortem + PDF | **`app/reports`** (`render_*`, WeasyPrint) |
| Timeline / progression / partage | **`app/instrumentation`** (events) |
| Plan d'entraînement / orientation | **`next_actions`** + **`app/opportunities`** (le `pitch_score` nourrit l'éligibilité) |
| LLM bon marché + mock | **`app/llm`** (provider + mock déterministe) |

---

## 12. Découpage Sprint 4 (stories)

| Code | Story | Pts |
| :-- | :-- | --: |
| IDX-PITCH-01 | Rubrique de pitch (3 comités, 10 axes ancrés placeholder) + `PitchRubric` | 5 | ✅ |
| IDX-PITCH-02 | Deck : upload (DOC-01) + parsing PDF/PPTX → slides typées | 5 | ✅ |
| IDX-PITCH-03 | Session + tours (narration/answer) + moteur de scénario | 8 | ✅ |
| IDX-PITCH-04 | Scoring Fond (LLM ancré, `PitchRun` rejouable) + Forme-texte (déterministe) | 5 | ✅ |
| IDX-PITCH-05 | Post-mortem (réutilise report+PDF) + progression + plan→Academy/OPP | 5 | ✅ |

**Sprint 4 backend (4A) = 28 pts — LIVRÉ.** Refonte « comité silencieux » = **PITCH-06 (§14.12, ~26 pts)**.
4B (audio/Whisper) et V2 (realtime/caméra/bio) = épics séparées.

---

## 13. Risques & garde-fous

- **Coût LLM** par session (multi-juges + scoring) → provider bon marché, tours **bornés** au gratuit,
  pré-notation par heuristique quand possible.
- **Latence** : tout est **tour-par-tour** au MVP (pas de realtime) → pas de barge-in à gérer.
- **RGPD** : aucune biométrie au MVP ; quand 4B/V2 arrivent → consentement explicite + rétention courte.
- **Intégrité du credential** : seul le **Fond** alimente le score partagé/B2B ; la Forme reste coaching.
- **Matière** : les **3 rubriques ancrées** + personas sont *placeholder v1* → à figer en atelier produit
  (comme la grille Radar v2).

---

## 14. Modèle d'interaction « Comité silencieux » (CANONIQUE — doc fondateur, V2.1)

> **Statut.** Le doc fondateur « Version Humaine — Juin 2026 » fait foi. Il **remplace** le modèle
> d'interruption livré en 4A (PITCH-03). La refonte de l'orchestration = **PITCH-06** ; le socle
> (rubrique, mapping faiblesse→juge, Fond/Forme, post-mortem, gamification, deck) **est réutilisé**.

### 14.1 Les 5 règles d'or (contrat d'expérience)
1. Le comité **ne coupe jamais la parole pendant le pitch** (réactions visuelles seulement).
2. **C'est le porteur qui annonce la fin** (« j'ai terminé », clic en MVP / phrase en V2). Alerte douce
   à la durée cible + **30 s de grâce**, jamais de coupure auto.
3. Chaque agent **parle à son tour** (ordre fixe), puis un **tour libre**.
4. Les agents **se parlent entre eux** (rebond, contradiction, soutien).
5. Le rapport cite **les mots exacts** de chaque agent (pas un score abstrait).

### 14.2 Machine à PHASES (remplace la machine plate de §3 pour PITCH-06)
```
BRIEFING ─start─> PITCHING ─« terminé »(garde ≥30s)─> QA ─tous ont fini─> FREE_ROUND
   └─> DELIBERATING ─(verdicts + scoring)─> COMPLETED        (any non-terminal ─abandon─> ABANDONED)
```
- `phase` devient un champ explicite de `PitchSession` (BRIEFING/PITCHING/QA/FREE_ROUND/DELIBERATING/
  COMPLETED/ABANDONED). Aucune transition implicite ; saut illégal → 422 (comme les autres machines).

### 14.3 L'Orchestrateur (pur, déterministe → testable)
Fonction serveur invisible qui, à partir de `phase` + mémoire, décide **le prochain coup du jury** :
- tient **un seul jeton de parole** (`current_speaker`) — un agent à la fois ;
- en QA, donne la parole dans l'**ordre du comité** ; un agent rend le micro quand sa file de questions
  est vide **ou** qu'il a atteint `qa_questions_per_agent` ;
- **anti-doublon** : clé de question = `(axis, angle)` ; sautée si déjà dans `asked_questions` ;
- déclenche les **micro-réactions** (§14.8) et fait évoluer la **conviction** (§14.4) ;
- avance les phases. **Toute cette logique est sans LLM** (règles pures) ; seul le *contenu* (questions,
  débat, verdicts) appelle le modèle.

### 14.4 Mémoire de session + conviction
Au-delà des `pitch_turns` (transcript horodaté), la session porte un **état d'agents** (JSONB) :
```
agent_state = { "<nom>": { "conviction": {axis: -2..+2}, "pending": [angle…], "asked": int } }
current_speaker, qa_order: [noms], qa_index, asked_questions: [(axis,angle)]
```
La conviction baisse quand une faiblesse touche l'obsession de l'agent, monte sur un signal positif.
Elle pondère le **ton** du verdict final (§14.9) et l'ordre/priorité des questions.

### 14.5 Le TEMPS — qui le définit (combinaison, pas un seul facteur)
| Levier | Effet |
| :-- | :-- |
| **Type de comité** | durée de base + style de Q&A (`default_duration_min`, `qa_questions_per_agent`, `tour_libre`) |
| **Format** choisi par le porteur | dans les bornes du comité : `elevator`(1') · `standard`(3') · `long`(5') |
| **Niveau** (gamification) | **débloque** les modes extrêmes (Flash 30s, Contrarian, Imprévisible) — n'altère pas la base |
| **Palier freemium** | plafonne (gratuit = format standard, 1 session/mois ; premium = tous modes) |

Défauts par comité : **Concours** 3' / 1 question·agent ; **Investisseur** 3' / 2 + tour libre ;
**Incubateur** 5' / 2 + tour libre. **Le chrono dur ne s'applique qu'au PITCH** (soft alert + 30 s de
grâce) ; le **Q&A se mesure en nombre de questions par agent**, pas en horloge (plus humain, plus simple).

### 14.6 Le QUESTIONNEMENT varié (sans tomber dans l'incohérence)
Séparer **structure** (déterministe) et **contenu** (varié) :
- **Pertinence contrainte** : l'axe d'une question ∈ (faiblesses détectées ∪ obsession de l'agent).
- **Variété du contenu**, 4 leviers : (1) le transcript réel diffère ; (2) **seed de variation** par
  session + **température LLM > 0** ; (3) **pool d'angles par axe** (ex. marché : taille / source /
  part adressable / saturation) dans lequel l'agent pioche un angle **non encore utilisé** ; (4)
  **mémoire inter-sessions** : on évite les angles déjà posés aux sessions précédentes du projet.
- En **test** : mock déterministe (seed → angle stable). En **prod** : Mistral génère la variété.
- → « aléatoire » = **varié dans le cadre de la pertinence**, jamais du hasard pur.

### 14.7 L'EXPERT MÉTIER — 5ᵉ juge dynamique par secteur
Le comité = **4 personas fixes + 1 expert sectoriel** injecté selon `project.sector` (qu'on stocke déjà)
→ on retombe sur les « 3 à 5 juges » du doc.
```
SECTOR_EXPERTS = {
  "fintech":  {name:"Expert Fintech",  obsession:"business_model", concerns:[régulation, confiance, unit economics]},
  "agritech": {name:"Expert AgriTech", obsession:"marche",         concerns:[chaîne d'appro, saisonnalité, logistique]},
  "sante":    {name:"Expert Santé",    obsession:"traction",       concerns:[preuve clinique, régulation, remboursement]},
  …  + "_default": {name:"Expert Secteur", obsession:"solution", concerns:[…]}   # repli
}
```
Le comité **résolu** (4 fixes + expert) est **snapshotté sur la session** (`committee_personas` JSONB) →
stable et **rejouable**. Le prompt de l'expert inclut le secteur + ses `concerns`.

### 14.8 Micro-réactions pendant le pitch (silencieuses)
Pour chaque narration, chaque agent émet **un signal** (déterministe : faiblesse + obsession +
conviction) parmi : `nod`, `frown`, `note`, `glance`, `impatient`, `none`. Renvoyés dans la réponse
`/slide` (`reactions:[{agent,reaction}]`) → **le front anime l'avatar**. Stockés en `meta` de la
narration pour la timeline du post-mortem. **Aucune parole.**

### 14.9 Délibération VERBATIM + rapport
À `DELIBERATING` : chaque agent produit **son verdict, avec ses mots** (1 appel LLM par persona, sous
son prompt système + sa conviction + la mémoire) ; il peut **changer d'avis** et **voter**. Stocké en
`pitch_turns` (kind=`deliberation`, actor=agent) **et** dans `PitchRun.verdicts = [{agent, text, vote}]`.
Le post-mortem les surface **verbatim** (Règle 5) — « Ce que M. Morel a dit pendant la délibération… ».
Le scoring **Fond/Forme** (inchangé) est calculé en parallèle sur le transcript complet.

### 14.10 Contrat API (deltas PITCH-06)
| Méthode | Route | Rôle |
| :-- | :-- | :-- |
| POST | `/sessions` | résout le comité (**+ expert secteur**), `phase=BRIEFING`, renvoie comité + timing |
| POST | `/sessions/{id}/start` | BRIEFING→PITCHING (démarre le chrono) |
| POST | `/sessions/{id}/slide` | narration → **réactions** (plus d'interruption) + indicateurs ; MAJ pending+conviction |
| POST | `/sessions/{id}/end-pitch` | « j'ai terminé » → PITCHING→QA (garde ≥30 s) |
| POST | `/sessions/{id}/answer` | réponse à l'agent au micro → question suivante **ou** passe le micro / → FREE_ROUND |
| POST | `/sessions/{id}/pause` · `/resume` | le porteur suspend ; le comité attend |
| POST | `/sessions/{id}/free-round` | génère 1 échange inter-agents (borné) |
| POST | `/sessions/{id}/finish` | FREE_ROUND→DELIBERATING→COMPLETED : verdicts verbatim + scoring |
| GET | `/sessions/{id}/post-mortem` | + `verdicts` verbatim |

### 14.11 Modèle de données (deltas)
- `PitchSession` : `+phase`, `+committee_personas` (snapshot), `+agent_state`, `+current_speaker`,
  `+qa_order`, `+qa_index`, `+format`, `+pitch_clock` (soft).
- `PitchTurn` : nouveaux `kind` = `reaction` (silencieux), `verdict` ; `meta` porte `angle`, `conviction`.
- `PitchRun` : `+verdicts` (les mots des agents) ; `+committee_key`/personas pour l'audit.
- Comités (constantes) : `+default_duration_min`, `+qa_questions_per_agent`, `+allowed_formats`,
  `+tour_libre` ; nouveau `SECTOR_EXPERTS`.

### 14.12 Stories PITCH-06 (refonte orchestration)
| Code | Story | Pts |
| :-- | :-- | --: |
| IDX-PITCH-06a | Machine à **phases** + Orchestrateur (parole, ordre, anti-doublon) — pur/testé | 8 |
| IDX-PITCH-06b | **Expert métier** par secteur + comité snapshotté + timing (contexte×format×niveau×palier) | 5 |
| IDX-PITCH-06c | **Questionnement varié** (pool d'angles + seed + mémoire inter-sessions) | 5 |
| IDX-PITCH-06d | **Tour libre** (inter-agents) + **délibération verbatim** → rapport « mots des agents » | 5 |
| IDX-PITCH-06e | **Micro-réactions** + conviction (signaux pour le front) | 3 |

**PITCH-06 ≈ 26 pts** (texte d'abord). Réutilise tout le socle 4A ; ne touche pas au scoring Fond/Forme.
Le realtime/voix/avatars/ambiance restent **V2 « La Salle »** (transport, pas logique).

---

## 15. Voix des agents (TTS — couche V2 « La Salle »)

> Côté **sortie** (la voix des juges). À distinguer du côté **entrée** (la voix du porteur → STT/Whisper,
> couche 4B). La voix est **additive** : PITCH-06 produit déjà le *texte* ; le TTS le met en son.

### 15.1 Pipeline
```
texte de l'agent (PITCH-06)  →  TTSProvider (synthèse)  →  audio  →  streaming au porteur
                                                                      (sync avatar = front)
```

### 15.2 Seam `TTSProvider` (+ mock) — comme le LLM
Abstraction provider-agnostique : `synthesize(text, *, voice_id, style) -> bytes | stream`. **Mock
déterministe** (stub court) pour dev/tests → la logique PITCH-06 reste testable **sans vrai TTS**.
Providers réels :
- **ElevenLabs** (primaire) : voix réalistes **distinctes**, bon **français**, mode *Flash* basse latence,
  prosodie réglable ;
- **OpenAI TTS** (repli économique).
Config : clé par provider + voix par défaut.

### 15.3 Une voix par persona
Chaque persona (y compris l'**expert métier**) porte un `voice_id` + un style de base (Diallo chaleureuse,
Morel sèche, Chen posée, Koné rapide). Le mapping est **snapshotté sur la session** → **rejouable**.

### 15.4 Latence — la pré-génération (la parade clé)
Pendant le **PITCHING silencieux**, l'orchestrateur **prépare déjà les questions** (§14.3) → on
**pré-synthétise leur audio en parallèle**, mis en cache par `(session, agent, question)`. Au tour de
l'agent → **audio prêt → parole instantanée**. Les **lignes fixes** (briefing, « passons aux questions »)
sont **pré-rendues une fois et mises en cache global**. Le reste passe en **TTS streaming** (jouer avant
la fin de génération).

### 15.5 Prosodie = persona + conviction
Les paramètres de style (stabilité / émotion / vitesse) dérivent du **persona + son niveau de conviction**
(déjà suivi dans la mémoire de session, §14.4) → chaque voix est *vivante*, pas robotique.

### 15.6 Transport & stockage
- **Pré-généré** : audio dans **MinIO** (presigned, cacheable).
- **Temps réel** : streaming **WebRTC/WebSocket** ; synchro labiale de l'avatar = **front**.

### 15.7 Coût & RGPD
Facturé au caractère → **V2 / premium** (le gratuit reste **texte**, cohérent avec « le coût suit le
revenu », §1). Les voix d'agents sont **synthétiques** (aucune donnée perso). La donnée sensible reste la
**voix du porteur en entrée** (STT/4B) → consentement explicite.

### 15.8 Stories (V2 « La Salle »)
| Code | Story |
| :-- | :-- |
| IDX-PITCH-V2-tts-a | Seam `TTSProvider` + mock + ElevenLabs/OpenAI ; `voice_id` par persona (snapshot) |
| IDX-PITCH-V2-tts-b | **Pré-génération** pendant le pitch + cache des lignes fixes (anti-latence) |
| IDX-PITCH-V2-tts-c | Prosodie pilotée par conviction + transport streaming (avec WebRTC « La Salle ») |
