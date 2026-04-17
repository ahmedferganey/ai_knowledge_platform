import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from shared.src.db.base import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Document(Base):
    """
    Metadata record for an uploaded document.
    Raw file bytes are NOT persisted after processing.

    Per-user deduplication is enforced via UniqueConstraint(owner_id, content_hash).
    """

    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint("owner_id", "content_hash", name="uq_documents_owner_hash"),
        Index("ix_documents_owner_id", "owner_id"),
        Index("ix_documents_content_hash", "content_hash"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    # Reserved for future multi-tenancy — NULL in v1.
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), nullable=True
    )
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    content_type: Mapped[str] = mapped_column(
        String(10), nullable=False
    )  # "pdf" | "docx" | "csv"
    content_hash: Mapped[str] = mapped_column(
        String(64), nullable=False
    )  # SHA-256 hex digest
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    processing_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )  # pending | processing | completed | failed
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )

    def __repr__(self) -> str:
        return (
            f"<Document id={self.id} filename={self.original_filename!r} "
            f"status={self.processing_status!r}>"
        )
