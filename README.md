# Ideaxion — Backend (FastAPI)

Backend du MVP freemium Ideaxion : **moteur de transformation** (diagnostic, Radar de
Collision, Workshop). Seule source de vérité métier, exposée en API REST `/api/v1` avec
OpenAPI auto.

> Architecture de référence : [`docs/ARCHITECTURE_BACKEND.md`](docs/ARCHITECTURE_BACKEND.md).
> Périmètre produit (fait foi) : `GUIDE.md` côté `idea-front`. Contrat consommé par le
> front Next.js (`idea-front`).
> Suivi d'exécution : [`docs/BACKLOG.md`](docs/BACKLOG.md) (stories + statut) et
> [`sprints/`](sprints/README.md) (kanban par sprint).

## Stack

Python 3.12 · FastAPI · SQLAlchemy 2.0 async + asyncpg · Pydantic v2 · Alembic ·
Redis · MinIO · jobs Postgres (`SKIP LOCKED`) · abstraction LLM (DeepSeek/Mistral).
Outillage : **uv**, ruff, mypy, pytest.

## Conventions

- **Code en anglais, commentaires en français.** Libellés utilisateur en français (i18n).
- Couches strictes : `router → service → repository → DB`. Jamais de saut de couche.
- `app/core/` = technique (aucun métier). Chaque feature = un dossier autonome.
- Tout I/O externe est faillible : timeout + retry + circuit breaker + dégradation.
- Toute action sensible → `audit_logs`, **dans la même transaction**.

## Démarrage

```bash
cp .env.example .env          # ajuster JWT_SECRET, clés LLM, MinIO…
make install                  # uv sync (prod + dev)
docker compose up -d          # postgres, redis, minio (+ bucket), api, worker
make migrate                  # applique la migration baseline (0001_initial)
make seed                     # comptes de démo par rôle + grille Radar v2
make test-int                 # (optionnel) parcours porteur de bout en bout
```

| Service | URL |
| :--- | :--- |
| API | http://localhost:8080 |
| Swagger / OpenAPI | http://localhost:8080/api/v1/docs |
| Health | http://localhost:8080/api/v1/health |
| MinIO console | http://localhost:9001 |

Comptes de seed (mdp `ideaxion`, local) : `admin@`, `analyst@`, `mentor@`,
`founder@` `ideaxion.dev` (le TLD `.test` est refusé par la validation d'email).

## Commandes

### PDF du bilan (WeasyPrint)
Le PDF est généré par **WeasyPrint** (extra `pdf`), qui requiert des **libs système** (Pango,
Cairo, GDK-PixBuf…) — déjà installées dans le `Dockerfile`. En local hors Docker, installer ces
libs (GTK) avant `make install`. Sans elles, le pipeline **dégrade gracieusement** : le bilan est
`ready` (score + tableau de compréhension), seul le PDF est absent. Bucket MinIO créé au démarrage
par le service `createbuckets` (compose) + filet `ensure_bucket` côté code.

```bash
make run        # API en local (reload)
make worker     # worker (draine la file jobs)
make test       # pytest
make lint       # ruff
make typecheck  # mypy
make revision m="message"   # nouvelle migration auto
make migrate    # applique les migrations
```

## État du socle (Sprint 1)

Posé et fonctionnel :

- `app/core/` — config (fail-fast), database (async), cache (Redis), security
  (argon2id + JWT), errors (enveloppe uniforme), logging (structlog), resilience,
  pagination.
- `app/iam/` — **auth complète** : register / login / refresh rotatif / logout / me,
  RBAC 4 rôles + permissions explicites (grants) + garde-fous ressource. Modèle
  d'invitation posé (service Sprint 5).
- `app/audit/` — audit transactionnel.
- `app/jobs/` + `app/worker.py` — file Postgres `SKIP LOCKED`, backoff 1/5/15 min.
- `app/projects/` — machine à états (segment « comprendre ») + modèle.
- `app/platform/` — health check (DB + Redis).
- `app/llm/` — protocole + fabrique, providers concrets avec failover et circuit breaker.
- Outillage : `pyproject` (uv), Docker (api+worker), docker-compose, Alembic async,
  seed, tests unitaires (permissions, machine à états, sécurité).

**Modules démontés** — `pitch` (éditeur & deck), `pitchsim` (comité) et `studio` (logo &
marque) ne sont plus montés dans `app/api.py`. Ils sortent du chemin critique : marque et
deck sont l'aval du parcours, hors du seul moment produit validé (diagnostic → bilan
explicable → ce qui manque). Retrait par **démontage, pas par suppression** : le code, les
modèles et les tests restent, aucune migration destructive. Pour rouvrir, remettre l'import
et le `include_router` (les instructions sont dans `app/api.py`) et lever le flag
correspondant côté front — les tests d'intégration se réactivent alors d'eux-mêmes.

Le `_v2/` (payments, signatures, certification, dealflow) est architecturé mais **non
monté** en phase freemium.
