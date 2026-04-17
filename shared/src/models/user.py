import uuid
from datetime import datetime, timezone

from sqlalchemy import BigInteger, DateTime, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from shared.src.db.base import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    """
    Platform user profile.
    Credentials are managed by the external IdP; this record is created/synced
    lazily on first authenticated request (keyed by external_id = token sub claim).
    """

    __tablename__ = "users"
    __table_args__ = (
        Index("ix_users_external_id", "external_id", unique=True),
        Index("ix_users_email", "email", unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    external_id: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True
    )
    email: Mapped[str | None] = mapped_column(
        String(255), nullable=True, unique=True
    )
    role: Mapped[str] = mapped_column(
        String(50), nullable=False, default="reader"
    )
    query_rate_limit_per_minute: Mapped[int] = mapped_column(
        Integer, nullable=False, default=20
    )
    storage_quota_bytes: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=1_073_741_824  # 1 GB
    )
    used_storage_bytes: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0
    )
    # Reserved for future multi-tenancy — NULL in v1.
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} role={self.role!r}>"
