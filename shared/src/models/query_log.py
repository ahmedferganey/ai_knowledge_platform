import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from shared.src.db.base import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class QueryLog(Base):
    """
    Append-only audit and observability record for every query event.
    Never used to serve responses — analytics and debugging only.
    """

    __tablename__ = "query_logs"
    __table_args__ = (
        Index("ix_query_logs_user_created", "user_id", "created_at"),
        Index("ix_query_logs_query_hash", "query_hash"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    # Reserved for future multi-tenancy — NULL in v1.
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), nullable=True
    )
    query_hash: Mapped[str] = mapped_column(
        String(64), nullable=False
    )  # SHA-256 of normalized query text
    response_latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cache_hit: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    degraded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    top_k_requested: Mapped[int | None] = mapped_column(Integer, nullable=True)
    chunks_retrieved: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    def __repr__(self) -> str:
        return (
            f"<QueryLog id={self.id} cache_hit={self.cache_hit} "
            f"degraded={self.degraded}>"
        )
