from sqlalchemy import String, Text, Integer, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base, UUIDMixin, TimestampMixin


class FaqEntry(Base, UUIDMixin, TimestampMixin):
    """A question and answer shown to every signed-in user on Help & Reference.

    Authored only by system_admin. `answer_html` holds the allowlist-sanitised
    subset of HTML produced by app.richtext -- never raw author input.
    """

    __tablename__ = "faq_entries"

    category: Mapped[str] = mapped_column(String(80), nullable=False, default="General", index=True)
    question: Mapped[str] = mapped_column(String(300), nullable=False)
    answer_html: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # Ordering is per-category; ties fall back to created_at so the list is stable.
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    is_published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
