#!/usr/bin/env bash
# deploy-staging.sh — déploiement manuel du staging Ideaxion.
# Usage (sur le VPS) : ./scripts/deploy-staging.sh [back_tag] [front_tag]
#   back_tag  : tag image backend  (défaut : staging)
#   front_tag : tag image frontend (défaut : staging)
#
# Prérequis :
#   - Docker + Compose installés
#   - .env.staging rempli (cp .env.staging.example .env.staging && nano .env.staging)
#   - Être loggé sur GHCR : echo $GHCR_TOKEN | docker login ghcr.io -u <user> --password-stdin

set -euo pipefail

BACK_TAG="${1:-staging}"
FRONT_TAG="${2:-staging}"

export BACK_IMAGE="ghcr.io/ctocarein/idea-back:${BACK_TAG}"
export FRONT_IMAGE="ghcr.io/ctocarein/idea-front:${FRONT_TAG}"

echo "→ Pull images..."
docker compose -f docker-compose.staging.yml pull api migrate front nginx

echo "→ Migrations..."
docker compose -f docker-compose.staging.yml run --rm migrate

echo "→ Up (no-recreate data services)..."
docker compose -f docker-compose.staging.yml up -d

echo "→ Prune images anciennes..."
docker image prune -f

echo ""
echo "✓ Staging déployé"
echo "  Back  : ${BACK_IMAGE}"
echo "  Front : ${FRONT_IMAGE}"
echo "  Front : https://staging.ideaxion.cloud"
echo "  API   : https://api.staging.ideaxion.cloud/api/v1/health"
