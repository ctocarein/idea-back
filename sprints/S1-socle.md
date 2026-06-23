# SPRINT 1 — Socle (Semaines 1-2) · backend

> 🎯 **Objectif :** fondation déployable sur staging — Docker (+MinIO), API FastAPI,
> PostgreSQL migrée, auth JWT + RBAC 4 rôles.
> 🧪 **Démo :** se connecter via l'API avec les 4 rôles et obtenir les bonnes permissions.

**Capacité backend : 31 pts.** Détail des stories : [BACKLOG.md](../docs/BACKLOG.md#sprint-1--socle).

## Board

### ✅ Done
- **IDX-FND-02** DB, migrations, logger `[3]` — `app/core/{database,logging,config}`, Alembic async.
- **IDX-AUTH-01** Inscription & login (Argon2id + JWT 15 min) `[5]`.
- **IDX-AUTH-02** Refresh rotatif + logout + `/auth/me` `[3]`.
- **IDX-AUTH-03** RBAC 4 rôles + permissions + garde-fous ressource + tests 403 `[5]`.

### 🟡 In progress
- **IDX-FND-01** Dépôt & Docker `[5]` — reste : **CI lint+test**.
- **IDX-FND-03** Health check `[2]` — reste : **check MinIO**.
- **IDX-FND-04** Schéma MVP `[5]` — tables socle ✅ ; reste : **grille Radar v1 (seed)**, tables features (livrées avec leur sprint).

### ⬜ To Do
- **IDX-AUTH-04** Rate limiting & headers sécurité `[3]` — 5 essais/15 min/email, rate-limit Redis, CORS allow-list, CSP/X-Frame-Options.

## Reste-à-faire pour clore le sprint
1. `IDX-AUTH-04` (rate-limiting + headers).
2. ~~Migration initiale~~ ✅ baseline `0001_initial` (délègue à `Base.metadata`) → `make migrate`.
3. Brancher la **CI** (ruff + mypy + pytest) sur `develop`.
4. Compléter le **health MinIO** et la **grille Radar v2** au seed (✅ grille seedée).

## DoD du sprint
- [ ] Stack `docker compose up -d` OK (api, worker, postgres, redis, minio).
- [ ] `/api/v1/health` → 200 (DB+Redis+MinIO).
- [ ] Login fonctionnel pour les 4 comptes de seed, permissions correctes.
- [ ] Tests 403 verts ; couverture `app/iam` ≥ 70 %.
- [ ] OpenAPI à jour ; CI verte sur `develop`.
