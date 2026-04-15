"""Op3 Studio backend settings.

All runtime configuration is loaded from environment variables so the
container can be re-targeted at a different Op3 checkout or LLM model
without editing source. Defaults are chosen for the standard dev
setup: backend on :8000, frontend on :5173, Op3 package importable
from the repo root (``pip install -e ..`` in development).
"""
from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-backed settings for Op3 Studio."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- API server -----------------------------------------------------
    host: str = "0.0.0.0"
    port: int = 8000
    reload: bool = True

    # --- CORS -----------------------------------------------------------
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    # --- Op3 location --------------------------------------------------
    # Absolute path to the Op3 repo root; contains the op3/ package.
    op3_root: Path = Path(__file__).resolve().parent.parent.parent

    # --- Anthropic (chat) ----------------------------------------------
    anthropic_api_key: str | None = None
    llm_model: str = "claude-sonnet-4-5-20250929"
    llm_max_tokens: int = 4096
    llm_timeout_s: int = 60

    # --- Sandbox -------------------------------------------------------
    sandbox_timeout_s: int = 60
    sandbox_allowed_imports: tuple[str, ...] = (
        "op3",
        "op3.foundations",
        "op3.composer",
        "op3.standards",
        "op3.anchors",
        "op3.uq",
        "numpy",
        "pandas",
        "math",
    )


settings = Settings()
