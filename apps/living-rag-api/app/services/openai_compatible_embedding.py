"""OpenAI-compatible embedding provider implementation."""

from __future__ import annotations

from collections.abc import Sequence

import httpx

from app.services.embedding import EmbeddingProvider


class OpenAICompatibleEmbeddingProvider(EmbeddingProvider):
    """Embedding Provider for services compatible with /v1/embeddings."""

    dimension = 768

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        timeout_seconds: float = 30.0,
    ) -> None:
        if not base_url.strip():
            raise ValueError(
                "OpenAI-compatible embedding base_url must not be blank.",
            )

        if not api_key.strip():
            raise ValueError(
                "OpenAI-compatible embedding api_key must not be blank.",
            )

        if not model.strip():
            raise ValueError(
                "OpenAI-compatible embedding model must not be blank.",
            )

        if timeout_seconds <= 0:
            raise ValueError(
                "timeout_seconds must be greater than zero.",
            )

        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds

    def embed_texts(
        self,
        texts: Sequence[str],
    ) -> list[list[float]]:
        """Generate embeddings through an OpenAI-compatible API.

        Args:
            texts: Texts that should be embedded.

        Returns:
            One 768-dimensional vector for each input text.

        Raises:
            ValueError: If any input text is blank.
            RuntimeError: If the service cannot be reached, returns an HTTP
                error, or returns an invalid embedding response.
        """
        text_list = list(texts)

        for text in text_list:
            if not text.strip():
                raise ValueError("Embedding text must not be blank.")

        if not text_list:
            return []

        payload = {
            "model": self.model,
            "input": text_list,
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            response = httpx.post(
                f"{self.base_url}/v1/embeddings",
                json=payload,
                headers=headers,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
        except httpx.TimeoutException as error:
            raise RuntimeError(
                "OpenAI-compatible embedding request timed out.",
            ) from error
        except httpx.HTTPStatusError as error:
            raise RuntimeError(
                "OpenAI-compatible embedding request failed with HTTP status "
                f"{error.response.status_code}.",
            ) from error
        except httpx.RequestError as error:
            raise RuntimeError(
                "OpenAI-compatible embedding service could not be reached.",
            ) from error

        try:
            response_data = response.json()
        except ValueError as error:
            raise RuntimeError(
                "OpenAI-compatible service returned invalid JSON.",
            ) from error

        if not isinstance(response_data, dict):
            raise RuntimeError(
                "OpenAI-compatible response must be a JSON object.",
            )

        raw_data = response_data.get("data")

        if not isinstance(raw_data, list):
            raise RuntimeError(
                "OpenAI-compatible response does not contain a data list.",
            )

        if len(raw_data) != len(text_list):
            raise RuntimeError(
                "OpenAI-compatible service returned a different number "
                "of vectors than the input texts.",
            )

        validated_items: list[dict[str, object]] = []

        for item in raw_data:
            if not isinstance(item, dict):
                raise RuntimeError(
                    "OpenAI-compatible response contains an invalid data item.",
                )

            validated_items.append(item)

        sorted_data = sorted(
            validated_items,
            key=lambda item: item.get("index", 0),
        )

        embeddings: list[list[float]] = []

        for item in sorted_data:
            raw_embedding = item.get("embedding")

            if not isinstance(raw_embedding, list):
                raise RuntimeError(
                    "OpenAI-compatible response item does not contain "
                    "an embedding list.",
                )

            try:
                embedding = [
                    float(value)
                    for value in raw_embedding
                ]
            except (TypeError, ValueError) as error:
                raise RuntimeError(
                    "OpenAI-compatible response contains a non-numeric "
                    "embedding value.",
                ) from error

            if len(embedding) != self.dimension:
                raise RuntimeError(
                    "OpenAI-compatible service returned an embedding with "
                    f"an unexpected dimension: expected {self.dimension}, "
                    f"got {len(embedding)}.",
                )

            embeddings.append(embedding)

        return embeddings