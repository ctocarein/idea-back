"""Configuration applicative — pydantic-settings, validée AU DÉMARRAGE (fail-fast).

Si une variable requise manque ou est mal typée, l'app refuse de démarrer :
un crash visible vaut mieux qu'une erreur silencieuse en production.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    # --- Application ---
    app_env: str = "local"  # local | staging | production
    app_name: str = "ideaxion-backend"
    log_level: str = "INFO"

    # --- Base de données ---
    # On accepte une URL postgresql:// classique et on force le driver async (asyncpg)
    # au moment de construire l'engine (cf. database.py), pour ne pas l'imposer dans le .env.
    database_url: str

    # --- Cache / sessions ---
    redis_url: str = "redis://localhost:6379/0"

    # --- Sécurité (JWT) ---
    jwt_secret: SecretStr
    access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 30

    # --- Email (vérification d'adresse) ---
    # URL publique du front, pour construire les liens des emails.
    public_base_url: str = "http://localhost:3000"

    # --- OAuth (connexion par fournisseur d'identité : Google, LinkedIn) ---
    # URL publique du BACKEND : sert à construire le redirect_uri déclaré aux fournisseurs
    # (le provider renvoie sur `{backend_base_url}/api/v1/auth/oauth/{provider}/callback`).
    # Cette URL doit être enregistrée à l'identique côté Google/LinkedIn.
    backend_base_url: str = "http://localhost:8080"
    google_client_id: str | None = None
    google_client_secret: SecretStr | None = None
    linkedin_client_id: str | None = None
    linkedin_client_secret: SecretStr | None = None
    # SMTP optionnel : si smtp_host est absent, on LOGGE le lien (dev) au lieu d'envoyer.
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: SecretStr | None = None
    email_from: str = "IDEAXION <no-reply@ideaxion.cloud>"

    # --- CORS ---
    # Liste blanche d'origines. NoDecode : on reçoit la chaîne brute du .env et c'est notre
    # validateur (_split_csv) qui la découpe — pas le décodage JSON de pydantic-settings.
    cors_origins: Annotated[list[str], NoDecode] = Field(default_factory=list)
    # IPs/CIDR des reverse proxies de confiance (ex. "10.0.0.1,10.0.0.2").
    # Uniquement ces peers peuvent fixer X-Forwarded-For. En local = vide.
    trusted_proxies: Annotated[list[str], NoDecode] = Field(default_factory=list)

    # --- Abstraction LLM ---
    llm_provider: str = "deepseek"  # mock | deepseek | mistral | openai | gemini
    # Providers de repli (ordre), ex. "mistral,openai" : si le primaire tombe, on bascule.
    # Seuls ceux dont la clé est présente sont activés.
    llm_fallbacks: Annotated[list[str], NoDecode] = Field(default_factory=list)
    deepseek_api_key: SecretStr | None = None
    mistral_api_key: SecretStr | None = None
    openai_api_key: SecretStr | None = None
    gemini_api_key: SecretStr | None = None
    # Modèles par défaut (surchargables par env). Choix : petits modèles (coût freemium).
    deepseek_model: str = "deepseek-chat"
    mistral_model: str = "mistral-small-latest"
    mistral_vision_model: str = "pixtral-12b-2409"  # Pixtral : multimodal (voit les slides)
    openai_model: str = "gpt-4o-mini"
    gemini_model: str = "gemini-1.5-flash"
    # Paramètres d'appel. Température basse (reproductibilité), un peu > 0 pour que
    # l'ensemble (N passes) ait une dispersion exploitable.
    llm_temperature: float = 0.2
    llm_max_tokens: int = 4096
    llm_timeout_seconds: float = 30.0

    # --- Stockage objet (MinIO) ---
    minio_endpoint: str = "localhost:9000"
    minio_access_key: SecretStr | None = None
    minio_secret_key: SecretStr | None = None
    minio_bucket: str = "ideaxion"
    minio_secure: bool = False
    minio_region: str | None = None
    minio_timeout_seconds: float = Field(default=5.0, gt=0, le=60)
    minio_max_attempts: int = Field(default=3, ge=1, le=5)
    minio_circuit_failure_threshold: int = Field(default=3, ge=1, le=20)
    minio_circuit_reset_seconds: int = Field(default=30, ge=1, le=300)

    # --- Monétisation (V1.2) ---
    # Paywall de l'export du pitch : False = gratuit au lancement (défaut).
    # Passer à True quand le paiement est branché → l'export exigera un droit.
    pitch_export_paid: bool = False

    @field_validator("cors_origins", "llm_fallbacks", mode="before")
    @classmethod
    def _split_csv(cls, value: object) -> object:
        # Accepte "a,b,c" dans le .env plutôt qu'un JSON ["a","b","c"].
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def async_database_url(self) -> str:
        # Force le driver asyncpg si l'URL fournie est un postgresql:// nu.
        url = self.database_url
        if url.startswith("postgresql+"):
            return url
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    # lru_cache : une seule instance de Settings pour tout le process.
    return Settings()
