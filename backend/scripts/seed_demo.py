"""
Seed demo data — THREE colleagues on the same project, each with their own Kairo agent.

User 1: Gaurav Gupta  (gaurav@kairo.ai / demo1234)
  - Backend lead, bilingual EN+HI, deep work 9-11am
  - Agent: running, ghost mode ON, auto-decline ON, voice: male
  - Contacts: Phani (teammate), Sarah (manager), Rahul, Mike, CEO, Mom

User 2: Phani Kulkarni  (phani@kairo.ai / demo1234)
  - Frontend lead, English, deep work 10am-12pm
  - Agent: running, ghost mode ON, voice: female
  - Contacts: Gaurav (teammate), Sarah (manager), Jake (client), CEO

User 3: Demo User  (demo@kairo.ai / demo1234)
  - Product Manager, English, deep work 2-4pm
  - Agent: running, ghost mode ON, voice: female
  - Contacts: Gaurav, Phani, Sarah, CEO, Client (Jake)
  - Best account for reviewers — sees full cross-team activity

Run: cd backend && python scripts/seed_demo.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta, timezone
import random

from config import get_settings
from models.database import (
    init_db, User, AgentConfig, AgentAction, get_engine, create_session_factory,
    MarketplaceListing, MarketplaceTransaction, ListingStatus, TransactionStatus,
    Commitment, DelegationRequest, BurnoutSnapshot, DecisionReplay, FlowSession,
    CommitmentStatus, DelegationStatus,
)
from services.auth import hash_password
from services.relationship_graph import get_relationship_graph

settings = get_settings()
engine = init_db(settings.database_url)
Session = create_session_factory(engine)


def seed():
    db = Session()

    if db.query(User).filter(User.email == "gaurav@kairo.ai").first():
        print("Demo data already exists. Skipping.")
        db.close()
        return

    now = datetime.now(timezone.utc)

    # ═══════════════════════════════════════════
    # USER 1: GAURAV — Backend Lead
    # ═══════════════════════════════════════════

    gaurav = User(
        id="user-gaurav",
        email="gaurav@kairo.ai",
        username="gaurav",
        hashed_password=hash_password("demo1234"),
        full_name="Gaurav Gupta",
        preferred_language="auto",
        timezone="Asia/Kolkata",
    )
    db.add(gaurav)

    gaurav_agent = AgentConfig(
        id="agent-gaurav",
        user_id="user-gaurav",
        name="Gaurav's Kairo",
        status="running",
        ghost_mode_enabled=True,
        ghost_mode_confidence_threshold=0.85,
        ghost_mode_vip_contacts=["ceo@company.com", "investor@vc.com"],
        ghost_mode_max_spend_per_action=25.0,
        ghost_mode_max_spend_per_day=100.0,
        deep_work_start="09:00",
        deep_work_end="11:00",
        deep_work_days=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
        max_meetings_per_day=6,
        auto_decline_enabled=True,
        voice_language="auto",
        voice_gender="male",
        briefing_time="07:00",
        briefing_enabled=True,
        gmail_connected=True,
        slack_connected=True,
        teams_connected=True,
        calendar_connected=True,
        composio_connected=True,
    )
    db.add(gaurav_agent)

    # Gaurav's actions (last 7 days)
    gaurav_actions = [
        ("email_reply",      "email",    "Phani Kulkarni",    "en", 0.93, "executed",          "Replied to Phani's API integration question",           3.0, 0),
        ("email_reply",      "email",    "Rahul Verma",    "hi", 0.88, "executed",          "रिप्लाई — sprint standup notes in Hindi",               3.0, 0),
        ("teams_reply",      "teams",    "Phani Kulkarni",    "en", 0.91, "executed",          "Shared updated DB schema on Teams with Phani",          2.0, 0),
        ("teams_reply",      "teams",    "Sarah Kim",      "en", 0.72, "queued_for_review", "Queued — Sarah's tone shifted, confidence low",         0,   0),
        ("meeting_declined", "calendar", "Tom Wilson",      "en", 0.91, "executed",          "Auto-declined — conflicts with 9-11am deep work",      15.0, 0),
        ("slack_reply",      "slack",    "Phani Kulkarni",    "en", 0.95, "executed",          "Replied to Phani's design-system PR review on Slack",   2.0, 0),
        ("teams_reply",      "teams",    "Rahul Verma",    "hi", 0.87, "executed",          "Teams reply to Rahul in Hindi — project blocker",       3.0, 0),
        ("purchase",         "skyfire",  "Figma",          "en", 0.93, "executed",          "Auto-renewed Figma license via Skyfire",                2.0, 12.0),
        ("email_reply",      "email",    "Investor Mark",  "en", 0.62, "queued_for_review", "VIP — queued investor email for manual review",         0,   0),
        ("morning_briefing", "voice",    "System",         "en", 1.0,  "executed",          "Briefing: 4 meetings, 2 alerts, Phani blocked on API",  5.0, 0),
        ("email_reply",      "email",    "Mike Chen",      "en", 0.94, "executed",          "Follow-up on PR review with Mike",                      3.0, 0),
        ("slack_reply",      "slack",    "DevOps Bot",     "en", 0.98, "executed",          "Acknowledged deployment alert on Slack",                1.0, 0),
        ("meeting_declined", "calendar", "Sales Team",     "en", 0.86, "executed",          "Declined — exceeds 6 meeting daily limit",              30.0, 0),
        ("email_reply",      "email",    "Mom",            "hi", 0.96, "executed",          "Family reply in Hindi — warm tone",                     2.0, 0),
        ("mesh_meeting_scheduled", "mesh", "Phani Kulkarni",  "en", 1.0,  "executed",          "Gaurav's agent + Phani's agent auto-negotiated Wed 2pm", 10.0, 0),
        ("weekly_report",    "dashboard","System",         "en", 1.0,  "executed",          "Weekly report: 4.2 hrs saved, 91% accuracy",            15.0, 0),
    ]

    for atype, channel, contact, lang, conf, status, action, time_saved, amount in gaurav_actions:
        db.add(AgentAction(
            user_id="user-gaurav", agent_id="agent-gaurav",
            timestamp=now - timedelta(hours=random.randint(1, 168)),
            action_type=atype, channel=channel, target_contact=contact,
            language_used=lang, action_taken=action, confidence_score=conf,
            reasoning=f"[Gaurav's agent] {action}",
            factors=["relationship_score", "ghost_mode_threshold", "energy_state"],
            status=status, estimated_time_saved_minutes=time_saved,
            amount_spent=amount,
            user_feedback="approved" if status == "executed" else "",
        ))

    # Gaurav's relationship graph
    g_graph = get_relationship_graph("user-gaurav")
    g_contacts = [
        {"id": "phani",  "name": "Phani Kulkarni",     "type": "colleague", "importance": 0.9,  "channel": "teams",  "language": "en", "tone": "casual",       "greeting": "Hey Phani"},
        {"id": "sarah",  "name": "Sarah Kim",       "type": "manager",   "importance": 0.9,  "channel": "slack",  "language": "en", "tone": "professional", "greeting": "Hi Sarah"},
        {"id": "rahul",  "name": "Rahul Verma",     "type": "colleague", "importance": 0.7,  "channel": "teams",  "language": "hi", "tone": "casual",       "greeting": "Kya haal Rahul"},
        {"id": "mike",   "name": "Mike Chen",       "type": "colleague", "importance": 0.75, "channel": "email",  "language": "en", "tone": "casual",       "greeting": "Hey Mike"},
        {"id": "mark",   "name": "Investor Mark",   "type": "investor",  "importance": 0.95, "channel": "email",  "language": "en", "tone": "formal",       "greeting": "Dear Mark"},
        {"id": "tom",    "name": "Tom Wilson",       "type": "colleague", "importance": 0.3,  "channel": "email",  "language": "en", "tone": "professional", "greeting": "Hi Tom"},
        {"id": "mom",    "name": "Mom",              "type": "family",    "importance": 1.0,  "channel": "email",  "language": "hi", "tone": "casual",       "greeting": "Maa"},
        {"id": "ceo",    "name": "CEO Anika",        "type": "manager",   "importance": 1.0,  "channel": "email",  "language": "en", "tone": "formal",       "greeting": "Hi Anika"},
    ]
    for c in g_contacts:
        g_graph.add_or_update_contact(c["id"], c)
        for _ in range(random.randint(3, 10)):
            g_graph.record_interaction(c["id"], sentiment=random.uniform(0.4, 0.95), channel=c["channel"], language=c["language"])
    # Sarah's tone declining for Gaurav
    for _ in range(3):
        g_graph.record_interaction("sarah", sentiment=0.22, channel="slack", language="en")

    # ═══════════════════════════════════════════
    # USER 2: PHANI — Frontend Lead (same project)
    # ═══════════════════════════════════════════

    phani = User(
        id="user-phani",
        email="phani@kairo.ai",
        username="phani",
        hashed_password=hash_password("demo1234"),
        full_name="Phani Kulkarni",
        preferred_language="en",
        timezone="Asia/Kolkata",
    )
    db.add(phani)

    phani_agent = AgentConfig(
        id="agent-phani",
        user_id="user-phani",
        name="Phani's Kairo",
        status="running",
        ghost_mode_enabled=True,
        ghost_mode_confidence_threshold=0.80,
        ghost_mode_vip_contacts=["ceo@company.com"],
        ghost_mode_max_spend_per_action=20.0,
        ghost_mode_max_spend_per_day=75.0,
        deep_work_start="10:00",
        deep_work_end="12:00",
        deep_work_days=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
        max_meetings_per_day=5,
        auto_decline_enabled=True,
        voice_language="en",
        voice_gender="female",
        briefing_time="07:30",
        briefing_enabled=True,
        gmail_connected=True,
        slack_connected=True,
        teams_connected=True,
        calendar_connected=True,
        github_connected=True,
        composio_connected=True,
    )
    db.add(phani_agent)

    # Phani's actions (last 7 days)
    phani_actions = [
        ("email_reply",      "email",    "Gaurav Gupta",  "en", 0.94, "executed",          "Replied to Gaurav's schema update — asked about API",   3.0, 0),
        ("slack_reply",      "slack",    "Gaurav Gupta",  "en", 0.92, "executed",          "Discussed component architecture with Gaurav on Slack",  2.0, 0),
        ("teams_reply",      "teams",    "Sarah Kim",      "en", 0.89, "executed",          "Sent design mockup links to Sarah on Teams",            2.0, 0),
        ("email_reply",      "email",    "Jake Rivera",    "en", 0.85, "executed",          "Client update email to Jake — professional tone",       3.0, 0),
        ("meeting_declined", "calendar", "HR Team",        "en", 0.88, "executed",          "Auto-declined — conflicts with 10-12 deep work",       15.0, 0),
        ("slack_reply",      "slack",    "Design Bot",     "en", 0.97, "executed",          "Acknowledged Figma comment notification",               1.0, 0),
        ("email_reply",      "email",    "CEO Anika",      "en", 0.55, "queued_for_review", "VIP — queued CEO email for Phani's review",             0,   0),
        ("morning_briefing", "voice",    "System",         "en", 1.0,  "executed",          "Briefing: 3 meetings, Gaurav shared DB schema",         5.0, 0),
        ("purchase",         "skyfire",  "Vercel Pro",     "en", 0.91, "executed",          "Auto-upgraded Vercel plan via Skyfire",                  2.0, 20.0),
        ("teams_reply",      "teams",    "Gaurav Gupta",  "en", 0.90, "executed",          "Confirmed API contract changes with Gaurav",            2.0, 0),
        ("slack_reply",      "slack",    "Gaurav Gupta",  "en", 0.93, "executed",          "Sent PR link to Gaurav for frontend integration",       2.0, 0),
        ("mesh_meeting_scheduled", "mesh", "Gaurav Gupta", "en", 1.0,  "executed",         "Phani's agent + Gaurav's agent negotiated Wed 2pm sync", 10.0, 0),
        ("mesh_task_received",     "mesh", "Gaurav Gupta", "en", 1.0,  "executed",         "Received updated API spec from Gaurav's agent",         5.0, 0),
        ("weekly_report",    "dashboard","System",         "en", 1.0,  "executed",          "Weekly report: 3.5 hrs saved, 93% accuracy",            15.0, 0),
    ]

    for atype, channel, contact, lang, conf, status, action, time_saved, amount in phani_actions:
        db.add(AgentAction(
            user_id="user-phani", agent_id="agent-phani",
            timestamp=now - timedelta(hours=random.randint(1, 168)),
            action_type=atype, channel=channel, target_contact=contact,
            language_used=lang, action_taken=action, confidence_score=conf,
            reasoning=f"[Phani's agent] {action}",
            factors=["relationship_score", "ghost_mode_threshold", "energy_state"],
            status=status, estimated_time_saved_minutes=time_saved,
            amount_spent=amount,
            user_feedback="approved" if status == "executed" else "",
        ))

    # Phani's relationship graph
    p_graph = get_relationship_graph("user-phani")
    p_contacts = [
        {"id": "gaurav", "name": "Gaurav Gupta",   "type": "colleague", "importance": 0.9,  "channel": "teams",  "language": "en", "tone": "casual",       "greeting": "Hey Gaurav"},
        {"id": "sarah",  "name": "Sarah Kim",       "type": "manager",   "importance": 0.85, "channel": "teams",  "language": "en", "tone": "professional", "greeting": "Hi Sarah"},
        {"id": "jake",   "name": "Jake Rivera",     "type": "client",    "importance": 0.8,  "channel": "email",  "language": "en", "tone": "professional", "greeting": "Hi Jake"},
        {"id": "ceo",    "name": "CEO Anika",        "type": "manager",   "importance": 1.0,  "channel": "email",  "language": "en", "tone": "formal",       "greeting": "Hi Anika"},
        {"id": "mike",   "name": "Mike Chen",       "type": "colleague", "importance": 0.6,  "channel": "slack",  "language": "en", "tone": "casual",       "greeting": "Hey Mike"},
        {"id": "rahul",  "name": "Rahul Verma",     "type": "colleague", "importance": 0.5,  "channel": "teams",  "language": "en", "tone": "casual",       "greeting": "Hey Rahul"},
    ]
    for c in p_contacts:
        p_graph.add_or_update_contact(c["id"], c)
        for _ in range(random.randint(3, 10)):
            p_graph.record_interaction(c["id"], sentiment=random.uniform(0.5, 0.95), channel=c["channel"], language=c["language"])
    # Phani and Gaurav interact heavily (same project)
    for _ in range(8):
        p_graph.record_interaction("gaurav", sentiment=random.uniform(0.7, 0.95), channel="teams", language="en")

    # ═══════════════════════════════════════════
    # USER 3: DEMO USER — Product Manager (reviewer-friendly)
    # ═══════════════════════════════════════════

    demo = User(
        id="user-demo",
        email="demo@kairo.ai",
        username="demo",
        hashed_password=hash_password("demo1234"),
        full_name="Demo User",
        preferred_language="en",
        timezone="America/New_York",
    )
    db.add(demo)

    demo_agent = AgentConfig(
        id="agent-demo",
        user_id="user-demo",
        name="Demo's Kairo",
        status="running",
        ghost_mode_enabled=True,
        ghost_mode_confidence_threshold=0.80,
        ghost_mode_vip_contacts=["ceo@company.com"],
        ghost_mode_max_spend_per_action=20.0,
        ghost_mode_max_spend_per_day=80.0,
        deep_work_start="14:00",
        deep_work_end="16:00",
        deep_work_days=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
        max_meetings_per_day=5,
        auto_decline_enabled=True,
        voice_language="en",
        voice_gender="female",
        briefing_time="08:00",
        briefing_enabled=True,
        gmail_connected=True,
        slack_connected=True,
        teams_connected=True,
        calendar_connected=True,
        github_connected=True,
        composio_connected=True,
    )
    db.add(demo_agent)

    # Demo's actions (last 7 days) — covers all feature areas
    demo_actions = [
        ("email_reply",      "email",    "Gaurav Gupta",     "en", 0.92, "executed",          "Replied to Gaurav's sprint update — approved backend plan",   3.0, 0),
        ("email_reply",      "email",    "Phani Kulkarni",   "en", 0.90, "executed",          "Replied to Phani's design review — shared feedback",          3.0, 0),
        ("slack_reply",      "slack",    "Gaurav Gupta",     "en", 0.94, "executed",          "Discussed API timeline with Gaurav on Slack",                 2.0, 0),
        ("slack_reply",      "slack",    "Phani Kulkarni",   "en", 0.91, "executed",          "Approved Phani's component library PR on Slack",              2.0, 0),
        ("teams_reply",      "teams",    "Sarah Kim",        "en", 0.88, "executed",          "Sent weekly status update to Sarah on Teams",                 3.0, 0),
        ("teams_reply",      "teams",    "Jake Rivera",      "en", 0.85, "executed",          "Client check-in with Jake — professional tone",              3.0, 0),
        ("email_reply",      "email",    "CEO Anika",        "en", 0.58, "queued_for_review", "VIP — queued CEO strategy email for review",                  0,   0),
        ("teams_reply",      "teams",    "Sarah Kim",        "en", 0.68, "queued_for_review", "Queued — Sarah asked about budget, needs manual review",      0,   0),
        ("meeting_declined", "calendar", "Vendor Demo",      "en", 0.89, "executed",          "Auto-declined — conflicts with 2-4pm deep work block",       15.0, 0),
        ("meeting_declined", "calendar", "All-Hands Sync",   "en", 0.82, "executed",          "Declined — exceeds 5 meeting daily limit",                   30.0, 0),
        ("morning_briefing", "voice",    "System",           "en", 1.0,  "executed",          "Briefing: 5 meetings, 3 pending reviews, Gaurav shipped API", 5.0, 0),
        ("purchase",         "skyfire",  "Notion Team",      "en", 0.91, "executed",          "Auto-renewed Notion workspace via Skyfire",                   2.0, 15.0),
        ("slack_reply",      "slack",    "DevOps Bot",       "en", 0.97, "executed",          "Acknowledged CI/CD pipeline alert on Slack",                  1.0, 0),
        ("mesh_meeting_scheduled", "mesh", "Gaurav Gupta",   "en", 1.0,  "executed",          "Demo's agent + Gaurav's agent negotiated Thu 3pm sync",       10.0, 0),
        ("mesh_meeting_scheduled", "mesh", "Phani Kulkarni", "en", 1.0,  "executed",          "Demo's agent + Phani's agent negotiated Fri 11am design review", 10.0, 0),
        ("mesh_task_received",     "mesh", "Gaurav Gupta",   "en", 1.0,  "executed",          "Received deployment checklist from Gaurav's agent",           5.0, 0),
        ("weekly_report",    "dashboard","System",           "en", 1.0,  "executed",          "Weekly report: 5.1 hrs saved, 89% accuracy, $15 spent",      15.0, 0),
    ]

    for atype, channel, contact, lang, conf, status, action, time_saved, amount in demo_actions:
        db.add(AgentAction(
            user_id="user-demo", agent_id="agent-demo",
            timestamp=now - timedelta(hours=random.randint(1, 168)),
            action_type=atype, channel=channel, target_contact=contact,
            language_used=lang, action_taken=action, confidence_score=conf,
            reasoning=f"[Demo's agent] {action}",
            factors=["relationship_score", "ghost_mode_threshold", "energy_state"],
            status=status, estimated_time_saved_minutes=time_saved,
            amount_spent=amount,
            user_feedback="approved" if status == "executed" else "",
        ))

    # Demo's relationship graph — connects to both teams
    d_graph = get_relationship_graph("user-demo")
    d_contacts = [
        {"id": "gaurav", "name": "Gaurav Gupta",   "type": "colleague", "importance": 0.9,  "channel": "slack",  "language": "en", "tone": "casual",       "greeting": "Hey Gaurav"},
        {"id": "phani",  "name": "Phani Kulkarni",  "type": "colleague", "importance": 0.9,  "channel": "slack",  "language": "en", "tone": "casual",       "greeting": "Hey Phani"},
        {"id": "sarah",  "name": "Sarah Kim",       "type": "manager",   "importance": 0.85, "channel": "teams",  "language": "en", "tone": "professional", "greeting": "Hi Sarah"},
        {"id": "jake",   "name": "Jake Rivera",     "type": "client",    "importance": 0.8,  "channel": "email",  "language": "en", "tone": "professional", "greeting": "Hi Jake"},
        {"id": "ceo",    "name": "CEO Anika",        "type": "manager",   "importance": 1.0,  "channel": "email",  "language": "en", "tone": "formal",       "greeting": "Hi Anika"},
        {"id": "mike",   "name": "Mike Chen",       "type": "colleague", "importance": 0.65, "channel": "slack",  "language": "en", "tone": "casual",       "greeting": "Hey Mike"},
    ]
    for c in d_contacts:
        d_graph.add_or_update_contact(c["id"], c)
        for _ in range(random.randint(3, 10)):
            d_graph.record_interaction(c["id"], sentiment=random.uniform(0.5, 0.95), channel=c["channel"], language=c["language"])
    # Heavy interaction with both Gaurav and Phani (cross-team PM)
    for _ in range(6):
        d_graph.record_interaction("gaurav", sentiment=random.uniform(0.7, 0.95), channel="slack", language="en")
        d_graph.record_interaction("phani", sentiment=random.uniform(0.7, 0.95), channel="slack", language="en")
    # Sarah's tone declining for Demo too
    for _ in range(2):
        d_graph.record_interaction("sarah", sentiment=0.30, channel="teams", language="en")

    # ═══════════════════════════════════════════
    # MARKETPLACE SEED DATA
    # ═══════════════════════════════════════════

    listing_gaurav = MarketplaceListing(
        id="listing-gaurav-1",
        seller_user_id="user-gaurav",
        agent_id="agent-gaurav",
        title="Deep Work Shield — Auto-Decline Preset",
        description="Pre-configured auto-decline rules that protect deep work blocks, reject low-priority meetings exceeding daily cap, and respect VIP overrides. Tuned for engineering leads with 9-11am focus windows.",
        category="scheduling",
        tags=["deep-work", "auto-decline", "meetings", "focus"],
        capability_type="automation",
        price_per_use=0.75,
        status=ListingStatus.ACTIVE,
        total_purchases=23,
        avg_rating=4.7,
        total_reviews=8,
        total_earnings=15.53,
        is_featured=True,
    )
    db.add(listing_gaurav)

    listing_phani = MarketplaceListing(
        id="listing-phani-1",
        seller_user_id="user-phani",
        agent_id="agent-phani",
        title="Slack & Teams Tone Matcher",
        description="Voice-matched reply configuration trained on 500+ messages. Adapts greeting style, emoji usage, and formality per contact relationship. Works across Slack and Teams channels.",
        category="communication",
        tags=["slack", "teams", "tone", "voice-match"],
        capability_type="automation",
        price_per_use=1.25,
        status=ListingStatus.ACTIVE,
        total_purchases=15,
        avg_rating=4.5,
        total_reviews=6,
        total_earnings=16.88,
    )
    db.add(listing_phani)

    listing_demo = MarketplaceListing(
        id="listing-demo-1",
        seller_user_id="user-demo",
        agent_id="agent-demo",
        title="Ghost Mode Triage — PM Preset",
        description="Full ghost mode config for product managers: 80% confidence threshold, auto-reply across email/Slack/Teams, auto-escalate C-suite and investor contacts. Queues uncertain items for review.",
        category="ghost_mode",
        tags=["ghost-mode", "triage", "pm", "auto-reply"],
        capability_type="automation",
        price_per_use=1.50,
        status=ListingStatus.ACTIVE,
        total_purchases=31,
        avg_rating=4.8,
        total_reviews=12,
        total_earnings=41.85,
        is_featured=True,
    )
    db.add(listing_demo)

    listing_gaurav_2 = MarketplaceListing(
        id="listing-gaurav-2",
        seller_user_id="user-gaurav",
        agent_id="agent-gaurav",
        title="Relationship Health Monitor",
        description="Sentiment drift detection, neglected contact nudges, and tone shift alerts across all channels. Tuned for engineering team dynamics with weekly relationship health reports.",
        category="relationship_intel",
        tags=["sentiment", "tone-tracking", "contacts", "alerts"],
        capability_type="automation",
        price_per_use=1.00,
        status=ListingStatus.ACTIVE,
        total_purchases=9,
        avg_rating=4.3,
        total_reviews=4,
        total_earnings=8.10,
    )
    db.add(listing_gaurav_2)

    # Sample transactions with reviews
    txn1 = MarketplaceTransaction(
        id="txn-1",
        listing_id="listing-gaurav-1",
        buyer_user_id="user-phani",
        seller_user_id="user-gaurav",
        buyer_agent_id="agent-phani",
        amount=0.75,
        skyfire_transaction_id="mkt_20260225143000",
        platform_fee=0.08,
        seller_earnings=0.67,
        status=TransactionStatus.COMPLETED,
        task_description="Apply deep work protection to my 10am-12pm focus block",
        rating=5,
        review_text="Perfect auto-decline setup. Blocked 3 low-priority meetings on day one without touching VIP invites.",
        created_at=now - timedelta(days=3),
        completed_at=now - timedelta(days=3),
    )
    db.add(txn1)

    txn2 = MarketplaceTransaction(
        id="txn-2",
        listing_id="listing-demo-1",
        buyer_user_id="user-gaurav",
        seller_user_id="user-demo",
        buyer_agent_id="agent-gaurav",
        amount=1.50,
        skyfire_transaction_id="mkt_20260226100000",
        platform_fee=0.15,
        seller_earnings=1.35,
        status=TransactionStatus.COMPLETED,
        task_description="Set up ghost mode triage for my email and Slack channels",
        rating=5,
        review_text="Ghost mode handled 12 messages overnight. Only escalated the CEO email — exactly right.",
        created_at=now - timedelta(days=2),
        completed_at=now - timedelta(days=2),
    )
    db.add(txn2)

    txn3 = MarketplaceTransaction(
        id="txn-3",
        listing_id="listing-phani-1",
        buyer_user_id="user-demo",
        seller_user_id="user-phani",
        buyer_agent_id="agent-demo",
        amount=1.25,
        skyfire_transaction_id="mkt_20260226150000",
        platform_fee=0.13,
        seller_earnings=1.12,
        status=TransactionStatus.COMPLETED,
        task_description="Match my reply tone across Slack and Teams for the engineering team",
        rating=4,
        review_text="Tone matching is solid — replies sound like me. Emoji usage could be slightly less formal for Slack.",
        created_at=now - timedelta(days=1),
        completed_at=now - timedelta(days=1),
    )
    db.add(txn3)

    # ═══════════════════════════════════════════
    # DETERMINISTIC AGENT ACTIONS (for Decision Replays)
    # ═══════════════════════════════════════════

    action_demo_decline_vendor = AgentAction(
        id="action-demo-decline-vendor",
        user_id="user-demo", agent_id="agent-demo",
        timestamp=now - timedelta(hours=5),
        action_type="meeting_declined", channel="calendar",
        target_contact="Vendor Demo", language_used="en",
        action_taken="Auto-declined vendor demo during deep work block",
        confidence_score=0.89,
        reasoning="[Demo's agent] Vendor demo conflicts with 2-4pm deep work. Low priority contact.",
        factors=["deep_work_block", "contact_priority", "meeting_cap"],
        status="executed", estimated_time_saved_minutes=45.0,
        amount_spent=0, user_feedback="approved",
    )
    db.add(action_demo_decline_vendor)

    action_gaurav_decline_tom = AgentAction(
        id="action-gaurav-decline-tom",
        user_id="user-gaurav", agent_id="agent-gaurav",
        timestamp=now - timedelta(hours=8),
        action_type="meeting_declined", channel="calendar",
        target_contact="Tom Wilson", language_used="en",
        action_taken="Auto-declined Tom's sync during deep work block",
        confidence_score=0.91,
        reasoning="[Gaurav's agent] Tom's meeting conflicts with 9-11am deep work. Low importance contact.",
        factors=["deep_work_block", "contact_priority", "relationship_score"],
        status="executed", estimated_time_saved_minutes=30.0,
        amount_spent=0, user_feedback="approved",
    )
    db.add(action_gaurav_decline_tom)

    action_demo_reply_jake = AgentAction(
        id="action-demo-reply-jake",
        user_id="user-demo", agent_id="agent-demo",
        timestamp=now - timedelta(hours=12),
        action_type="email_reply", channel="email",
        target_contact="Jake Rivera", language_used="en",
        action_taken="Auto-replied to Jake's project update request",
        confidence_score=0.87,
        reasoning="[Demo's agent] Professional tone auto-reply to client update request.",
        factors=["relationship_score", "ghost_mode_threshold", "tone_match"],
        status="executed", estimated_time_saved_minutes=5.0,
        amount_spent=0, user_feedback="approved",
    )
    db.add(action_demo_reply_jake)

    # ═══════════════════════════════════════════
    # COMMITMENTS
    # ═══════════════════════════════════════════

    # Gaurav's commitments
    db.add(Commitment(
        id="commit-g1", user_id="user-gaurav", agent_id="agent-gaurav",
        raw_text="I'll send you the updated API schema by end of day",
        parsed_commitment="Send updated API schema to Phani",
        target_contact="Phani Kulkarni", channel="slack",
        detected_at=now - timedelta(hours=6),
        deadline=now + timedelta(hours=3),
        deadline_source="extracted",
        status=CommitmentStatus.ACTIVE,
        ghost_fulfillable=True, ghost_action_type="email_reply",
        sentiment_impact=0.0,
    ))
    db.add(Commitment(
        id="commit-g2", user_id="user-gaurav", agent_id="agent-gaurav",
        raw_text="Will review the PR before standup tomorrow",
        parsed_commitment="Review Phani's PR before standup",
        target_contact="Phani Kullarni", channel="teams",
        detected_at=now - timedelta(hours=18),
        deadline=now - timedelta(hours=6),
        deadline_source="extracted",
        status=CommitmentStatus.OVERDUE,
        sentiment_impact=-0.15,
    ))
    db.add(Commitment(
        id="commit-g3", user_id="user-gaurav", agent_id="agent-gaurav",
        raw_text="Rahul ko weekend tak migration script bhej dunga",
        parsed_commitment="Send migration script to Rahul by weekend",
        target_contact="Rahul Verma", channel="teams",
        detected_at=now - timedelta(days=4),
        deadline=now - timedelta(days=2),
        deadline_source="extracted",
        status=CommitmentStatus.BROKEN,
        sentiment_impact=-0.25,
    ))
    db.add(Commitment(
        id="commit-g4", user_id="user-gaurav", agent_id="agent-gaurav",
        raw_text="I'll update the deployment docs after the release",
        parsed_commitment="Update deployment documentation",
        target_contact="Mike Chen", channel="email",
        detected_at=now - timedelta(days=3),
        deadline=now - timedelta(days=1),
        deadline_source="inferred",
        status=CommitmentStatus.FULFILLED,
        fulfilled_at=now - timedelta(days=1),
        sentiment_impact=0.0,
    ))

    # Phani's commitments
    db.add(Commitment(
        id="commit-p1", user_id="user-phani", agent_id="agent-phani",
        raw_text="I'll have the frontend review done by tomorrow morning",
        parsed_commitment="Complete frontend code review",
        target_contact="Gaurav Gupta", channel="slack",
        detected_at=now - timedelta(hours=10),
        deadline=now + timedelta(hours=8),
        deadline_source="extracted",
        status=CommitmentStatus.ACTIVE,
    ))
    db.add(Commitment(
        id="commit-p2", user_id="user-phani", agent_id="agent-phani",
        raw_text="Will send the updated mockups to Sarah",
        parsed_commitment="Send updated mockups to Sarah",
        target_contact="Sarah Kim", channel="teams",
        detected_at=now - timedelta(days=2),
        deadline=now - timedelta(days=1),
        deadline_source="extracted",
        status=CommitmentStatus.FULFILLED,
        fulfilled_at=now - timedelta(days=1, hours=2),
        sentiment_impact=0.0,
    ))
    db.add(Commitment(
        id="commit-p3", user_id="user-phani", agent_id="agent-phani",
        raw_text="I'll fix the responsive layout bug today",
        parsed_commitment="Fix responsive layout bug",
        target_contact="Jake Rivera", channel="email",
        detected_at=now - timedelta(hours=30),
        deadline=now - timedelta(hours=6),
        deadline_source="extracted",
        status=CommitmentStatus.OVERDUE,
        sentiment_impact=-0.10,
    ))

    # Demo's commitments
    db.add(Commitment(
        id="commit-d1", user_id="user-demo", agent_id="agent-demo",
        raw_text="I'll share the product roadmap with the team by Friday",
        parsed_commitment="Share product roadmap with team",
        target_contact="Sarah Kim", channel="teams",
        detected_at=now - timedelta(hours=12),
        deadline=now + timedelta(hours=24),
        deadline_source="extracted",
        status=CommitmentStatus.ACTIVE,
    ))
    db.add(Commitment(
        id="commit-d2", user_id="user-demo", agent_id="agent-demo",
        raw_text="Will get back to Jake on the timeline question",
        parsed_commitment="Reply to Jake's timeline question",
        target_contact="Jake Rivera", channel="email",
        detected_at=now - timedelta(hours=36),
        deadline=now - timedelta(hours=12),
        deadline_source="inferred",
        status=CommitmentStatus.OVERDUE,
        sentiment_impact=-0.12,
    ))
    db.add(Commitment(
        id="commit-d3", user_id="user-demo", agent_id="agent-demo",
        raw_text="I'll review Gaurav's architecture doc tonight",
        parsed_commitment="Review architecture doc",
        target_contact="Gaurav Gupta", channel="slack",
        detected_at=now - timedelta(days=2),
        deadline=now - timedelta(days=1, hours=12),
        deadline_source="extracted",
        status=CommitmentStatus.FULFILLED,
        fulfilled_at=now - timedelta(days=1, hours=14),
        sentiment_impact=0.0,
    ))
    db.add(Commitment(
        id="commit-d4", user_id="user-demo", agent_id="agent-demo",
        raw_text="I'll send the meeting notes to the team after the sync",
        parsed_commitment="Send meeting notes to team",
        target_contact="Phani Kulkarni", channel="slack",
        detected_at=now - timedelta(hours=4),
        deadline=now + timedelta(hours=6),
        deadline_source="extracted",
        status=CommitmentStatus.ACTIVE,
        ghost_fulfillable=True, ghost_action_type="slack_reply",
    ))

    # ═══════════════════════════════════════════
    # DELEGATION REQUESTS
    # ═══════════════════════════════════════════

    db.add(DelegationRequest(
        id="deleg-1",
        from_user_id="user-demo", to_user_id="user-gaurav",
        task_description="Review backend API rate limiting implementation",
        task_source="email from Jake about performance concerns",
        source_channel="email", original_sender="Jake Rivera",
        match_score=0.92,
        match_reasons=["Backend expertise", "API architecture owner", "Available bandwidth"],
        expertise_match=0.95, bandwidth_score=0.78, relationship_strength=0.90,
        status=DelegationStatus.ACCEPTED,
        deadline=now + timedelta(days=2),
        created_at=now - timedelta(hours=18),
    ))
    db.add(DelegationRequest(
        id="deleg-2",
        from_user_id="user-gaurav", to_user_id="user-phani",
        task_description="Update frontend dashboard with new analytics widgets",
        task_source="sprint planning decision",
        source_channel="teams", original_sender="Sarah Kim",
        match_score=0.88,
        match_reasons=["Frontend lead", "Dashboard component owner", "Design system expertise"],
        expertise_match=0.92, bandwidth_score=0.72, relationship_strength=0.90,
        status=DelegationStatus.IN_PROGRESS,
        deadline=now + timedelta(days=3),
        created_at=now - timedelta(hours=24),
    ))
    db.add(DelegationRequest(
        id="deleg-3",
        from_user_id="user-phani", to_user_id="user-gaurav",
        task_description="Fix database migration script for user preferences table",
        task_source="CI/CD pipeline failure alert",
        source_channel="slack", original_sender="DevOps Bot",
        match_score=0.85,
        match_reasons=["Database migration expertise", "Backend owner", "Previous migration author"],
        expertise_match=0.90, bandwidth_score=0.68, relationship_strength=0.90,
        status=DelegationStatus.COMPLETED,
        deadline=now - timedelta(hours=6),
        completed_at=now - timedelta(hours=8),
        created_at=now - timedelta(days=2),
    ))

    # ═══════════════════════════════════════════
    # BURNOUT SNAPSHOTS
    # ═══════════════════════════════════════════

    # Demo user — 4 weekly snapshots showing trend
    db.add(BurnoutSnapshot(
        id="burn-demo-1", user_id="user-demo",
        snapshot_date=now,
        burnout_risk_score=42.0, workload_score=58.0, relationship_health_score=71.0,
        avg_daily_meetings=4.2, avg_response_time_hours=1.8,
        deep_work_hours_weekly=8.5, messages_sent_daily=32.0,
        after_hours_activity_pct=18.0,
        predicted_cold_contacts=["Jake Rivera", "Mike Chen"],
        productivity_multipliers={"deep_work": 1.3, "morning": 1.1, "after_lunch": 0.85},
        workload_trajectory="rising",
        recommended_interventions=[
            "Reduce meetings to 3/day max this week",
            "Schedule 15-min break between back-to-back meetings",
            "Reach out to Jake Rivera — last contact 9 days ago",
        ],
    ))
    db.add(BurnoutSnapshot(
        id="burn-demo-2", user_id="user-demo",
        snapshot_date=now - timedelta(days=7),
        burnout_risk_score=38.0, workload_score=52.0, relationship_health_score=74.0,
        avg_daily_meetings=3.8, avg_response_time_hours=1.5,
        deep_work_hours_weekly=9.2, messages_sent_daily=28.0,
        after_hours_activity_pct=15.0,
        predicted_cold_contacts=["Mike Chen"],
        productivity_multipliers={"deep_work": 1.35, "morning": 1.15, "after_lunch": 0.80},
        workload_trajectory="stable",
        recommended_interventions=[
            "Maintain current meeting cadence",
            "Consider reaching out to Mike Chen",
        ],
    ))
    db.add(BurnoutSnapshot(
        id="burn-demo-3", user_id="user-demo",
        snapshot_date=now - timedelta(days=14),
        burnout_risk_score=35.0, workload_score=48.0, relationship_health_score=76.0,
        avg_daily_meetings=3.5, avg_response_time_hours=1.3,
        deep_work_hours_weekly=10.0, messages_sent_daily=25.0,
        after_hours_activity_pct=12.0,
        predicted_cold_contacts=[],
        productivity_multipliers={"deep_work": 1.4, "morning": 1.2, "after_lunch": 0.82},
        workload_trajectory="stable",
        recommended_interventions=["All metrics healthy — no interventions needed"],
    ))
    db.add(BurnoutSnapshot(
        id="burn-demo-4", user_id="user-demo",
        snapshot_date=now - timedelta(days=21),
        burnout_risk_score=32.0, workload_score=45.0, relationship_health_score=78.0,
        avg_daily_meetings=3.2, avg_response_time_hours=1.2,
        deep_work_hours_weekly=10.5, messages_sent_daily=23.0,
        after_hours_activity_pct=10.0,
        predicted_cold_contacts=[],
        productivity_multipliers={"deep_work": 1.4, "morning": 1.2, "after_lunch": 0.85},
        workload_trajectory="stable",
        recommended_interventions=["All metrics healthy — no interventions needed"],
    ))

    # Gaurav — single snapshot
    db.add(BurnoutSnapshot(
        id="burn-gaurav-1", user_id="user-gaurav",
        snapshot_date=now,
        burnout_risk_score=55.0, workload_score=65.0, relationship_health_score=62.0,
        avg_daily_meetings=5.1, avg_response_time_hours=2.5,
        deep_work_hours_weekly=6.0, messages_sent_daily=40.0,
        after_hours_activity_pct=25.0,
        predicted_cold_contacts=["Tom Wilson", "Investor Mark"],
        productivity_multipliers={"deep_work": 1.5, "morning": 1.2, "after_lunch": 0.75},
        workload_trajectory="rising",
        recommended_interventions=[
            "Burnout risk elevated — reduce after-hours work",
            "Delegate 2 low-priority tasks via mesh",
            "Protect 9-11am deep work block strictly",
            "Follow up with Investor Mark — 12 days since last contact",
        ],
    ))

    # Phani — single snapshot
    db.add(BurnoutSnapshot(
        id="burn-phani-1", user_id="user-phani",
        snapshot_date=now,
        burnout_risk_score=28.0, workload_score=40.0, relationship_health_score=82.0,
        avg_daily_meetings=2.8, avg_response_time_hours=0.9,
        deep_work_hours_weekly=12.0, messages_sent_daily=20.0,
        after_hours_activity_pct=8.0,
        predicted_cold_contacts=[],
        productivity_multipliers={"deep_work": 1.45, "morning": 1.25, "after_lunch": 0.88},
        workload_trajectory="stable",
        recommended_interventions=["All metrics healthy — maintain current pace"],
    ))

    # ═══════════════════════════════════════════
    # DECISION REPLAYS
    # ═══════════════════════════════════════════

    db.add(DecisionReplay(
        id="replay-1", user_id="user-demo",
        source_action_id="action-demo-decline-vendor",
        original_decision="Auto-declined Vendor Demo during deep work block",
        original_outcome="Protected 45-min deep work session. Vendor rescheduled for next week.",
        counterfactual_decision="Accept the vendor demo meeting",
        counterfactual_cascade=[
            {"step": 1, "event": "Accepted 45-min vendor demo at 2:30 PM", "impact": "Lost deep work block"},
            {"step": 2, "event": "Context switch cost: 23 min to regain focus", "impact": "Reduced afternoon productivity by 40%"},
            {"step": 3, "event": "Delayed roadmap review pushed to after-hours", "impact": "+1.5 hrs after-hours work"},
            {"step": 4, "event": "Increased burnout risk score by 4 points", "impact": "Cumulative fatigue"},
        ],
        time_impact_minutes=150.0,
        relationship_impact={"Vendor Demo": -0.02, "Sarah Kim": 0.0},
        productivity_impact=0.40,
        verdict="Excellent call — protected deep work, vendor rescheduled with zero relationship cost",
        confidence=0.91,
        created_at=now - timedelta(hours=4),
    ))
    db.add(DecisionReplay(
        id="replay-2", user_id="user-gaurav",
        source_action_id="action-gaurav-decline-tom",
        original_decision="Auto-declined Tom's meeting during 9-11am deep work",
        original_outcome="Completed API schema redesign during protected focus time.",
        counterfactual_decision="Accept Tom's meeting request",
        counterfactual_cascade=[
            {"step": 1, "event": "Accepted Tom's 30-min sync at 9:30 AM", "impact": "Broke deep work block"},
            {"step": 2, "event": "API schema redesign delayed by 1 day", "impact": "Blocked Phani's frontend integration"},
            {"step": 3, "event": "Sprint velocity reduced — missed sprint commitment", "impact": "Team morale dip"},
        ],
        time_impact_minutes=90.0,
        relationship_impact={"Tom Wilson": -0.05, "Phani Kulkarni": 0.10},
        productivity_impact=0.35,
        verdict="Good call — Tom's sync was informational only, could have been an email",
        confidence=0.87,
        created_at=now - timedelta(hours=6),
    ))
    db.add(DecisionReplay(
        id="replay-3", user_id="user-demo",
        source_action_id="action-demo-reply-jake",
        original_decision="Auto-replied to Jake's project update request",
        original_outcome="Jake received timely professional update. Client satisfaction maintained.",
        counterfactual_decision="Delay reply until manual review",
        counterfactual_cascade=[
            {"step": 1, "event": "Jake waited 6+ hours for reply", "impact": "Client frustration"},
            {"step": 2, "event": "Jake escalated to Sarah", "impact": "Manager intervention required"},
            {"step": 3, "event": "Sarah's already declining sentiment worsened", "impact": "Relationship strain"},
        ],
        time_impact_minutes=45.0,
        relationship_impact={"Jake Rivera": 0.08, "Sarah Kim": 0.03},
        productivity_impact=0.15,
        verdict="Auto-reply prevented client escalation — relationship preserved",
        confidence=0.84,
        created_at=now - timedelta(hours=10),
    ))

    # ═══════════════════════════════════════════
    # FLOW SESSIONS
    # ═══════════════════════════════════════════

    db.add(FlowSession(
        id="flow-demo-1", user_id="user-demo", agent_id="agent-demo",
        started_at=now - timedelta(hours=2, minutes=0),
        ended_at=now - timedelta(hours=1, minutes=13),
        duration_minutes=47.0,
        trigger_signals=["sustained_typing", "no_app_switches_10min", "deep_work_block_active"],
        flow_score=0.87,
        messages_held=4, messages_escalated=0, auto_responses_sent=3, meetings_auto_declined=1,
        held_messages=[
            {"from": "Mike Chen", "channel": "slack", "summary": "Quick question about docs", "urgency": 0.3},
            {"from": "Phani Kulkarni", "channel": "slack", "summary": "PR approved, merging now", "urgency": 0.4},
            {"from": "DevOps Bot", "channel": "slack", "summary": "Deploy succeeded", "urgency": 0.2},
            {"from": "Sarah Kim", "channel": "teams", "summary": "Can we reschedule 1:1?", "urgency": 0.5},
        ],
        debrief_delivered=True, debrief_at=now - timedelta(hours=1, minutes=10),
        estimated_focus_saved_minutes=35.0,
    ))
    db.add(FlowSession(
        id="flow-demo-2", user_id="user-demo", agent_id="agent-demo",
        started_at=now - timedelta(days=1, hours=3),
        ended_at=now - timedelta(days=1, hours=2, minutes=28),
        duration_minutes=32.0,
        trigger_signals=["sustained_typing", "deep_work_block_active"],
        flow_score=0.74,
        messages_held=2, messages_escalated=0, auto_responses_sent=2, meetings_auto_declined=0,
        held_messages=[
            {"from": "Gaurav Gupta", "channel": "slack", "summary": "API deploy ETA?", "urgency": 0.5},
            {"from": "Mike Chen", "channel": "email", "summary": "Weekly sync agenda", "urgency": 0.2},
        ],
        debrief_delivered=True, debrief_at=now - timedelta(days=1, hours=2, minutes=25),
        estimated_focus_saved_minutes=22.0,
    ))
    db.add(FlowSession(
        id="flow-gaurav-1", user_id="user-gaurav", agent_id="agent-gaurav",
        started_at=now - timedelta(hours=3, minutes=55),
        ended_at=now - timedelta(hours=3),
        duration_minutes=55.0,
        trigger_signals=["sustained_typing", "no_app_switches_10min", "deep_work_block_active", "ide_active"],
        flow_score=0.92,
        messages_held=5, messages_escalated=1, auto_responses_sent=4, meetings_auto_declined=1,
        held_messages=[
            {"from": "Phani Kulkarni", "channel": "teams", "summary": "Component API question", "urgency": 0.5},
            {"from": "Tom Wilson", "channel": "email", "summary": "Lunch plans?", "urgency": 0.1},
            {"from": "Rahul Verma", "channel": "teams", "summary": "Migration script question", "urgency": 0.4},
            {"from": "DevOps Bot", "channel": "slack", "summary": "Build passed", "urgency": 0.2},
            {"from": "Sarah Kim", "channel": "slack", "summary": "Urgent: client escalation", "urgency": 0.95},
        ],
        debrief_delivered=True, debrief_at=now - timedelta(hours=2, minutes=55),
        estimated_focus_saved_minutes=42.0,
    ))
    db.add(FlowSession(
        id="flow-phani-1", user_id="user-phani", agent_id="agent-phani",
        started_at=now - timedelta(days=1, hours=4),
        ended_at=now - timedelta(days=1, hours=3, minutes=22),
        duration_minutes=38.0,
        trigger_signals=["sustained_typing", "deep_work_block_active", "ide_active"],
        flow_score=0.79,
        messages_held=3, messages_escalated=0, auto_responses_sent=2, meetings_auto_declined=0,
        held_messages=[
            {"from": "Gaurav Gupta", "channel": "teams", "summary": "Schema update ready for review", "urgency": 0.5},
            {"from": "Mike Chen", "channel": "slack", "summary": "Design system question", "urgency": 0.3},
            {"from": "Jake Rivera", "channel": "email", "summary": "Demo feedback", "urgency": 0.4},
        ],
        debrief_delivered=True, debrief_at=now - timedelta(days=1, hours=3, minutes=18),
        estimated_focus_saved_minutes=28.0,
    ))

    # ═══════════════════════════════════════════
    # NEW MARKETPLACE LISTINGS (one per feature + bundle)
    # ═══════════════════════════════════════════

    db.add(MarketplaceListing(
        id="listing-commitment-1",
        seller_user_id="user-demo", agent_id="agent-demo",
        title="Commitment Tracker — Promise Detection",
        description="Automatically detects promises in outgoing messages, tracks deadlines, and nudges before commitments go overdue. Supports Hindi and English. Ghost mode can auto-fulfill simple commitments.",
        category="commitment_tracking",
        tags=["commitments", "promises", "deadlines", "accountability"],
        capability_type="automation",
        price_per_use=1.00,
        status=ListingStatus.ACTIVE,
        total_purchases=18, avg_rating=4.6, total_reviews=7, total_earnings=16.20,
        is_featured=True,
    ))
    db.add(MarketplaceListing(
        id="listing-delegation-1",
        seller_user_id="user-gaurav", agent_id="agent-gaurav",
        title="Smart Delegation — Mesh Task Router",
        description="Intelligently routes tasks to the best-matched teammate via agent mesh. Considers expertise, bandwidth, and relationship strength. Tracks delegation through completion.",
        category="delegation",
        tags=["delegation", "mesh", "task-routing", "teamwork"],
        capability_type="automation",
        price_per_use=1.50,
        status=ListingStatus.ACTIVE,
        total_purchases=12, avg_rating=4.4, total_reviews=5, total_earnings=16.20,
    ))
    db.add(MarketplaceListing(
        id="listing-burnout-1",
        seller_user_id="user-phani", agent_id="agent-phani",
        title="Burnout Shield — Wellness Monitor",
        description="Weekly burnout risk analysis with workload scoring, relationship health tracking, and proactive intervention recommendations. Predicts contacts going cold and suggests outreach.",
        category="wellness",
        tags=["burnout", "wellness", "workload", "mental-health"],
        capability_type="automation",
        price_per_use=2.00,
        status=ListingStatus.ACTIVE,
        total_purchases=25, avg_rating=4.9, total_reviews=10, total_earnings=45.00,
        is_featured=True,
    ))
    db.add(MarketplaceListing(
        id="listing-replay-1",
        seller_user_id="user-demo", agent_id="agent-demo",
        title="Decision Replay — Counterfactual Analysis",
        description="Replays past agent decisions with 'what-if' analysis. Shows cascade effects of alternative choices on time, relationships, and productivity. Learn from every decision.",
        category="analytics",
        tags=["decision-replay", "counterfactual", "analytics", "learning"],
        capability_type="automation",
        price_per_use=1.25,
        status=ListingStatus.ACTIVE,
        total_purchases=14, avg_rating=4.5, total_reviews=6, total_earnings=15.75,
    ))
    db.add(MarketplaceListing(
        id="listing-flow-1",
        seller_user_id="user-gaurav", agent_id="agent-gaurav",
        title="Flow State Guardian — Focus Protector",
        description="Detects flow state via typing patterns and app usage, holds non-urgent messages, auto-responds, and delivers a debrief when flow ends. Protects your most productive hours.",
        category="focus",
        tags=["flow-state", "focus", "deep-work", "productivity"],
        capability_type="automation",
        price_per_use=1.00,
        status=ListingStatus.ACTIVE,
        total_purchases=20, avg_rating=4.7, total_reviews=9, total_earnings=18.00,
        is_featured=True,
    ))
    db.add(MarketplaceListing(
        id="listing-bundle-1",
        seller_user_id="user-demo", agent_id="agent-demo",
        title="Kairo Pro Bundle — All 5 Features",
        description="Complete bundle: Commitment Tracking, Smart Delegation, Burnout Shield, Decision Replay, and Flow State Guardian. Save 25% vs buying individually. Everything you need for autonomous agent management.",
        category="bundle",
        tags=["bundle", "pro", "all-features", "discount"],
        capability_type="automation",
        price_per_use=4.00,
        status=ListingStatus.ACTIVE,
        total_purchases=8, avg_rating=4.8, total_reviews=4, total_earnings=28.80,
        is_featured=True,
    ))

    db.commit()
    db.close()

    print()
    print("═══════════════════════════════════════════")
    print("  Kairo Demo Data Seeded — 3 Users")
    print("═══════════════════════════════════════════")
    print()
    print("  DEMO ACCOUNT (for reviewers):")
    print("    Email:    demo@kairo.ai")
    print("    Password: demo1234")
    print("    Role:     Product Manager")
    print("    Agent:    running, ghost mode ON")
    print("    Deep work: 2:00–4:00 PM ET")
    print()
    print("  USER 1: Gaurav Gupta (Backend Lead)")
    print("    Email:    gaurav@kairo.ai")
    print("    Password: demo1234")
    print("    Agent:    running, ghost mode ON")
    print("    Language: auto (EN + HI)")
    print("    Deep work: 9:00–11:00 AM IST")
    print()
    print("  USER 2: Phani Kulkarni (Frontend Lead)")
    print("    Email:    phani@kairo.ai")
    print("    Password: demo1234")
    print("    Agent:    running, ghost mode ON")
    print("    Language: English")
    print("    Deep work: 10:00 AM–12:00 PM IST")
    print()
    print("  All 3 are colleagues on the same project.")
    print("  Their agents coordinate via the Agent Mesh.")
    print("═══════════════════════════════════════════")
    print()


if __name__ == "__main__":
    seed()
