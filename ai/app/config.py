"""Central config. Everything is read from env vars (never hardcode hosts/keys).

Local dev: values come from ai/.env (gitignored). In production they come from
the platform dashboard (Render/Railway). See ai/.env.example for the full list.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Database (Neon pooled URL) ---
    # e.g. postgresql://user:pass@ep-xxx-pooler.region.aws.neon.tech/db?sslmode=require
    database_url: str = ""

    # --- Embeddings (OpenAI-compatible API) ---
    # Default targets OpenAI; swap base/model for Voyage/Cohere if desired.
    embedding_api_base: str = "https://api.openai.com/v1"
    embedding_api_key: str = ""
    embedding_model: str = "text-embedding-3-small"
    # text-embedding-3-small returns 1536 dims. Must match the chunks.embedding column.
    embedding_dim: int = 1536

    # --- CORS: comma-separated list of allowed frontend origins ---
    # In prod, set to the Vercel domain. Locally we default to the Next.js dev server.
    cors_origins: str = "http://localhost:3000"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
