# Makefile — raccourcis de dev. Tout passe par `uv` (gestionnaire de paquets).
# Cible par défaut : afficher l'aide.

.DEFAULT_GOAL := help
.PHONY: help install run worker migrate revision seed test test-int lint format typecheck calibrate stack stack-down dev dev-all health

# Ports de dev (source de vérité) : API 8080 — le port publié par docker-compose,
# celui du README et celui qu'attend idea-front (BACKEND_API_URL). Postgres 5432,
# Redis 6379, MinIO 9000/9001. Le port Postgres est paramétrable via POSTGRES_PORT
# (.env) et DOIT correspondre au port de DATABASE_URL.

help: ## Affiche cette aide
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

install: ## Installe les dépendances (prod + dev + pdf + pitch)
	uv sync --extra dev --extra pdf --extra pitch

stack: ## Lève l'infra en arrière-plan (postgres, redis, minio)
	docker compose up -d postgres redis minio

stack-down: ## Arrête l'infra
	docker compose down

dev: stack ## Stack complète : infra + attente DB + migrations + API (8080)
	@echo "Attente de Postgres..."
	@until docker compose exec -T postgres pg_isready -U ideaxion >/dev/null 2>&1; do sleep 1; done
	$(MAKE) migrate
	$(MAKE) run

dev-all: stack ## Comme dev, MAIS lance aussi le worker (sinon aucun bilan n'est généré)
	@echo "Attente de Postgres..."
	@until docker compose exec -T postgres pg_isready -U ideaxion >/dev/null 2>&1; do sleep 1; done
	$(MAKE) migrate
	@echo "Démarrage du worker en arrière-plan (draine les diagnostics → bilans)..."
	@uv run python -m app.worker & echo $$! > .worker.pid; \
	trap 'kill `cat .worker.pid` 2>/dev/null; rm -f .worker.pid; echo "worker arrêté"' EXIT INT TERM; \
	uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8080

health: ## Vérifie /health de l'API locale (8080)
	@curl -fsS http://localhost:8080/api/v1/health | python -m json.tool || echo "API injoignable sur 8080"

run: ## Lance l'API en local (rechargement à chaud, port 8080)
	uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8080

worker: ## Lance le worker (draine la table jobs)
	uv run python -m app.worker

migrate: ## Applique les migrations jusqu'à la dernière révision
	uv run alembic upgrade head

revision: ## Génère une migration auto (usage : make revision m="message")
	uv run alembic revision --autogenerate -m "$(m)"

seed: ## Injecte les comptes de démo + la grille Radar v1
	uv run python -m app.seed

test: ## Lance les tests unitaires (les tests d'intégration s'auto-ignorent sans DB)
	uv run pytest

test-int: ## Tests d'intégration (nécessite la stack : docker compose up -d)
	TEST_DATABASE_URL=postgresql://ideaxion:ideaxion@localhost:5432/ideaxion uv run pytest tests/integration -v

calibrate: ## Mesure l'accord IA↔expert sur le golden set (porte de non-régression)
	uv run python -m app.scoring.calibrate

lint: ## Lint (ruff)
	uv run ruff check app tests

format: ## Formate le code (ruff)
	uv run ruff format app tests

typecheck: ## Vérifie le typage (mypy)
	uv run mypy app
