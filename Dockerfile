# Image unique pour l'API et le worker : même code base, commande différente.
FROM python:3.12-slim AS base

# uv : gestionnaire de paquets rapide (copié depuis l'image officielle).
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# Dépendances système de WeasyPrint (génération PDF du bilan) : Pango, Cairo, GDK-PixBuf,
# HarfBuzz, fontconfig + une police de base. Sans elles, render_bilan_pdf échoue (ImportError
# / OSError) — le pipeline dégrade alors gracieusement (bilan `ready` sans PDF).
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpango-1.0-0 \
        libpangoft2-1.0-0 \
        libpangocairo-1.0-0 \
        libcairo2 \
        libgdk-pixbuf-2.0-0 \
        libharfbuzz0b \
        libffi8 \
        libfontconfig1 \
        shared-mime-info \
        fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Couche dépendances (cache) : `--extra pdf` = WeasyPrint, `--extra pitch` = parsing decks.
COPY pyproject.toml ./
RUN uv sync --no-install-project --no-dev --extra pdf --extra pitch || true

# Puis le code applicatif.
COPY . .
RUN uv sync --no-dev --extra pdf --extra pitch

EXPOSE 8080

# Commande par défaut : l'API. Le worker surcharge `command` dans docker-compose.
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
