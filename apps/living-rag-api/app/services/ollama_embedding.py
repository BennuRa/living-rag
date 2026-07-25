"""Ollama embedding provider implementation."""

from __future__ import annotations

from collections.abc import Sequence

import httpx

from app.services.embedding import EmbeddingProvider


class OllamaEmbeddingProvider(EmbeddingProvider):
    """Embedding Provider backed by Ollama's /api/embed endpoint."""

    dimension = 768

    def __init__(
        self,
        base_url: str,
        model: str = "nomic-embed-text",
        timeout_seconds: float = 30.0,
    ) -> None:
        if not base_url.strip():
            raise ValueError("Ollama base_url must not be blank.")

        if not model.strip():
            raise ValueError("Ollama model must not be blank.")

        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than zero.")

        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds

    def embed_texts(
        self,
        texts: Sequence[str],
    ) -> list[list[float]]:
        """Generate embeddings for a batch of texts through Ollama.

        Args:
            texts: Texts that should be embedded.

        Returns:
            One 768-dimensional vector for each input text.

        Raises:
            ValueError: If any input text is blank.
            RuntimeError: If Ollama cannot be reached, returns an HTTP error,
                or returns an invalid embedding response.
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

        try:
            response = httpx.post(
                f"{self.base_url}/api/embed",
                json=payload,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
        except httpx.TimeoutException as error:
            raise RuntimeError(
                "Ollama embedding request timed out.",
            ) from error
        except httpx.HTTPStatusError as error:
            raise RuntimeError(
                "Ollama embedding request failed with HTTP status "
                f"{error.response.status_code}.",
            ) from error
        except httpx.RequestError as error:
            raise RuntimeError(
                "Ollama embedding service could not be reached.",
            ) from error

        response_data = response.json()
        raw_embeddings = response_data.get("embeddings")

        if not isinstance(raw_embeddings, list):
            raise RuntimeError(
                "Ollama response does not contain an embeddings list.",
            )

        if len(raw_embeddings) != len(text_list):
            raise RuntimeError(
                "Ollama returned a different number of vectors "
                "than the input texts.",
            )

        embeddings: list[list[float]] = []

        for raw_embedding in raw_embeddings:
            if not isinstance(raw_embedding, list):
                raise RuntimeError(
                    "Ollama returned an invalid embedding value.",
                )

            try:
                embedding = [
                    float(value)
                    for value in raw_embedding
                ]
            except (TypeError, ValueError) as error:
                raise RuntimeError(
                    "Ollama returned a non-numeric embedding value.",
                ) from error

            if len(embedding) != self.dimension:
                raise RuntimeError(
                    "Ollama returned an embedding with an unexpected "
                    f"dimension: expected {self.dimension}, "
                    f"got {len(embedding)}.",
                )

            embeddings.append(embedding)

        return embeddings