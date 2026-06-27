# Audit pré-production — Ideaxion (front + back)

**Date :** 2026-06-26
**Périmètre :** `idea-back` (FastAPI) + `idea-front` (Next.js 16) — vue d'ensemble du projet
**Objectif :** état des lieux strict, bugs, cohérence du flux porteur, obstacles, prép. staging.

---

## 1. Données dures (mesuré, pas déclaré)

| Repo | Tests | Lint | Types | Build |
|------|-------|------|-------|-------|
| **idea-back** | ✅ 128 pass / 25 skip | ✅ ruff | ✅ mypy (151 fichiers) | image prod OK |
| **idea-front** | scoring ✅ (vitest) | ✅ 0 erreur *(après audit ; 19 avant)* | ✅ tsc source | ✅ standalone |

> Les 25 tests back « skipped » sont les scénarios nécessitant un provider LLM réel /
> ressources externes (volontairement exclus du run déterministe `LLM_PROVIDER=mock`).

---

## 2. Bugs révélés et corrigés (front)

| # | Constat | Fichier | Statut |
|---|---------|---------|--------|
| A1 | « tes 6 axes » au lieu de 12 dimensions | `diagnostics/components/DiagnosticResult.tsx` | ✅ corrigé |
| A2 | `PitchProgress` affichait une **progression mock** (42→70) sur le dashboard | `pitch-simulator/components/PitchProgress.tsx` | ✅ remplacé par carte CTA honnête |
| A3 | Code mort (0 usage) : `PitchSimulator.tsx`, `PitchFeedbackPanel.tsx`, `data/mock.ts` | pitch-simulator | ✅ supprimé |
| A4 | `ReactQueryDevtools` embarqué en prod (pas de garde) | `shared/providers/app-providers.tsx` | ✅ dev-only |
| A5 | 19 erreurs lint (imports de feature par leurs internes) | pages + barrels | ✅ 0 (barrels complétés + règle `api`/`actions`) |

---

## 3. Cohérence du flux porteur

Parcours **login → diagnostic → bilan → dashboard → readiness → academy → opportunités →
mentors → simulateur** : **cohérent et fonctionnel** (prouvé live de bout en bout).
Échelle de score interne cohérente (axes /10, score global /100).

**Restes de mock = placeholders *design-first* assumés** (en attente de pipeline backend), hors
chemin critique de démonstration :
- scoring d'un **upload PDF/DOCX** (`UploadDiagnostic`) — attend extraction + scoring backend ;
- **coaching** du wizard guidé et `GuidedBuilder` (Academy) — attendent `app/llm`.

**Frictions UX mineures (non bloquantes, à arbitrer) :**
- E1 — l'onboarding mène au dashboard (vide) plutôt qu'au diagnostic directement.
- E2 — `/diagnostic` n'est pas dans le menu du dashboard (accessible par CTA).
- E3 — garde d'accès au pitch : erreur backend 403 (Mentors prévient côté client). Asymétrie.

---

## 4. Obstacles staging

### Backend — **prêt**
`docker-compose.prod.yml`, CI/CD (`deploy.yml` + `ci.yml`), `Dockerfile` multi-rôle
(WeasyPrint inclus), healthcheck `/api/v1/health` (DB+Redis+MinIO), migrations Alembic,
seed idempotent, worker `restart: unless-stopped`, secrets validés au démarrage (fail-fast),
CORS liste blanche, rate-limit Redis, headers sécurité + HSTS en prod.

### Frontend — **débloqué pendant cet audit**
- 🔴→✅ **Pas de Dockerfile / `next.config` non standalone** → créés : `Dockerfile` multi-stage
  non-root, `output: "standalone"`, `.dockerignore`, `.env.staging.example`, `docs/DEPLOYMENT.md`.

### À décider / durcir avant prod
- **LLM en staging** : `mock` (gratuit, déterministe) sauf besoin de calibration réelle → éviter
  une facture LLM surprise.
- **CORS staging** : ajouter l'origine du front staging à `CORS_ORIGINS`.
- Healthcheck du **worker** (visibilité s'il meurt), automatisation du **seed** au 1er déploiement.
- Observabilité (Sentry), backup Postgres/MinIO, rotation des secrets.

---

## 5. Checklist de mise en staging

1. **Infra** : serveur Docker + reverse-proxy TLS (Caddy/Traefik) ; DNS `api-staging` + `staging`.
2. **Secrets** : `.env` serveur (`JWT_SECRET=openssl rand -hex 32`, `POSTGRES_PASSWORD`,
   `MINIO_*`, `LLM_PROVIDER=mock`, `CORS_ORIGINS=https://staging.ideaxion.app`).
3. **Backend** : `up -d postgres redis minio` → `run migrate` → `run python -m app.seed` →
   `up -d api worker` → `GET /api/v1/health` = 200.
4. **Front** : `docker build -t ideaxion-front:staging .` →
   `docker run -e BACKEND_API_URL=https://api-staging.ideaxion.app -e NODE_ENV=production`.
5. **Smoke** (cf. `docs/CAHIER_RECETTE.md`) : login démo → diagnostic → bilan → simulateur ;
   vérifier le refresh silencieux (attendre 15 min).

---

## 6. Verdict

**Aucun blocage majeur restant.** Le backend est prod-grade ; le front est désormais
conteneurisable et le parcours porteur est cohérent et prouvé. Les éléments « à durcir »
(LLM staging, CORS, observabilité, backups) sont des arbitrages d'exploitation, pas des
bugs. Le projet est **prêt pour un déploiement staging**.
