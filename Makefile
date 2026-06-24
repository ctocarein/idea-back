# Makefile — raccourcis de dev. Tout passe par `uv` (gestionnaire de paquets).
# Cible par défaut : afficher l'aide.

.DEFAULT_GOAL := help
.PHONY: help install run worker migrate revision seed test lint format typecheck calibrate

help: ## Affiche cette aide
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

install: ## Installe les dépendances (prod + dev + pdf + pitch)
	uv sync --extra dev --extra pdf --extra pitch

run: ## Lance l'API en local (rechargement à chaud)
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
