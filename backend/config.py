"""Backend settings. Label maps and token length come from ml/config.py."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

from ml.config import MAX_LENGTH, PROJECT_ROOT, TWO_STAGE_OUTPUT_DIR

STAGE_A_RELATIVE = Path("stage_a") / "best_model"
STAGE_B_RELATIVE = Path("stage_b") / "best_model"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    port: int = 8000
    frontend_url: str = "http://localhost:3000"
    model_dir: Path = TWO_STAGE_OUTPUT_DIR
    llm_enabled: bool = False
    llm_provider: str = "openai"
    llm_api_key: str = ""
    llm_model: str = "gpt-4o-mini"
    llm_base_url: str = "https://api.openai.com/v1"
    llm_timeout_seconds: float = 20.0
    llm_max_output_tokens: int = 800
    max_requirement_chars: int = 2000
    max_length: int = MAX_LENGTH

    @property
    def resolved_model_dir(self) -> Path:
        path = Path(self.model_dir)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        return path

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.frontend_url.split(",") if origin.strip()]

    @property
    def stage_a_dir(self) -> Path:
        return self.resolved_model_dir / STAGE_A_RELATIVE

    @property
    def stage_b_dir(self) -> Path:
        return self.resolved_model_dir / STAGE_B_RELATIVE


@lru_cache
def get_settings() -> Settings:
    return Settings()
