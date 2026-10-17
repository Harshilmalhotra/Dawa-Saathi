from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.db import Base

def uid() -> str:
    return str(uuid4())

def utcnow() -> datetime:
    return datetime.now(timezone.utc)

class Case(Base):
    __tablename__ = "cases"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    access_code: Mapped[str] = mapped_column(String(6), unique=True, index=True)
    status: Mapped[str] = mapped_column(String, default="uploaded")
    language: Mapped[str] = mapped_column(String(2), default="en")
    telegram_chat_id: Mapped[str | None] = mapped_column(String, nullable=True)
    doctor_notes_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    consent_given: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

class Image(Base):
    __tablename__ = "images"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String)
    storage_key: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

class Medicine(Base):
    __tablename__ = "medicines"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    source_text: Mapped[str] = mapped_column(Text)
    drug_name: Mapped[str | None] = mapped_column(String, nullable=True)
    drug_name_conf: Mapped[float] = mapped_column(Float, default=0)
    strength: Mapped[str | None] = mapped_column(String, nullable=True)
    strength_conf: Mapped[float] = mapped_column(Float, default=0)
    frequency_code: Mapped[str | None] = mapped_column(String, nullable=True)
    frequency_conf: Mapped[float] = mapped_column(Float, default=0)
    as_needed: Mapped[bool] = mapped_column(Boolean, default=False)
    food_timing: Mapped[str | None] = mapped_column(String, nullable=True)
    food_timing_conf: Mapped[float] = mapped_column(Float, default=0)
    duration_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_conf: Mapped[float] = mapped_column(Float, default=0)
    matched_strip_image_id: Mapped[str | None] = mapped_column(ForeignKey("images.id"), nullable=True)
    strip_match_status: Mapped[str] = mapped_column(String, default="none")
    review_status: Mapped[str] = mapped_column(String, default="needs_review")

class ReminderJob(Base):
    __tablename__ = "reminder_jobs"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    medicine_id: Mapped[str] = mapped_column(ForeignKey("medicines.id", ondelete="CASCADE"))
    slot: Mapped[str] = mapped_column(String)
    fire_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    sent: Mapped[bool] = mapped_column(Boolean, default=False)

class TelegramLinkToken(Base):
    __tablename__ = "telegram_link_tokens"
    token: Mapped[str] = mapped_column(String, primary_key=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used: Mapped[bool] = mapped_column(Boolean, default=False)

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    actor: Mapped[str] = mapped_column(String)
    action: Mapped[str] = mapped_column(String)
    detail_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
