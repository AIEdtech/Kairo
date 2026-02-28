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


class CommitmentStatus(str, enum.Enum):
    ACTIVE = "active"
    FULFILLED = "fulfilled"
    OVERDUE = "overdue"
    BROKEN = "broken"
    CANCELLED = "cancelled"


class DelegationStatus(str, enum.Enum):
    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class ListingStatus(str, enum.Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    REMOVED = "removed"


class TransactionStatus(str, enum.Enum):
    COMPLETED = "completed"
    PENDING = "pending"
    FAILED = "failed"
    REFUNDED = "refunded"


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

    # Flow State Guardian settings
    flow_guardian_enabled = Column(Boolean, default=True)
    flow_auto_respond_text = Column(String, default="In deep focus right now. I'll get back to you shortly.")
    flow_urgency_threshold = Column(Float, default=0.9)
    flow_min_duration_minutes = Column(Integer, default=15)

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


class MarketplaceListing(Base):
    """A capability listed for sale on the marketplace"""
    __tablename__ = "marketplace_listings"

    id = Column(String, primary_key=True, default=generate_id)
    seller_user_id = Column(String, ForeignKey("users.id"), nullable=False)
    agent_id = Column(String, ForeignKey("agent_configs.id"), nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text, default="")
    category = Column(String, default="custom")
    tags = Column(JSON, default=list)
    capability_type = Column(String, default="task")
    price_per_use = Column(Float, nullable=False)
    currency = Column(String, default="USD")
    status = Column(String, default=ListingStatus.ACTIVE)
    is_featured = Column(Boolean, default=False)
    total_purchases = Column(Integer, default=0)
    avg_rating = Column(Float, default=0.0)
    total_reviews = Column(Integer, default=0)
    total_earnings = Column(Float, default=0.0)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    seller = relationship("User", foreign_keys=[seller_user_id])
    agent = relationship("AgentConfig", foreign_keys=[agent_id])


class MarketplaceTransaction(Base):
    """A purchase of a marketplace capability"""
    __tablename__ = "marketplace_transactions"

    id = Column(String, primary_key=True, default=generate_id)
    listing_id = Column(String, ForeignKey("marketplace_listings.id"), nullable=False)
    buyer_user_id = Column(String, ForeignKey("users.id"), nullable=False)
    seller_user_id = Column(String, ForeignKey("users.id"), nullable=False)
    buyer_agent_id = Column(String, ForeignKey("agent_configs.id"), nullable=False)
    amount = Column(Float, nullable=False)
    currency = Column(String, default="USD")
    skyfire_transaction_id = Column(String, default="")
    platform_fee = Column(Float, default=0.0)
    seller_earnings = Column(Float, default=0.0)
    status = Column(String, default=TransactionStatus.COMPLETED)
    task_description = Column(Text, default="")
    result_summary = Column(Text, default="")
    rating = Column(Integer, nullable=True)
    review_text = Column(Text, default="")
    created_at = Column(DateTime, default=utcnow)
    completed_at = Column(DateTime, nullable=True)

    listing = relationship("MarketplaceListing", foreign_keys=[listing_id])
    buyer = relationship("User", foreign_keys=[buyer_user_id])
    seller = relationship("User", foreign_keys=[seller_user_id])


class Commitment(Base):
    """Promises detected in outgoing messages"""
    __tablename__ = "commitments"

    id = Column(String, primary_key=True, default=generate_id)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    agent_id = Column(String, ForeignKey("agent_configs.id"), nullable=False)

    # What was promised
    raw_text = Column(Text, nullable=False)
    parsed_commitment = Column(Text, default="")
    target_contact = Column(String, default="")
    channel = Column(String, default="email")

    # When
    detected_at = Column(DateTime, default=utcnow)
    deadline = Column(DateTime, nullable=True)
    deadline_source = Column(String, default="extracted")

    # Status
    status = Column(String, default=CommitmentStatus.ACTIVE)
    fulfilled_at = Column(DateTime, nullable=True)

    # Correlation
    related_action_id = Column(String, nullable=True)
    sentiment_impact = Column(Float, default=0.0)

    # Ghost mode
    ghost_fulfillable = Column(Boolean, default=False)
    ghost_action_type = Column(String, default="")

    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    user = relationship("User", foreign_keys=[user_id])
    agent = relationship("AgentConfig", foreign_keys=[agent_id])


class DelegationRequest(Base):
    """Smart delegation between mesh agents"""
    __tablename__ = "delegation_requests"

    id = Column(String, primary_key=True, default=generate_id)
    from_user_id = Column(String, ForeignKey("users.id"), nullable=False)
    to_user_id = Column(String, ForeignKey("users.id"), nullable=False)

    # Task details
    task_description = Column(Text, nullable=False)
    task_source = Column(String, default="")
    source_channel = Column(String, default="email")
    original_sender = Column(String, default="")

    # Why this person
    match_score = Column(Float, default=0.0)
    match_reasons = Column(JSON, default=list)
    expertise_match = Column(Float, default=0.0)
    bandwidth_score = Column(Float, default=0.0)
    relationship_strength = Column(Float, default=0.0)

    # Status
    status = Column(String, default=DelegationStatus.PROPOSED)
    response_note = Column(Text, default="")

    # Tracking
    deadline = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    from_user = relationship("User", foreign_keys=[from_user_id])
    to_user = relationship("User", foreign_keys=[to_user_id])


class BurnoutSnapshot(Base):
    """Periodic burnout risk and workload analysis"""
    __tablename__ = "burnout_snapshots"

    id = Column(String, primary_key=True, default=generate_id)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)

    snapshot_date = Column(DateTime, default=utcnow)

    # Scores (0-100)
    burnout_risk_score = Column(Float, default=0.0)
    workload_score = Column(Float, default=0.0)
    relationship_health_score = Column(Float, default=0.0)

    # Factors
    avg_daily_meetings = Column(Float, default=0.0)
    avg_response_time_hours = Column(Float, default=0.0)
    deep_work_hours_weekly = Column(Float, default=0.0)
    messages_sent_daily = Column(Float, default=0.0)
    after_hours_activity_pct = Column(Float, default=0.0)

    # Predictions
    predicted_cold_contacts = Column(JSON, default=list)
    productivity_multipliers = Column(JSON, default=dict)
    workload_trajectory = Column(String, default="stable")

    # Interventions
    recommended_interventions = Column(JSON, default=list)

    created_at = Column(DateTime, default=utcnow)

    user = relationship("User", foreign_keys=[user_id])


class DecisionReplay(Base):
    """Counterfactual analysis of past decisions"""
    __tablename__ = "decision_replays"

    id = Column(String, primary_key=True, default=generate_id)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    source_action_id = Column(String, ForeignKey("agent_actions.id"), nullable=False)

    # The original decision
    original_decision = Column(String, default="")
    original_outcome = Column(Text, default="")

    # The counterfactual
    counterfactual_decision = Column(String, default="")
    counterfactual_cascade = Column(JSON, default=list)

    # Impact
    time_impact_minutes = Column(Float, default=0.0)
    relationship_impact = Column(JSON, default=dict)
    productivity_impact = Column(Float, default=0.0)

    # Verdict
    verdict = Column(String, default="")
    confidence = Column(Float, default=0.0)

    created_at = Column(DateTime, default=utcnow)

    user = relationship("User", foreign_keys=[user_id])
    source_action = relationship("AgentAction", foreign_keys=[source_action_id])


class FlowSession(Base):
    """Flow state protection sessions"""
    __tablename__ = "flow_sessions"

    id = Column(String, primary_key=True, default=generate_id)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    agent_id = Column(String, ForeignKey("agent_configs.id"), nullable=False)

    # Session timing
    started_at = Column(DateTime, default=utcnow)
    ended_at = Column(DateTime, nullable=True)
    duration_minutes = Column(Float, default=0.0)

    # Detection signals
    trigger_signals = Column(JSON, default=list)
    flow_score = Column(Float, default=0.0)

    # Protection actions taken
    messages_held = Column(Integer, default=0)
    messages_escalated = Column(Integer, default=0)
    auto_responses_sent = Column(Integer, default=0)
    meetings_auto_declined = Column(Integer, default=0)

    # Debrief
    held_messages = Column(JSON, default=list)
    debrief_delivered = Column(Boolean, default=False)
    debrief_at = Column(DateTime, nullable=True)

    # Impact
    estimated_focus_saved_minutes = Column(Float, default=0.0)

    created_at = Column(DateTime, default=utcnow)

    user = relationship("User", foreign_keys=[user_id])
    agent = relationship("AgentConfig", foreign_keys=[agent_id])


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
