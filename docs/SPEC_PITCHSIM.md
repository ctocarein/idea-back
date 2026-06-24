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
| **4A — « Le Comité »** | Mode Slides **texte**, tour-par-tour : comités+personas, parsing deck, slides typées, narration→réactions, **interruptions déclenchées par les faiblesses**, imprévus (config), score **Fond** + **Forme-texte**, **post-mortem + PDF**, progression | **S4 (MVP)** |
| **4B — « La Voix »** | Upload audio (DOC-01) → Whisper (seam STT + mock) → métriques de délivrance déterministes (débit, tics, timing) → Forme défendable | Premium (post-S4) |
| **V2 — « La Salle »** | Realtime WebRTC + voix TTS par juge + **Mode Caméra** (Hume/MediaPipe) RGPD-gated + replay vidéo | V2 (épic séparée) |

Cette spec couvre **4A** en détail ; 4B/V2 sont esquissés pour que le modèle ne se peigne pas dans un coin.

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
| IDX-PITCH-01 | Rubrique de pitch (3 comités, 10 axes ancrés placeholder) + `PitchRubric` | 5 |
| IDX-PITCH-02 | Deck : upload (DOC-01) + parsing PDF/PPTX → slides typées | 5 |
| IDX-PITCH-03 | Session + tours (narration/answer) + **moteur de scénario** (imprévus déclenchés par faiblesses) | 8 |
| IDX-PITCH-04 | Scoring Fond (LLM ancré, `PitchRun` rejouable) + Forme-texte (déterministe) | 5 |
| IDX-PITCH-05 | Post-mortem (réutilise report+PDF) + progression + plan→Academy/OPP | 5 |

**Sprint 4 backend ≈ 28 pts** (4A). 4B (audio/Whisper) et V2 (realtime/caméra/bio) = épics séparées.

---

## 13. Risques & garde-fous

- **Coût LLM** par session (multi-juges + scoring) → provider bon marché, tours **bornés** au gratuit,
  pré-notation par heuristique quand possible.
- **Latence** : tout est **tour-par-tour** au MVP (pas de realtime) → pas de barge-in à gérer.
- **RGPD** : aucune biométrie au MVP ; quand 4B/V2 arrivent → consentement explicite + rétention courte.
- **Intégrité du credential** : seul le **Fond** alimente le score partagé/B2B ; la Forme reste coaching.
- **Matière** : les **3 rubriques ancrées** + personas sont *placeholder v1* → à figer en atelier produit
  (comme la grille Radar v2).
```
