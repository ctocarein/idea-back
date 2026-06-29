# Image unique pour l'API et le worker : même code base, commande différente.
# SEC-09 : uv épinglé par version (pas :latest), build non-root, uv sync --frozen.
FROM python:3.12-slim AS base

# uv : gestionnaire de paquets rapide — version épinglée pour build reproductible.
COPY --from=ghcr.io/astral-sh/uv:0.5.26 /uv /uvx /bin/

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

# Utilisateur non-root (SEC-09 : limite l'impact d'une compromission runtime).
RUN groupadd --system app && useradd --system --gid app --no-create-home app

WORKDIR /app

# Couche dépendances (cache) : lockfile + pyproject.toml → build reproductible.
# `--frozen` : refuse de modifier le lockfile (pas de surprise en CI/prod).
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev --extra pdf --extra pitch

# Code applicatif.
COPY . .
RUN uv sync --frozen --no-dev --extra pdf --extra pitch

# Passage à l'utilisateur non-root AVANT le CMD.
USER app

EXPOSE 8080

# Commande par défaut : l'API. Le worker surcharge `command` dans docker-compose.
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
