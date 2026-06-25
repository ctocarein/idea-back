# CAHIER DE RECETTE — IDEAXION backend (MVP)

> Plan de recette du backend FastAPI. Chaque scénario décrit **préconditions → étapes →
> résultat attendu → critères d'acceptation**, avec la **traçabilité** vers le test automatisé
> qui le couvre. La recette est **rejouable** : `LLM_PROVIDER=mock` (déterministe), Postgres +
> Redis de test. Les points nécessitant un environnement réel (LLM, PDF, MinIO, déploiement)
> sont listés en §9 (recette manuelle).

## 1. Environnement & prérequis

| Élément | Valeur de recette |
| :-- | :-- |
| Base | PostgreSQL (`TEST_DATABASE_URL`) — schéma créé via `Base.metadata.create_all` |
| Cache / rate-limit | Redis (`REDIS_URL`) — vidé entre chaque test |
| LLM | `mock` (déterministe, hors-ligne) ; **Mistral** pour la recette réelle (§9) |
| Stockage | MinIO désactivé en test (storage `None`) → dégradation gracieuse |
| Seed | grille Radar v2 active, rubrique de pitch active, leçons, opportunités |
| Comptes démo (seed local) | `admin@`, `analyst@`, `mentor@`, `founder@ideaxion.dev` — mdp `ideaxion` |

**Lancer la recette automatisée :**
```bash
export TEST_DATABASE_URL=... REDIS_URL=... JWT_SECRET=... LLM_PROVIDER=mock
uv run pytest -q                 # 153 cas (unit + intégration)
uv run pytest -q -m integration  # parcours bout en bout uniquement
```
Critère global : **100 % verts**, `ruff check`, `ruff format --check`, `mypy` sans erreur.

---

## 2. Parcours PORTEUR (le cœur « comprendre → progresser → devenir visible »)

### REC-P1 — Diagnostic → bilan (score Radar)
- **Préconditions** : grille v2 active.
- **Étapes** : inscription porteur (`POST /auth/register`) → `POST /diagnostics` (flow A, alias camelCase + `terrain`) → traitement worker (`handle_run_diagnostic`) → `GET /reports/{id}`.
- **Attendu** : projet `diagnostic_in_progress`/`new_diagnostic` à la création (202) ; bilan `ready` avec **radar 12 dimensions**, `next_actions` (routage déterministe), couche structurée.
- **Acceptation** : le bilan est consultable au dashboard (jamais par email) ; `radar_score.axes` = 12 ; `next_actions` non vide.
- **Traçabilité** : `tests/integration/test_porteur_flow.py::test_register_diagnostic_to_bilan`.

### REC-P2 — Academy (résolution des next_actions)
- **Étapes** : `GET /academy/lessons?topic=modele_economique` → `GET /academy/lessons/{slug}` → `POST /lessons/{slug}/complete` (idempotent) → `GET /academy/progress` → construire guidé (`/academy/build/*`).
- **Attendu** : leçon servie par topic (résout l'intent) ; progression sans doublon ; l'assistant **questionne** (le porteur reste l'auteur).
- **Acceptation** : `completed_count` stable au rejeu ; tour de coach renvoyé.
- **Traçabilité** : `test_academy_opportunities.py::test_academy_lessons_progress_and_guided_build`.

### REC-P3 — Opportunités (orientation / visibilité)
- **Étapes** : `GET /opportunities?project_id=` → `POST /opportunities/{id}/interest`.
- **Attendu** : **éligibilité déterministe** (score + D11 + secteur) ; « ce qu'il te manque » ; éligibles en tête ; intérêt → événement `opportunity_interest`.
- **Acceptation** : Mentorat (sans critère) éligible ; AgriTech (secteur) bloqué avec raison ; intérêt → 204.
- **Traçabilité** : `test_academy_opportunities.py::test_opportunities_eligibility_for_project` + `tests/test_eligibility.py`.

### REC-P4 — Simulateur de pitch « Comité silencieux »
- **Étapes** : `POST /pitchsim/sessions` (comité + expert métier) → `start-pitch` → `narrate` (réactions silencieuses) → `end-pitch` → `respond` (Q&A ordonnée) → `deliberate`.
- **Attendu** : **aucune interruption** pendant le pitch ; micro-réactions + conviction ; questions ordonnées variées (mémoire inter-sessions) ; **verdicts verbatim** ; score **Fond** (credential) + **Forme** ; post-mortem (radar 10 axes, niveau, plan → Academy/OPP).
- **Acceptation** : `phase` suit `briefing→pitching→qa→free_round→completed` ; saut illégal → 422 ; `run.verdicts` non vide ; post-mortem `training_plan` se termine par `opportunity`.
- **Traçabilité** : `test_pitch.py::test_silent_committee_flow`, `::test_questions_vary_across_sessions` + unit `test_pitch_orchestrator/evaluate/forme/postmortem`.

### REC-P5 — Fiche B2B partageable (consentement)
- **Étapes** : `POST /projects/{id}/share` (consentement requis) → `GET /shared/{token}` (public) → `DELETE /projects/{id}/share`.
- **Attendu** : sans consentement → 422 ; fiche publique = **lecture jury** (score /100, synthèse, forces), pas d'internes ; révocation → 404.
- **Acceptation** : un tiers ne peut pas partager mon projet (403) ; après révocation, lien mort.
- **Traçabilité** : `test_sharing.py::test_share_consent_public_fiche_and_revoke`.

---

## 3. Parcours ANALYSTE / ADMIN (curation & pilotage)

### REC-A1 — Back-office projets
- **Étapes** : `GET /admin/projects?review_status=` → détail → `PATCH /review-status` (machine) → `PATCH /assignee`.
- **Attendu** : porteur exclu (403) ; transition légale OK, **saut illégal → 422** ; assignation refuse un porteur ; tout est **audité**.
- **Traçabilité** : `test_admin_projects.py::test_back_office_list_detail_transition_assign`.

### REC-A2 — Audit & timeline
- **Étapes** : `GET /admin/projects/{id}/timeline` + `GET /admin/audit-logs?entity=project`.
- **Attendu** : chaque action de curation laisse une trace lisible ; porteur sans `AUDIT_READ` → 403.
- **Traçabilité** : `test_admin_projects.py::test_audit_timeline_and_logs`.

### REC-A3 — Gouvernance grille
- **Étapes** : `GET /admin/scoring/grids` → `POST /{version}/activate`.
- **Attendu** : une seule grille active ; version inconnue → 404 ; porteur → 403.
- **Traçabilité** : `test_admin_projects.py::test_grid_governance`.

### REC-A4 — Tableau de bord d'apprentissage
- **Étapes** : générer du funnel (bilan vu + intérêt opportunité) → `GET /admin/learning-dashboard`.
- **Attendu** : compteurs par événement + **funnel** `bilan_viewed → action_started → opportunity_interest` avec taux de conversion ; porteur → 403.
- **Traçabilité** : `test_instrumentation.py::test_learning_dashboard_aggregates_funnel`.

### REC-A5 — Supervision des jobs
- **Étapes** : `GET /admin/jobs` + `/stats` + `POST /{id}/retry`.
- **Attendu** : le job du diagnostic est listé ; relance → `pending` (audité) ; inexistant → 404 ; porteur → 403.
- **Traçabilité** : `test_jobs_admin.py::test_jobs_supervision`.

---

## 4. Parcours MENTOR (onboarding & marketplace)

### REC-M1 — Onboarding bout en bout
- **Étapes** : `POST /mentors/apply` (public) → `GET /admin/mentor-applications` → `approve` → `POST /mentors/accept-invitation` → `POST /auth/login`.
- **Attendu** : approbation crée un compte **INVITED** + invitation à **token (hash, usage unique, expiration)** ; activation pose le mot de passe ; **login réussit** ; token réutilisé → 422.
- **Traçabilité** : `test_mentors.py::test_mentor_onboarding_end_to_end`.

### REC-M2 — Profil & marketplace
- **Étapes** : `GET/PATCH /mentors/me` → `GET /mentors?sector=` → `POST /mentors/{id}/request` → indisponibilité (`is_active=false`).
- **Attendu** : profil créé à l'approbation ; marketplace filtrée ; demande → 201 ; mentor indisponible disparaît.
- **Traçabilité** : `test_mentors.py::test_mentor_profile_and_marketplace`.

### REC-M3 — Curation mentor (admin)
- **Étapes** : `POST /admin/mentors/{id}/suspend` puis `/activate`.
- **Attendu** : suspendu → retiré de la marketplace ; réactivé → de retour ; non-mentor → 422 ; porteur → 403.
- **Traçabilité** : `test_mentors.py::test_mentor_suspend_and_activate`.

---

## 5. Conformité RGPD

### REC-R1 — Export & droit à l'oubli
- **Étapes** : `GET /me/export` → `DELETE /me`.
- **Attendu** : export JSON complet (compte, projets, bilans, documents) ; suppression → cascade SQL, **email libéré**, token invalidé (401) ; la trace d'audit survit.
- **Traçabilité** : `test_gdpr.py::test_export_then_delete_account`.

---

## 6. Sécurité (transverse)

### REC-S1 — Authentification & autorisations
- **Attendu** : routes sensibles sans token → **401** ; back-office pour porteur → **403** ; token invalide → 401 ; en-têtes de sécurité (`nosniff`, `X-Frame DENY`) présents **même sur erreur**.
- **Traçabilité** : `test_security_authz.py` (3 cas) + `test_porteur_flow.py::test_health_and_security_headers` + `tests/test_permissions/test_guards/test_security`.

### REC-S2 — Robustesse du scoring (cœur métier)
- **Attendu** : score **rejouable** (`ScoreRun`), validation stricte des axes, ensemble (consensus + confiance), grille ancrée intègre, fallback LLM.
- **Traçabilité** : `tests/test_scoring/test_ensemble/test_calibration/test_fallback/test_llm_parse`.

---

## 7. Migration & données

### REC-D1 — Migration réversible
- **Étapes** : `alembic downgrade base` → `upgrade head`.
- **Attendu** : schéma reconstruit (**27 tables métier**), réversible, idempotent ; seed (users, grille, rubrique pitch, leçons, opportunités).
- **Acceptation** : `upgrade`/`downgrade` sans erreur ; `python -m app.seed` idempotent.

---

## 8. Matrice de couverture (stories → recette)

| Sprint | Stories | Recette |
| :-- | :-- | :-- |
| S1 | AUTH/FND | REC-S1, REC-D1, /health |
| S2 | LLM/SCORING/DIAG/JOB | REC-P1, REC-S2, REC-A5 |
| S3 | ACADEMY/DOC/OPP | REC-P2, REC-P3 |
| S4 | PITCH (06) | REC-P4 |
| S5 | MENTOR/ADMIN/OPP-02 | REC-M1/2/3, REC-A1/2/3, REC-P5 |
| S6 | INSTRUM/OPS | REC-A4, REC-A5, REC-R1, REC-S1 |

---

## 9. Recette MANUELLE (environnement réel — hors CI)

Ces points sont **vérifiés à la main** car ils dépendent de services réels :

| # | Quoi | Comment |
| :-- | :-- | :-- |
| MAN-1 | **LLM réel** (Mistral) | `LLM_PROVIDER=mistral` + clé → un diagnostic + un scoring de pitch ; vérifier le **parsing JSON** et la pertinence des scores/verdicts |
| MAN-2 | **PDF** (WeasyPrint) | `--extra pdf` → `GET /reports/{id}/pdf` et `/pitchsim/.../post-mortem/pdf` rendent un PDF valide |
| MAN-3 | **Upload MinIO** | MinIO lancé + creds → `POST /documents/upload-url` (presigned) → PUT direct → `confirm` |
| MAN-4 | **Fallback LLM** | couper le primaire → vérifier la bascule sur le secondaire |
| MAN-5 | **Déploiement** (OPS-05) | push `develop` → staging ; merge `main` → prod ; `/health` post-déploiement |

---

> **État de la recette** : la couverture automatisée (153 cas) valide l'intégralité des parcours
> backend de bout en bout. Restent la recette manuelle §9 (services réels) et le déploiement (OPS-05).
