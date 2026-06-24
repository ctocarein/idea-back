# BACKLOG BACKEND — IDEAXION (MVP freemium)

**Backlog exécutable du backend FastAPI.** Dérivé du `GUIDE.md` (périmètre, qui fait foi)
et de `ARCHITECTURE_BACKEND.md` (conventions de code). Ce document est le **suivi vivant**
de l'exécution ; le GUIDE reste la spec. Périmètre : **stories à dominante backend**
(les stories front — DS, DASH, rendu UI — sont référencées mais suivies côté `idea-front`).

> Codification : `IDX-<EPIC>-<NN>` · Estimation Fibonacci `1,2,3,5,8,13` (complexité).
> DoR / DoD : voir `GUIDE.md` §2.4 / §2.5 (+ checklist backend condensée en bas de page).

## Légende de statut

| Symbole | Sens |
| :--- | :--- |
| ✅ | Done — livré et vérifié |
| 🟡 | In progress / partiel — amorcé, reste du travail (détaillé en note) |
| ⬜ | To Do — pas commencé |
| ⏳ | v2 — différé, architecturé mais non développé |

---

## Vue épics (backend)

| Code | Épic | Sprint | Statut | Points back |
| :--- | :--- | :--- | :--- | ---: |
| **FND** | Fondations / socle (`app/core`, Docker, Alembic) | S1 | 🟡 | 15 |
| **AUTH** | Authentification & RBAC 4 rôles (`app/iam`) | S1 | 🟡 | 16 |
| **LLM** | Couche IA multi-provider (`app/llm`) | S2 | ✅ | 5 |
| **SCORING** | Grille Radar versionnée (`app/scoring`) | S2 | 🟡 | 5 |
| **DIAG** | Diagnostic 2 flows + bilan (`app/diagnostics`, `app/reports`) | S2 | 🟡 | 18 |
| (DOC seam) | Storage MinIO (`app/core/storage.py`) — amorce DOC-01 | S3 | 🟡 | — |
| **JOB** | Worker & file de jobs (`app/jobs`, `app.worker`) | S2 | 🟡 | 8 |
| **ACADEMY** | Apprendre (`app/academy`) | S3 | ✅ | 16 |
| **DOC** | Documents presigned (`app/documents`) | S3 | ✅ | 5 |
| **OPP** | Espace opportunités (éligibilité déterministe) | S3 | ✅ | 5 |
| **PITCH** | Simulateur de pitch « Le Comité » (`app/pitchsim`) | S4 | ⬜ | 28 |
| **MENTOR** | Onboarding & marketplace mentors (`app/mentors`) | S5 | ⬜ | 15 |
| **ADMIN** | Back-office (`app/projects`, `app/audit`) | S5 | ⬜ | 16 |
| **INSTRUM** | Instrumentation d'apprentissage (transverse) | S6 | 🟡 | 8 |
| **OPS** | Tests, sécurité, RGPD, monitoring, prod | S6 | ⬜ | 23 |
| **PAY/SIGN/CERTIF/DEALFLOW** | Monétisation & industrialisation (`app/_v2/`) | — | ⏳ | — |

**Total backend MVP ≈ 178 pts** (hors stories front DS/DASH suivies dans `idea-front`).

---

## SPRINT 1 — Socle

> 🎯 Fondation déployable : Docker (+MinIO), API FastAPI, PostgreSQL migrée, auth JWT +
> RBAC 4 rôles. *Démo : se connecter via l'API avec 4 rôles et voir le bon espace.*

| Code | Story | Pts | Statut | Dépend de | Note |
| :--- | :--- | ---: | :--- | :--- | :--- |
| IDX-FND-01 | Dépôt & environnement Docker | 5 | ✅ | — | docker-compose (+ bucket MinIO), Dockerfile (api+worker, WeasyPrint), Makefile, `.env.example`, **CI GitHub Actions** (ruff+mypy+pytest+intégration) ✅ |
| IDX-FND-02 | DB, migrations, logger | 3 | ✅ | FND-01 | `app/core/{database,logging,config}` ✅ · Alembic async configuré · **migration initiale à générer** |
| IDX-FND-03 | Health check | 2 | ✅ | FND-02 | `/api/v1/health` agrège **DB + Redis + MinIO** (non configuré = non bloquant) → 200/503 |
| IDX-FND-04 | Schéma de données MVP | 5 | 🟡 | FND-02 | Tables socle (users, permission_grants, refresh_tokens, invitations, audit_logs, jobs, projects) ✅ · seed comptes ✅ · **tables features (diagnostics, reports, scoring_grids, academy_lessons, learning_progress, practice_sessions, mentors, documents) livrées avec leurs sprints** · **grille Radar v1 ⬜** |
| IDX-AUTH-01 | Inscription & login (Argon2id + JWT) | 5 | ✅ | FND-04 | `app/iam` register/login, access 15 min |
| IDX-AUTH-02 | Refresh token & logout | 3 | ✅ | AUTH-01 | refresh rotatif haché + détection de vol, `/auth/me` GET/PATCH · *cookie HttpOnly = BFF front* |
| IDX-AUTH-03 | RBAC 4 rôles + permissions | 5 | ✅ | AUTH-01 | `require(...)`, grants explicites, garde-fous ressource, **tests 403** |
| IDX-AUTH-04 | Rate limiting & headers sécurité | 3 | ✅ | AUTH-01 | rate-limit Redis (IP login/register + **5/15 min par email**, fail-open), middleware en-têtes (nosniff, X-Frame DENY, Referrer ; CSP/HSTS en prod), CORS allow-list ✅ |

**Sprint 1 backend : 31 pts** — déjà livré ≈ 21 (🟡/✅), reste ≈ 10 (AUTH-04, CI, migration initiale, check MinIO, grille Radar).

---

## SPRINT 2 — Diagnostic & Radar : « comprendre son projet »

> 🎯 Un porteur passe le diagnostic (idée guidée **ou** upload) → tableau de compréhension
> + bilan PDF visible au dashboard (pas d'email). *Démo : diagnostic bout en bout.*

| Code | Story | Pts | Statut | Dépend de | Note |
| :--- | :--- | ---: | :--- | :--- | :--- |
| IDX-LLM-01 | Couche `app/llm` multi-provider | 5 | ✅ | FND | Protocole `LLMProvider` + `factory` (imports paresseux) + provider `mock` + **providers réels DeepSeek/Mistral/OpenAI (compatible OpenAI, httpx)** + **résilience (timeout/retry/circuit breaker)** + **parsing JSON strict** + prompt ancré versionné · *(Gemini = stub, API non-OpenAI)* |
| IDX-SCORING-01 | Grille Radar versionnée | 5 | 🟡 | FND-04 | **grille v2 (12 dims D1-D12 / 4 piliers / 10)** ancrée + pondérée, scale-aware, `GET /scoring/grid`, agrégation déterministe (`engine.py`), validation stricte, `ScoreRun` rejouable, seed + intégrité ✅ · **ancres/poids réels (atelier) ⬜** |
| IDX-SCORING-02 | Tableau de compréhension (3 lentilles) | 3 | 🟡 | SCORING-01 | backend = agrégation axes→lentilles ✅ (`lens_score`/`overall_score`) · *rendu front-dominant* |
| IDX-DIAG-01 | Diagnostic flow A (idée guidée) | 5 | 🟡 | SCORING-01 | `POST /diagnostics` crée projet+diagnostic+bilan pending, consent RGPD, audit, enqueue job ✅ · **jeux de questions par catégorie servis par le backend ⬜** |
| IDX-DIAG-02 | Diagnostic flow B (upload + extraction) | 5 | 🟡 | DIAG-01, DOC-01 | `POST /diagnostics/upload` + DTO flow B ✅ · **extraction texte (worker) ⬜** |
| IDX-JOB-01 | Worker & file de jobs (SKIP LOCKED) | 8 | 🟡 | FND-02 | File Postgres + boucle worker + backoff 1/5/15 + **handler `run_diagnostic` enregistré** ✅ · **send_email, cleanup ⬜** |
| IDX-DIAG-03 | Génération du bilan (analyse + scoring + PDF) | 8 | ✅ | LLM-01, SCORING-01, JOB-01 | handler `run_diagnostic` (grille v2 → N passes → consensus → bilan `ready` → transitions → routage revue) + **rapport structuré complet** (`DiagnosticReport` : description, verdict, **matrice de risques**, **table concurrents**, **métriques d'avancement**, recos priorisées, next steps — gardé, affinable analyste) + lecture (`GET /reports`, `/reports/{id}`) + **PDF de pré-diagnostic (WeasyPrint, charte Aube), stocké MinIO, download presigned** ✅ |

**Sprint 2 backend : 39 pts** — squelette réconcilié posé ; reste : providers LLM, handler `run_diagnostic`, extraction document, PDF, grille v1 des ateliers.

> **Décisions de réconciliation appliquées :** projet à **deux machines** (`diagnostic_status` pipeline + `review_status` curation) ; archétype canonique **`field`** (alias `terrain` accepté) ; DTO acceptent les **alias camelCase** front (`projectName`, `fundingNeed`) + `consent` RGPD. Cf. mémoire projet `sprint2-contract-decisions`.

### Robustesse du scoring (core métier — la 1re porte)

Le score est traité comme un **système mesuré**, pas un appel LLM (cf. mémoire `scoring-core-metier`). Avancement des 6 piliers :

| Pilier | Mécanisme | État |
| :--- | :--- | :--- |
| 1. Reproductibilité | `ScoreRun` (inputs, `grid_version`, `prompt_version`, `model`, **N passes brutes stockées**) rejouable/auditable + LLM **température basse** | ✅ |
| 2. Validité (ancres + poids) | grille ancrée (rubrique 0-100) + pondération par catégorie + agrégation déterministe (`engine.py`) | ✅ structure · **vraies valeurs ateliers ⬜** |
| 3. Validation stricte | exactement les axes, bornes 0-100, valeur dans une ancre, intégrité de grille | ✅ |
| 4. Incertitude | N passes → consensus médiane + étendue/axe → confiance ; `needs_review` auto si axe incertain (`app/scoring/ensemble.py`, `build_consensus_score`) | 🟡 moteur ✅ · **N passes LLM réelles + transition `review_status` par le worker ⬜** |
| 5. Calibration (preuve) | golden set + accord IA↔expert (MAE/corrélation) + **porte de non-régression** (`make calibrate`, exit 0/1) | 🟡 machinerie ✅ (stdlib, hors-ligne) · **vrais cas experts ⬜** · branchement scorer LLM live ⬜ |
| 6. Résilience | **timeout + retry transitoire + circuit breaker** par modèle, **fallback multi-provider** (DeepSeek→Mistral→…), sortie malformée → `LLMParseError` → rejeu ; bilan reste `pending`, jamais de faux score | ✅ |

> **Pilier 7 (vision) — comparabilité / credential portable.** Le score circule dans l'écosystème
> (porteur → jury/incubateur → investisseur) : il doit être **comparable entre porteurs et entre
> `grid_version`**. À ajouter à la calibration : une **normalisation cross-version** (un score v1 et un
> score v2 ne se rangent pas dans le même classement sans elle). C'est ce qui fait du « score Ideaxion »
> un credential dont la valeur croît avec l'usage. Cf. mémoire `vision-actif-strategique`. ⬜

---

## SPRINT 3 — Academy, Documents & Opportunités : « apprendre, progresser, devenir visible »

> 🎯 Modules pédagogiques, construire guidé (l'IA explique, le porteur écrit), documents.

| Code | Story | Pts | Statut | Dépend de | Note |
| :--- | :--- | ---: | :--- | :--- | :--- |
| IDX-ACADEMY-01 | Modules pédagogiques | 5 | ✅ | FND-04 | `academy_lessons`, `GET /academy/lessons` (filtre `?topic=` → résout les next_actions) |
| IDX-ACADEMY-02 | Progression & suivi | 3 | ✅ | ACADEMY-01 | `learning_progress`, `POST /lessons/{slug}/complete` (idempotent), `GET /academy/progress` |
| IDX-ACADEMY-03 | Construire guidé (assistant IA) | 8 | ✅ | LLM-01 | `guided_sessions` · prompt coach (FORMAT=coach) **le porteur reste l'auteur** · brouillon + tours |
| IDX-DOC-01 | Upload documents (presigned MinIO) | 5 | ✅ | FND-04 | `POST /documents/upload-url` (5 min) → confirm · ≤ 20 Mo · types validés · `GET/DELETE` · storage injecté |
| IDX-OPP-01 | Espace opportunités (catalogue + éligibilité) | 5 | ✅ | SCORING, DIAG | `opportunities` · `GET /opportunities` filtré par **éligibilité déterministe** (`score + D11 + secteur`, pure, zéro LLM) · « ce qu'il te manque » · intérêt → event `opportunity_interest` |

**Sprint 3 backend : 26 pts.** *(la « visibilité » côté porteur — orientation vers les opportunités — ferme la boucle diagnostic→score→recos→parcours→**opportunités**.)*

---

## SPRINT 4 — Simulateur de pitch « Le Comité » : « recréer la pression, en sécurité »

> 🎯 Comité virtuel multi-personnalités, imprévus déclenchés par les faiblesses, double évaluation
> Fond/Forme, post-mortem. **Spec figée :** [SPEC_PITCHSIM.md](SPEC_PITCHSIM.md).
> Couche **4A (texte, Mode Slides, tour-par-tour)** ci-dessous ; 4B audio (Whisper) et V2 (realtime,
> Mode Caméra, biométrie) = épics séparées, derrière le paywall.

| Code | Story | Pts | Statut | Dépend de | Note |
| :--- | :--- | ---: | :--- | :--- | :--- |
| IDX-PITCH-01 | Rubrique de pitch (3 comités, 10 axes ancrés placeholder) | 5 | ✅ | SCORING | `PitchRubric` versionnée (8 axes Fond ancrés + 2 bio différés) · 3 comités/personas (obsession = axe) · seed + 15 tests |
| IDX-PITCH-02 | Deck : upload + parsing PDF/PPTX → slides typées | 5 | ✅ | DOC-01 | `pitch_decks`/`pitch_slides` (main/backup/synthèse) · upload **multipart** + parsing `pypdf`/`python-pptx` · 10 tests |
| IDX-PITCH-03 | Session + tours + **moteur de scénario** | 8 | ✅ | PITCH-01, LLM-01 | `pitch_sessions`/`pitch_turns` · moteur **pur déterministe** : heuristique de faiblesse → juge (obsession) interrompt · imprévus configurables + investisseur surprise · machine à états · 9 tests |
| IDX-PITCH-04 | Scoring Fond (LLM ancré, `PitchRun` rejouable) + Forme-texte | 5 | ✅ | PITCH-03 | Fond = credential (LLM ancré sur transcript+slides, validé strict) · Forme = proxies déterministes (concision/tics/complétude/structure) · `PitchRun` · **validé sur Mistral réel** · 5 tests |
| IDX-PITCH-05 | Post-mortem + progression + plan→Academy/OPP | 5 | ⬜ | PITCH-04, reports | réutilise report+PDF · timeline = `pitch_turns` · plan via next_actions + opportunités |

**Sprint 4 backend (4A) : 28 pts.** *(4B audio + V2 realtime/caméra/bio = épics séparées, payantes.)*

---

## SPRINT 5 — Mentors & Back-office admin

> 🎯 Onboarder des mentors (CV+email → compte créé par l'admin), les rendre découvrables,
> donner à l'admin de quoi curer et piloter.

| Code | Story | Pts | Statut | Dépend de | Note |
| :--- | :--- | ---: | :--- | :--- | :--- |
| IDX-MENTOR-01 | Candidature & création de compte par l'admin | 5 | ⬜ | AUTH, DOC-01 | `POST /mentors/apply` (CV presigned) · `/admin/mentor-applications` · invitation · audit |
| IDX-MENTOR-02 | Profil mentor | 5 | ⬜ | MENTOR-01 | secteurs, bio, agenda, honoraires (champ), `GET/PATCH /mentors/me` |
| IDX-MENTOR-03 | Marketplace découverte (côté porteur) | 5 | ⬜ | MENTOR-02 | `GET /mentors` filtrable · `POST /mentors/{id}/request` *(booking/paiement = v2)* |
| IDX-ADMIN-01 | Back-office projets (liste, détail, pilotage) | 8 | ⬜ | AUTH-03, projects | `GET /projects` filtré · `PATCH /projects/{id}/status` (machine à états + audit) · assignation |
| IDX-ADMIN-02 | Curation mentors & gouvernance grille | 5 | ⬜ | MENTOR-01, SCORING-01 | activer/suspendre mentor · **versionner la grille Radar** + catégories |
| IDX-ADMIN-03 | Audit logs & timeline | 3 | ⬜ | audit | `GET /projects/{id}/timeline`, `GET /admin/audit-logs` |
| IDX-OPP-02 | Fiche projet partageable (B2B) + visibilité | 5 | ⬜ | reports, OPS-03 | **export/partage du rapport** pensé jury/incubateur (la *triple-lecture* : porteur/analyste/jury) · **visibilité contrôlée par le porteur** (consentement explicite, ce qui est partagé) · base du sourcing B2B (vue organisateur = post-MVP) |

**Sprint 5 backend : 36 pts.**

---

## SPRINT 6 — Instrumentation, sécurité, RGPD & prod

> 🎯 Rendre le freemium **apprenant**, durcir, rendre conforme, déployer.

| Code | Story | Pts | Statut | Dépend de | Note |
| :--- | :--- | ---: | :--- | :--- | :--- |
| IDX-INSTRUM-01 ★ | Tableau de bord d'apprentissage | 8 | 🟡 | tout S2-S5 | **socle d'événements posé** (`app/instrumentation` : table `events` + `emit`) + **funnel maillon** (`bilan_viewed` à la lecture, `action_started` sur `POST /reports/{id}/actions/{key}/start`) ✅ · agrégations + `GET /admin/learning-dashboard` ⬜ |
| IDX-OPS-01 | Tests de recette | 5 | 🟡 | tout | **test d'intégration du parcours porteur** (register→diagnostic→worker→bilan, LLM mock, `tests/integration`) ✅ · scénarios `CAHIER_RECETTE` complets + couverture ≥ 70 % ⬜ |
| IDX-OPS-02 | Durcissement sécurité | 5 | ⬜ | AUTH-04 | headers, sanitization, rate-limit effectif · **tests 401/403 exhaustifs** |
| IDX-OPS-03 | Conformité RGPD | 5 | ⬜ | tout | export JSON · effacement cascade (projet/diag/docs + objets MinIO) · transactionnel |
| IDX-OPS-04 | Monitoring & supervision jobs | 3 | ⬜ | JOB-01 | Sentry + métriques · `GET /admin/jobs` + relance · alerte job échoué |
| IDX-OPS-05 | CI/CD & mise en production | 5 | ⬜ | FND-01 | push `develop`→staging · merge `main`→prod · health post-déploiement |

**Sprint 6 backend : 31 pts.**

---

## Lacunes / décisions à arbitrer

- **Onboarding** : le GUIDE crée le projet via `DIAG-01`. L'archi backend prévoit un module
  `app/onboarding` (porteur + **capture investisseur curatée**). La capture investisseur
  (profil + file de validation admin) n'a **pas de story dédiée** dans le GUIDE → à ajouter
  si on veut amorcer le Club dès le MVP (cf. archi backend §7.2).
- **FND-04** ambitionne tout le schéma MVP en S1 ; en pratique on livre les tables socle en S1
  et les tables métier avec leur feature (choix assumé, à valider avec le PO).
- **Vélocité** : recalibrer après S1 (sprint étalon). Si < 32 pts/sprint observés → étaler sur 14-18 semaines (GUIDE §8).

---

## DoD backend (condensée — détail GUIDE §2.5)

- [ ] PR mergée sur `develop`, ≥ 1 revue approuvée.
- [ ] Tous les critères d'acceptation vérifiés.
- [ ] Tests verts ; **couverture module ≥ 70 %** (priorité : cas 403, invitations, transitions).
- [ ] OpenAPI à jour pour toute route nouvelle/modifiée.
- [ ] Pas de secret en clair ; `.env.example` à jour.
- [ ] Logs structurés + `audit_logs` pour toute action sensible (même transaction).
- [ ] Migration Alembic **réversible** (up/down) si schéma modifié.
- [ ] `ruff` + `mypy` (strict) verts.
- [ ] Événements d'instrumentation émis si la story touche le parcours de transformation.
- [ ] Déployé et vérifié sur **staging**.
