"""Runtime persistence models for production-ready service state."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class UserProfileRecord(Base):
    __tablename__ = "runtime_user_profiles"

    user_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(255))
    age: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    preferences_json: Mapped[str] = mapped_column(Text)
    travel_history_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class UserInteractionRecord(Base):
    __tablename__ = "runtime_user_interactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    activity_id: Mapped[str] = mapped_column(String(128), index=True)
    interaction_type: Mapped[str] = mapped_column(String(64))
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
    metadata_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class MatchingProfileRecord(Base):
    __tablename__ = "runtime_matching_profiles"

    user_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    profile_json: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class MatchingConnectionRecord(Base):
    __tablename__ = "runtime_matching_connections"

    connection_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    initiator_id: Mapped[str] = mapped_column(String(128), index=True)
    target_user_id: Mapped[str] = mapped_column(String(128), index=True)
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    response_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class BehaviorEventRecord(Base):
    __tablename__ = "runtime_behavior_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    interaction_type: Mapped[str] = mapped_column(String(64))
    activity_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    activity_category: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    session_duration: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    context_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)


class PreferenceSessionRecord(Base):
    __tablename__ = "runtime_preference_sessions"

    session_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    answers_json: Mapped[str] = mapped_column(Text)
    step_index: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ChatSessionRecord(Base):
    __tablename__ = "runtime_chat_sessions"

    user_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    context_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ChatMessageRecord(Base):
    __tablename__ = "runtime_chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    role: Mapped[str] = mapped_column(String(32))
    content: Mapped[str] = mapped_column(Text)
    intent: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)


class TrendSignalRecord(Base):
    __tablename__ = "runtime_trend_signals"

    destination_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    country: Mapped[str] = mapped_column(String(255))
    tags_json: Mapped[str] = mapped_column(Text)
    previous: Mapped[int] = mapped_column(Integer)
    current: Mapped[int] = mapped_column(Integer)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class TrendSegmentRecord(Base):
    __tablename__ = "runtime_trend_segments"

    segment_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    payload_json: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class SeasonalityProfileRecord(Base):
    __tablename__ = "runtime_seasonality_profiles"

    destination_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    country: Mapped[str] = mapped_column(String(255))
    monthly_indices_json: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

