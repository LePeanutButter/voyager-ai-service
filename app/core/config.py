"""Centralized microservice configuration (environment variables and defaults).

Responsibilities:
    Define `Settings` with Pydantic Settings and expose the global `settings`
    instance for LLM, chat, matching, trends, model paths, and CORS.

Dependencies:
    `pydantic_settings.BaseSettings`, optional `.env` file.
"""

from __future__ import annotations

from typing import List, Optional
from urllib.parse import quote_plus

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings

# Origen browser típico cuando el front resuelve el DNS público de la instancia EC2
# (p. ej. Learner Lab). No coincide con IP literal ni con otros dominios.
_EC2_COMPUTE_PUBLIC_DNS_ORIGIN_REGEX = (
    r"^https?://ec2-(?:\d{1,3}-){3}\d{1,3}\.[a-z0-9.-]+\.amazonaws\.com(?::\d+)?$"
)


class Settings(BaseSettings):
    """Application parameters loaded from environment variables and `.env`.

    Groups service, API, ML, Redis (placeholder), LLM integration flags,
    recommendation/matching limits, and windows for trends and adaptive UI.

    Attributes:
        Declared fields (see body): all configurable via env with the same name
        and `case_sensitive=True` in `Config`.
    """

    # Service configuration
    SERVICE_NAME: str = "tourism-assistant"
    VERSION: str = "1.0.0"
    DEBUG: bool = False
    SERVICE_DESCRIPTION: str = (
        "AI-powered microservice for personalized travel recommendations, "
        "conversational trip planning, traveler matching, predictive travel trends, "
        "and adaptive UI driven by behavior signals"
    )

    # API configuration
    API_V1_STR: str = "/api/v1"
    # CORS: lista explícita. En env puedes usar CSV: http://localhost:3000,http://1.2.3.4:5173
    ALLOWED_ORIGINS: List[str] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://localhost:8080",
            "http://localhost:5173",
        ],
    )
    # Regex adicional (sin usar *). Útil para patrones de laboratorio (p. ej. Vocareum).
    CORS_ALLOW_ORIGIN_REGEX: str = Field(
        default="",
        description="Regex de origen permitido además de ALLOWED_ORIGINS. Vacío = desactivado.",
    )
    # Learner Lab / EC2: permite solo hostnames ec2-*.…amazonaws.com (no IP suelta ni *).
    CORS_ALLOW_EC2_COMPUTE_DNS: bool = Field(
        default=False,
        description="Activa regex acotada a DNS público compute.amazonaws.com típico de EC2.",
    )

    # Database: SQLite by default; set DB_HOST + DB_USERNAME + DB_PASSWORD for PostgreSQL
    # (local o RDS), alineado con voyager-backend-core (variables separadas + ssl opcional).
    DATABASE_URL: Optional[str] = Field(
        default=None,
        description="SQLAlchemy URL. Si no se define, se construye desde DB_* o se usa SQLite.",
    )
    DB_HOST: str = ""
    DB_PORT: int = 5432
    DB_NAME: str = "tourism_ai"
    DB_USERNAME: str = ""
    DB_PASSWORD: str = ""
    # RDS: usar "require" igual que JDBC ?sslmode=require en Spring.
    DB_SSLMODE: str = ""

    # ML Model configuration
    MODEL_PATH: str = "./app/ml/models"
    RECOMMENDATION_MODEL: str = "recommendation_model.pkl"
    USER_PROFILING_MODEL: str = "user_profiling_model.pkl"
    MATCHING_MODEL: str = "traveler_matching_model.pkl"

    # Redis configuration (for caching - placeholder)
    REDIS_URL: str = "redis://localhost:6379"
    CACHE_TTL: int = 3600  # 1 hour

    # External API configuration (placeholder)
    WEATHER_API_KEY: str = ""
    MAPS_API_KEY: str = ""

    # Logging configuration
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # Recommendation engine settings
    MAX_RECOMMENDATIONS: int = 10
    SIMILARITY_THRESHOLD: float = 0.7
    DEFAULT_LOCATION_RADIUS: float = 50.0  # km

    # User profiling settings
    PROFILE_UPDATE_THRESHOLD: int = 5  # minimum interactions before profile update
    PREFERENCE_DECAY_FACTOR: float = 0.9  # for time-based preference weighting

    # Matching algorithm settings
    MAX_MATCHES: int = 20
    MIN_COMPATIBILITY_SCORE: float = 0.6
    # PBI 24: minimum destination–profile compatibility (0–1) to surface a card
    DESTINATION_MIN_COMPATIBILITY: float = 0.80

    # Feature 15 — predictive trends (PBI 30)
    TREND_ANALYSIS_WINDOW_DAYS: int = 30
    TREND_EMERGENCE_SURGE_RATIO: float = 0.50  # 50% growth vs previous window marks emerging

    # Feature 16 — adaptive UI (PBI 32–33)
    ADAPTIVE_UI_ANALYSIS_WINDOW_DAYS: int = 30
    ADAPTIVE_UI_PRIMARY_NAV_SLOTS: int = 5
    ADAPTIVE_UI_THEME_BOOST_DELTA: float = 0.12

    # -----------------------------------------------------------------------
    # Seasonality (digital-transformation.tex: SARIMA s=12, mitigación, visibilidad)
    # -----------------------------------------------------------------------
    SEASONALITY_HISTORY_MONTHS: int = 36
    SEASONALITY_AMPLITUDE: float = 0.38
    SEASONALITY_MITIGATION_STRENGTH: float = 0.22
    SEASONALITY_PEAK_THRESHOLD: float = 1.12
    SEASONALITY_OFFPEAK_THRESHOLD: float = 0.88
    SEASONALITY_PEAK_DAMP_CAP: float = 0.45
    SEASONALITY_MULT_MIN: float = 0.82
    SEASONALITY_MULT_MAX: float = 1.18

    # -----------------------------------------------------------------------
    # LLM Integration settings
    # LLM_PROVIDER: "openai" | "openai_compatible" | "ollama" | "none"
    # Set to "none" (default) to run in rule-based fallback mode only.
    # -----------------------------------------------------------------------
    LLM_PROVIDER: str = "none"
    LLM_API_KEY: str = ""
    LLM_BASE_URL: str = "https://api.openai.com/v1"
    LLM_MODEL: str = "gpt-4o-mini"
    LLM_MAX_TOKENS: int = 1024
    LLM_TEMPERATURE: float = 0.7

    # -----------------------------------------------------------------------
    # Chat feature settings
    # -----------------------------------------------------------------------
    # Maximum messages to retain per user session (oldest evicted when exceeded)
    CHAT_MAX_HISTORY: int = 20
    # Maximum suggestions returned per chat turn
    CHAT_MAX_SUGGESTIONS: int = 5

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def _parse_allowed_origins(cls, v):
        if v is None:
            return v
        if isinstance(v, str):
            return [x.strip() for x in v.split(",") if x.strip()]
        return v

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def _empty_db_url_as_none(cls, v: Optional[str]) -> Optional[str]:
        if v is None or (isinstance(v, str) and not v.strip()):
            return None
        return v

    @model_validator(mode="after")
    def _assemble_database_url(self) -> Settings:
        if self.DATABASE_URL:
            return self
        if self.DB_HOST and self.DB_USERNAME and self.DB_PASSWORD:
            user = quote_plus(self.DB_USERNAME)
            pwd = quote_plus(self.DB_PASSWORD)
            ssl_q = f"?sslmode={self.DB_SSLMODE}" if (self.DB_SSLMODE or "").strip() else ""
            object.__setattr__(
                self,
                "DATABASE_URL",
                (
                    f"postgresql+psycopg2://{user}:{pwd}@{self.DB_HOST}:{self.DB_PORT}/"
                    f"{self.DB_NAME}{ssl_q}"
                ),
            )
        else:
            object.__setattr__(self, "DATABASE_URL", "sqlite:///./tourism_assistant.db")
        return self

    @property
    def resolved_database_url(self) -> str:
        """URL efectiva tras validadores (siempre definida)."""
        assert self.DATABASE_URL is not None
        return self.DATABASE_URL

    @property
    def resolved_cors_origin_regex(self) -> Optional[str]:
        """Patrón único o alternancia para CORSMiddleware.allow_origin_regex."""
        parts: List[str] = []
        if self.CORS_ALLOW_EC2_COMPUTE_DNS:
            parts.append(_EC2_COMPUTE_PUBLIC_DNS_ORIGIN_REGEX)
        custom = (self.CORS_ALLOW_ORIGIN_REGEX or "").strip()
        if custom:
            parts.append(f"({custom})")
        if not parts:
            return None
        return "|".join(parts) if len(parts) > 1 else parts[0]

    class Config:
        env_file = ".env"
        case_sensitive = True


# Create global settings instance
settings = Settings()
