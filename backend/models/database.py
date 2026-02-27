"""Database models and setup for Kairo"""

from datetime import datetime, timezone
from sqlalchemy import (
    create_engine, Column, String, Float, Boolean, Integer,
    DateTime, Text, JSON, ForeignKey, Enum as SAEnum
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
import uuid
import enum

Base = declarative_base()


def generate_id():
    return str(uuid.uuid4())


def utcnow():
    return datetime.now(timezone.utc)


# ── Enums ──

class AgentStatus(str, enum.Enum):
    DRAFT = "draft"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"


class ActionStatus(str, enum.Enum):
    EXECUTED = "executed"
    QUEUED = "queued_for_review"
    OVERRIDDEN = "overridden"
    REJECTED = "rejected"


# ── Models ──

class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=generate_id)
    email = Column(String, unique=True, nullable=False, index=True)
    username = Column(String, unique=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, default="")
    avatar_url = Column(String, default="")
    preferred_language = Column(String, default="en")  # en, hi, auto
    timezone = Column(String, default="Asia/Kolkata")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    # Relationships
    agents = relationship("AgentConfig", back_populates="user", cascade="all, delete-orphan")
    actions = relationship("AgentAction", back_populates="user", cascade="all, delete-orphan")
    preferences = relationship("UserPreference", back_populates="user", cascade="all, delete-orphan")


class AgentConfig(Base):
    """User's personal Kairo agent configuration"""
    __tablename__ = "agent_configs"

    id = Column(String, primary_key=True, default=generate_id)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    name = Column(String, default="My Kairo Agent")
    status = Column(String, default=AgentStatus.DRAFT)

    # Ghost Mode settings
    ghost_mode_enabled = Column(Boolean, default=False)
    ghost_mode_confidence_threshold = Column(Float, default=0.85)
    ghost_mode_allowed_actions = Column(JSON, default=lambda: [
        "reply_email", "reply_slack", "reply_teams", "decline_meeting"
    ])
    ghost_mode_vip_contacts = Column(JSON, default=list)
    ghost_mode_blocked_contacts = Column(JSON, default=list)
    ghost_mode_max_spend_per_action = Column(Float, default=25.0)
    ghost_mode_max_spend_per_day = Column(Float, default=100.0)

    # Scheduling settings
    deep_work_start = Column(String, default="09:00")
    deep_work_end = Column(String, default="11:00")
    deep_work_days = Column(JSON, default=lambda: ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"])
    max_meetings_per_day = Column(Integer, default=6)
    auto_decline_enabled = Column(Boolean, default=False)

    # Voice settings
    voice_language = Column(String, default="auto")  # en, hi, auto
    voice_gender = Column(String, default="female")
    briefing_time = Column(String, default="07:00")
    briefing_enabled = Column(Boolean, default=True)

    # Integrations
    composio_connected = Column(Boolean, default=False)
    gmail_connected = Column(Boolean, default=False)
    slack_connected = Column(Boolean, default=False)
    teams_connected = Column(Boolean, default=False)
    calendar_connected = Column(Boolean, default=False)
    github_connected = Column(Boolean, default=False)

    # Graph data (NetworkX serialized)
    relationship_graph_data = Column(JSON, default=dict)

    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    user = relationship("User", back_populates="agents")
    actions = relationship("AgentAction", back_populates="agent", cascade="all, delete-orphan")


class AgentAction(Base):
    """Every action Kairo takes — the Decision Log"""
    __tablename__ = "agent_actions"

    id = Column(String, primary_key=True, default=generate_id)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    agent_id = Column(String, ForeignKey("agent_configs.id"), nullable=False)
    timestamp = Column(DateTime, default=utcnow)

    # Action details
    action_type = Column(String, nullable=False)  # email_reply, meeting_decline, slack_reply, teams_reply, purchase, escalated
    channel = Column(String, default="email")  # email, slack, teams, calendar
    target_contact = Column(String, default="")
    language_used = Column(String, default="en")

    # Content
    original_message_summary = Column(Text, default="")
    action_taken = Column(Text, default="")
    draft_content = Column(Text, default="")

    # Reasoning
    confidence_score = Column(Float, default=0.0)
    reasoning = Column(Text, default="")
    factors = Column(JSON, default=list)

    # Status
    status = Column(String, default=ActionStatus.EXECUTED)
    user_feedback = Column(String, default="")  # approved, edited, rejected
    edited_content = Column(Text, default="")

    # Financial
    amount_spent = Column(Float, default=0.0)
    estimated_time_saved_minutes = Column(Float, default=0.0)

    user = relationship("User", back_populates="actions")
    agent = relationship("AgentConfig", back_populates="actions")


class UserPreference(Base):
    """Learned preferences from feedback loop"""
    __tablename__ = "user_preferences"

    id = Column(String, primary_key=True, default=generate_id)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    preference_key = Column(String, nullable=False)
    preference_value = Column(String, default="")
    confidence = Column(Float, default=0.5)
    source = Column(String, default="learned")  # explicit, learned
    learned_from_count = Column(Integer, default=0)
    last_updated = Column(DateTime, default=utcnow, onupdate=utcnow)

    user = relationship("User", back_populates="preferences")


class ContactRelationship(Base):
    """Persistent relationship data (synced from NetworkX)"""
    __tablename__ = "contact_relationships"

    id = Column(String, primary_key=True, default=generate_id)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    contact_name = Column(String, nullable=False)
    contact_email = Column(String, default="")
    contact_slack_id = Column(String, default="")
    contact_teams_id = Column(String, default="")
    relationship_type = Column(String, default="colleague")
    importance_score = Column(Float, default=0.5)
    preferred_channel = Column(String, default="email")
    preferred_language = Column(String, default="en")
    tone = Column(String, default="professional")
    formality_score = Column(Float, default=0.5)
    greeting_style = Column(String, default="Hi")
    sign_off_style = Column(String, default="Best")
    uses_emoji = Column(Boolean, default=False)
    avg_message_length = Column(Integer, default=50)
    recent_sentiment_trend = Column(String, default="neutral")
    sentiment_scores = Column(JSON, default=list)
    interaction_count = Column(Integer, default=0)
    last_interaction = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)


# ── Database Setup ──

def get_engine(database_url: str):
    if database_url.startswith("sqlite"):
        return create_engine(database_url, connect_args={"check_same_thread": False})
    return create_engine(database_url)


def create_session_factory(engine):
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db(database_url: str):
    engine = get_engine(database_url)
    Base.metadata.create_all(bind=engine)
    return engine
