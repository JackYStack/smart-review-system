from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class BasisItem(Base):
    __tablename__ = "basis_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    basis_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    scheme_type_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("scheme_types.id", ondelete="SET NULL"), nullable=True, index=True
    )
    doc_type: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    standard_no: Mapped[str] = mapped_column(String(128), nullable=False, default="", index=True)
    doc_name: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    effect_status: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    is_mandatory: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    scheme_category: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    scheme_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    scheme_type = relationship("SchemeType")
