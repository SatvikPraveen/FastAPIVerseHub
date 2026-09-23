"""Declarative base, shared column types and reusable mixins.

All models MUST inherit from :class:`Base` so that ``Base.metadata`` is
complete and Alembic can autogenerate migrations in one pass.

The models use SQLAlchemy 2.0's typed ``Mapped[]`` / ``mapped_column()``
style: attribute types are real Python types, which lets mypy check service
code that reads and writes them.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from sqlalchemy import JSON, MetaData, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.models.types import UTCDateTime

# Deterministic constraint names make Alembic migrations reviewable and
# reversible (unnamed constraints cannot be dropped portably).
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Single shared declarative base."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)

    # Python annotation -> column type defaults.  ``datetime`` becomes an
    # aware UTC column everywhere without repeating ``UTCDateTime`` per field.
    type_annotation_map = {
        datetime: UTCDateTime,
        dict[str, Any]: JSON,
        list[str]: JSON,
        list[Any]: JSON,
    }


# Reusable annotated column shapes -------------------------------------------

IntPK = Annotated[int, mapped_column(primary_key=True, index=True)]
"""Auto-increment integer primary key."""


class TimestampMixin:
    """``created_at`` (set by the database) and ``updated_at`` (bumped on UPDATE)."""

    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime | None] = mapped_column(onupdate=func.now())


class SoftDeleteMixin:
    """``deleted_at`` marker for rows that must survive for audit purposes."""

    deleted_at: Mapped[datetime | None] = mapped_column(default=None)

    @property
    def is_soft_deleted(self) -> bool:
        return self.deleted_at is not None
