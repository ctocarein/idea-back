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

    # --- CORS ---
    # Liste blanche d'origines. NoDecode : on reçoit la chaîne brute du .env et c'est notre
    # validateur (_split_csv) qui la découpe — pas le décodage JSON de pydantic-settings.
    cors_origins: Annotated[list[str], NoDecode] = Field(default_factory=list)

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
