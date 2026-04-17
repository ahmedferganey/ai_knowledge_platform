import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ChunkResult:
    chunk_id: uuid.UUID
    score: float


class VectorStoreProvider(ABC):
    """
    Abstract interface for vector storage backends.
    Concrete implementations (FAISS, pgvector, etc.) are injected at runtime.
    """

    @abstractmethod
    async def add_chunks(
        self,
        chunks: list[uuid.UUID],
        embeddings: list[list[float]],
        owner_id: uuid.UUID,
    ) -> None:
        """
        Persist chunk embeddings for the given owner.

        :param chunks: Ordered list of chunk UUIDs matching embeddings index.
        :param embeddings: Dense float vectors, one per chunk.
        :param owner_id: Scopes the write to the owner's isolated index.
        """

    @abstractmethod
    async def search(
        self,
        query_vector: list[float],
        k: int,
        owner_id: uuid.UUID,
    ) -> list[ChunkResult]:
        """
        Return the top-k nearest chunks for *owner_id* only.

        :param query_vector: Dense query embedding.
        :param k: Maximum number of results to return.
        :param owner_id: Restricts search to this owner's index.
        :returns: Results ordered by descending similarity score.
        """

    @abstractmethod
    async def delete_by_document(
        self,
        document_id: uuid.UUID,
        owner_id: uuid.UUID,
    ) -> None:
        """
        Remove all vectors belonging to *document_id* from *owner_id*'s index.
        """
