# SPRINT 2 — Diagnostic & Radar : « comprendre son projet » (Semaines 3-4) · backend

> 🎯 **Objectif :** un porteur passe le diagnostic (idée guidée **ou** upload), l'IA + la grille
> Radar produisent son tableau de compréhension + un bilan PDF, visible au dashboard (pas d'email).
> 🧪 **Démo :** diagnostic de bout en bout → tableau de compréhension + PDF dans l'espace porteur.

**Capacité backend : 39 pts.** Détail : [BACKLOG.md](../docs/BACKLOG.md#sprint-2--diagnostic--radar--comprendre-son-projet).

## Board

### 🟡 In progress (squelette réconcilié posé)
- **IDX-SCORING-01** Grille Radar versionnée `[5]` — modèle `scoring_grids` versionné + `GET /scoring/grid` + seed **grille v1 placeholder** ✅ ; reste : **vraie grille v1 (ateliers)**.
- **IDX-SCORING-02** Tableau de compréhension `[3]` — agrégation axes→lentilles ✅ (`lens_score`/`overall_score`) ; rendu front-dominant.
- **IDX-DIAG-01** Diagnostic flow A `[5]` — `POST /diagnostics` crée projet+diagnostic+bilan pending, consent RGPD, audit, enqueue job ✅ ; reste : **questions par catégorie servies par le backend**.
- **IDX-DIAG-02** Diagnostic flow B `[5]` — `POST /diagnostics/upload` + DTO ✅ ; reste : **extraction texte (worker)**.
- **IDX-DIAG-03** Génération du bilan `[8]` — **handler `run_diagnostic` ferme la boucle** (grille ancrée → N passes → consensus → bilan `ready` → transitions → routage revue) ✅ avec mock, offline ; reste : **LLM réel + PDF MinIO**.
- **IDX-JOB-01** Worker & file de jobs `[8]` — file + boucle + backoff + **handler `run_diagnostic` enregistré** ✅ ; reste : send_email, cleanup.
- **IDX-LLM-01** Couche `app/llm` `[5]` — ✅ **terminé** : mock + **providers réels DeepSeek/Mistral/OpenAI** (compatible OpenAI, httpx + résilience timeout/retry/circuit breaker) + parsing JSON strict + prompt ancré versionné *(Gemini = stub)*.

### 🤖 Scoring robuste — boucle complète (offline avec `LLM_PROVIDER=mock`)
`POST /diagnostics` → job → grille **ancrée** → **N passes** (ensemble) → **consensus médiane + confiance** → validation stricte → **agrégation pondérée déterministe** → `ScoreRun` rejouable → bilan `ready` → **routage auto vers l'analyste si incertain**. Calibration mesurable via `make calibrate`.

### 🔑 Décisions de réconciliation appliquées
- Projet à **deux machines à états** : `diagnostic_status` (pipeline) + `review_status` (curation analyste).
- Archétype canonique **`field`** (alias `terrain` accepté en entrée).
- DTO diagnostic acceptent les **alias camelCase** front (`projectName`, `fundingNeed`) + `consent` RGPD requis.

## Chemin critique
`SCORING-01` (grille) → `DIAG-01/03` · `LLM-01` → `DIAG-03`/academy/pitchsim · `JOB-01` → génération asynchrone.
⚠️ **La grille Radar v1 est un pré-requis bloquant** (vient des ateliers, pas du code — GUIDE §10/§11).

## DoD du sprint
- [ ] Diagnostic flow A et B produisent un bilan stocké (MinIO) + visible au dashboard.
- [ ] Parsing JSON LLM **strict** (Pydantic) ; sortie malformée → retry/revue, jamais de bilan corrompu.
- [ ] Dégradation LLM testée (job rejoué, projet en attente, pas de 500 silencieux).
- [ ] Événements d'instrumentation émis (diagnostic fait) — anticipation INSTRUM.
