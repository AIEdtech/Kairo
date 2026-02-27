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
