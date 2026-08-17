from __future__ import annotations

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMJudgeSettings(BaseSettings):
    """Local configuration for an OpenAI-compatible LLM Judge provider."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="LLM_JUDGE_",
        extra="ignore",
    )

    enabled: bool = False
    base_url: str = "https://api.openai.com/v1"
    api_key: SecretStr | None = None
    model_name: str | None = None
    timeout_seconds: float = Field(default=30.0, gt=0, le=300)
    max_calls: int = Field(default=3, ge=0, le=100)

    @model_validator(mode="after")
    def validate_enabled_configuration(self) -> LLMJudgeSettings:
        if not self.enabled:
            return self

        if self.api_key is None or not self.api_key.get_secret_value().strip():
            raise ValueError(
                "LLM_JUDGE_API_KEY is required when LLM Judge is enabled.",
            )

        if self.model_name is None or not self.model_name.strip():
            raise ValueError(
                "LLM_JUDGE_MODEL_NAME is required when LLM Judge is enabled.",
            )

        if self.max_calls == 0:
            raise ValueError(
                "LLM_JUDGE_MAX_CALLS must be greater than 0 when LLM Judge is enabled.",
            )

        return self
