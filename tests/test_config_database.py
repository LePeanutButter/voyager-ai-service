"""Construcción de DATABASE_URL y validadores relacionados en Settings."""

from __future__ import annotations

from pydantic_settings import SettingsConfigDict

from app.core.config import Settings


class SettingsNoEnv(Settings):
    """Misma definición que Settings pero sin leer `.env` (tests reproducibles)."""

    model_config = SettingsConfigDict(
        env_file=None,
        case_sensitive=True,
        env_ignore_empty=True,
    )


def test_database_url_assembled_from_db_credentials():
    s = SettingsNoEnv(
        DATABASE_URL=None,
        DB_HOST="localhost",
        DB_USERNAME="user_a",
        DB_PASSWORD="secret_x",
        DB_NAME="mydb",
        DB_PORT=5433,
        DB_SSLMODE="require",
    )
    url = s.resolved_database_url
    assert url.startswith("postgresql+psycopg2://")
    assert "localhost:5433" in url
    assert "mydb" in url
    assert "sslmode=require" in url


def test_database_url_empty_credentials_yield_sqlite_fallback():
    s = SettingsNoEnv(
        DATABASE_URL=None,
        DB_HOST="",
        DB_USERNAME="",
        DB_PASSWORD="",
    )
    assert "sqlite" in s.resolved_database_url.lower()


def test_allowed_origins_validator_branches():
    s_blank = SettingsNoEnv(ALLOWED_ORIGINS="")
    assert "localhost:3000" in s_blank.ALLOWED_ORIGINS
    s_list = SettingsNoEnv(ALLOWED_ORIGINS=["http://a", "http://b"])
    assert "http://a" in s_list.ALLOWED_ORIGINS and "http://b" in s_list.ALLOWED_ORIGINS
