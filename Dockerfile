# Image unique pour l'API et le worker : même code base, commande différente.
# SEC-09 : uv épinglé par version (pas :latest), build non-root, uv sync --frozen.
FROM python:3.12-slim AS base

# uv : gestionnaire de paquets rapide — version épinglée pour build reproductible.
COPY --from=ghcr.io/astral-sh/uv:0.5.26 /uv /uvx /bin/

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    # Chromium (export deck) : chemin partagé lisible par l'utilisateur non-root `app`.
    PLAYWRIGHT_BROWSERS_PATH=/opt/ms-playwright

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
RUN uv sync --frozen --no-install-project --no-dev --extra pdf --extra pitch --extra deck

# Navigateur Chromium + ses libs système (export deck PDF/PPTX via Playwright).
# En root (avant USER app) ; --with-deps installe les paquets apt requis. On rend
# le dossier lisible/exécutable par `app`. Sans ça, l'export deck échoue en prod.
# --no-sync : le code n'est pas encore copié, on utilise le venv tel quel.
RUN uv run --no-sync playwright install --with-deps chromium \
    && chmod -R a+rx /opt/ms-playwright \
    && rm -rf /var/lib/apt/lists/*

# Code applicatif.
COPY . .
RUN uv sync --frozen --no-dev --extra pdf --extra pitch --extra deck

# Passage à l'utilisateur non-root AVANT le CMD.
USER app

EXPOSE 8080

# Liveness : l'orchestrateur ne route que si /health répond 200 (db + redis + minio OK).
HEALTHCHECK --interval=30s --timeout=5s --start-period=25s --retries=3 \
    CMD ["python", "-c", "import sys,urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/api/v1/health',timeout=4).status==200 else 1)"]

# Commande par défaut : l'API. Le worker surcharge `command` dans docker-compose.
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
