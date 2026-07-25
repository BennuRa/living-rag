"""Embedding provider abstractions and deterministic mock implementation."""

from __future__ import annotations

import hashlib
import math
from abc import ABC, abstractmethod
from collections.abc import Sequence


class EmbeddingProvider(ABC):
    """将文本转换为向量的 Embedding Provider 抽象接口。"""

    @abstractmethod
    def embed_texts(
        self,
        texts: Sequence[str],
    ) -> list[list[float]]:
        """将一批文本转换为与输入顺序对应的向量列表。

        Args:
            texts: 待转换的文本序列。每一段输入文本都应该对应一个输出向量。

        Returns:
            与输入文本逐项对应的浮点向量列表。

        Raises:
            NotImplementedError: 抽象基类不提供具体的 Embedding 实现。
        """
        raise NotImplementedError


class MockEmbeddingProvider(EmbeddingProvider):
    """用于本地开发和测试的确定性 Mock Embedding Provider。"""

    dimension = 768

    def embed_texts(
        self,
        texts: Sequence[str],
    ) -> list[list[float]]:
        """将文本转换为确定性的归一化 Mock 向量。

        该实现不调用外部模型服务，只根据文本字符的稳定 hash
        将特征映射到固定维度的向量中。

        Args:
            texts: 待转换的文本序列。

        Returns:
            与输入顺序对应的 768 维浮点向量列表。

        Raises:
            ValueError: 当输入文本为空或只包含空白字符时抛出。
        """
        embeddings: list[list[float]] = []

        for text in texts:
            if not text.strip():
                raise ValueError("Embedding text must not be blank.")

            vector = [0.0] * self.dimension

            for character in text:
                if character.isspace():
                    continue

                digest = hashlib.sha256(
                    character.encode("utf-8"),
                ).digest()

                index = int.from_bytes(
                    digest[:4],
                    byteorder="big",
                ) % self.dimension

                vector[index] += 1.0

            norm = math.sqrt(
                sum(value * value for value in vector),
            )

            if norm > 0:
                vector = [
                    value / norm
                    for value in vector
                ]

            embeddings.append(vector)

        return embeddings