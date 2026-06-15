from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ReviewIssue(Base):
    """Persisted review issue."""

    __tablename__ = "review_issues"

    issue_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    task_id: Mapped[str] = mapped_column(String(64), index=True)
    severity: Mapped[str] = mapped_column(String(8))
    title: Mapped[str] = mapped_column(String(255))
