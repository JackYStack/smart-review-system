from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Regulation(Base):
    """Regulation clause."""

    __tablename__ = "regulations"

    clause_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    source: Mapped[str] = mapped_column(String(255))
    clause_text: Mapped[str] = mapped_column(Text)
