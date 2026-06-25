# DÉPLOIEMENT — IDEAXION backend (OPS-05)

> Pipeline **CI/CD** : `develop` → **staging**, `main` → **production**. Build d'image (GHCR),
> déploiement par SSH (`docker compose`), **migrations** puis **health post-déploiement**.
> Cible de référence : un serveur self-hosted avec Docker. Adaptable à une PaaS (cf. §6).

## 1. Vue d'ensemble du flux

```
push develop ─┐                         ┌─ deploy staging  ─ /health ✅
              ├─ CI (ruff+mypy+pytest) ─┤
push main ────┘   build image → GHCR    └─ deploy production ─ /health ✅
```
- **CI** (`.github/workflows/ci.yml`) : qualité + tests (doit être vert).
- **Deploy** (`.github/workflows/deploy.yml`) : build/push image, `scp` du compose, `migrate` → `up -d`, vérif `/api/v1/health`.

## 2. Prérequis serveur (une fois)

1. Docker + plugin Compose installés.
2. Un dossier de déploiement, ex. `/opt/idea-back` (= `DEPLOY_PATH`).
3. Le fichier **`.env`** (secrets applicatifs) dans ce dossier — depuis `.env.production.example`.
   `openssl rand -hex 32` pour `JWT_SECRET` ; mots de passe Postgres/MinIO ; clé(s) LLM.
4. Accès au registre GHCR : `docker login ghcr.io` (ou image publique).
5. Un **reverse-proxy TLS** devant l'API (Caddy/Traefik/nginx) → expose `:8080` en HTTPS.

## 3. Secrets & variables GitHub (par environnement)

Créer deux **environnements** GitHub : `staging` et `production`. Pour chacun :

| Type | Nom | Exemple |
| :-- | :-- | :-- |
| secret | `DEPLOY_HOST` | `staging.ideaxion.app` |
| secret | `DEPLOY_USER` | `deploy` |
| secret | `DEPLOY_SSH_KEY` | clé privée SSH (le serveur a la publique) |
| secret | `DEPLOY_PATH` | `/opt/idea-back` |
| variable | `APP_URL` | `https://api-staging.ideaxion.app` |

> Protéger l'environnement `production` (required reviewers) pour une **promotion contrôlée**.

## 4. Déployer

- **Automatique** : `git push origin develop` (→ staging) ou merge sur `main` (→ production).
  Le workflow build → push → `migrate` → `up -d` → health.
- **Manuel sur le serveur** (dépannage) :
  ```bash
  cd /opt/idea-back
  export IMAGE=ghcr.io/ctocarein/idea-back:<sha>
  docker compose -f docker-compose.prod.yml pull
  docker compose -f docker-compose.prod.yml run --rm migrate   # alembic upgrade head
  docker compose -f docker-compose.prod.yml up -d
  curl -fsS https://<app_url>/api/v1/health
  ```

## 5. Rollback

```bash
cd /opt/idea-back
export IMAGE=ghcr.io/ctocarein/idea-back:<sha_précédent>   # tag connu et sain
docker compose -f docker-compose.prod.yml up -d
```
- Les migrations sont **réversibles** (`alembic downgrade -1`) — à n'utiliser que si la nouvelle
  révision a cassé le schéma. Sinon, revenir à l'image précédente suffit (schéma additif).
- Tag GHCR par `sha` → tout déploiement est traçable et réversible.

## 6. Cibler une PaaS (alternative au SSH)

`build-push` et `Health post-déploiement` sont réutilisables tels quels. Remplacer l'étape
**Déploiement** par l'action de la plateforme :
- **Fly.io** : `flyctl deploy --image $IMAGE` (secret `FLY_API_TOKEN`).
- **Render/Scalingo** : hook de déploiement ou CLI, en pointant l'image GHCR.

## 7. Post-déploiement (checklist)

- [ ] `/api/v1/health` → `200` (db + redis ok ; minio non bloquant).
- [ ] `/api/v1/docs` accessible (derrière auth/IP si souhaité).
- [ ] **Seed** (1re mise en prod) : grille Radar + rubrique pitch actives → `python -m app.seed`
      (ou une migration de données dédiée).
- [ ] Smoke LLM réel (cf. `CAHIER_RECETTE.md` §9 MAN-1).
- [ ] Sauvegarde Postgres planifiée + rétention MinIO.

> **Limite assumée** : ce dépôt fournit la **config** ; le déploiement effectif requiert l'infra
> et les secrets (serveur, DNS, TLS, registre) côté exploitant.
