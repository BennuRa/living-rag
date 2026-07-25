"""Factory for selecting the configured embedding provider."""

from __future__ import annotations

from app.core.config import Settings, get_settings
from app.services.embedding import EmbeddingProvider, MockEmbeddingProvider
from app.services.ollama_embedding import OllamaEmbeddingProvider
from app.services.openai_compatible_embedding import (
    OpenAICompatibleEmbeddingProvider,
)


def create_embedding_provider(
    settings: Settings | None = None,
) -> EmbeddingProvider:
    """Create an embedding provider from runtime settings.

    Args:
        settings: Optional runtime settings. When omitted, the cached
            application settings are loaded.

    Returns:
        The configured embedding provider.

    Raises:
        ValueError: If the configured provider name is unsupported.
    """
    runtime_settings = settings or get_settings()
    provider_name = runtime_settings.embedding_provider.strip().lower()

    if provider_name == "mock":
        return MockEmbeddingProvider()

    if provider_name == "ollama":
        return OllamaEmbeddingProvider(
            base_url=runtime_settings.ollama_base_url,
            model=runtime_settings.embedding_model,
            timeout_seconds=runtime_settings.embedding_timeout_seconds,
        )

    if provider_name == "openai_compatible":
        return OpenAICompatibleEmbeddingProvider(
            base_url=runtime_settings.embedding_api_base_url,
            api_key=runtime_settings.embedding_api_key,
            model=runtime_settings.embedding_model,
            timeout_seconds=runtime_settings.embedding_timeout_seconds,
        )

    raise ValueError(
        "Unsupported embedding provider: "
        f"{runtime_settings.embedding_provider}",
    )