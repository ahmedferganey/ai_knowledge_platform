from abc import ABC, abstractmethod


class EmbeddingProvider(ABC):
    """
    Abstract interface for embedding backends.
    Concrete implementations (sentence-transformers, OpenAI embeddings, etc.)
    are injected at runtime.
    """

    @abstractmethod
    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """
        Produce dense embeddings for a batch of texts.

        :param texts: Input strings to embed.
        :returns: List of float vectors, one per input text, in the same order.
        """

    @abstractmethod
    async def embed_query(self, text: str) -> list[float]:
        """
        Produce a single embedding optimised for query-side retrieval.

        :param text: The user query string.
        :returns: A single dense float vector.
        """
