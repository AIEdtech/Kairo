"""
Agent Runtime Service — each user runs their own isolated Kairo agent.

Architecture:
─────────────────────────────────────────────────────────────
  RuntimeManager (singleton, one per server)
    │
    ├── AgentRuntime[user_A]     ← isolated per-user instance
    │     ├── ComposioClient     (user_A's OAuth tokens)
    │     ├── RelationshipGraph  (user_A's NetworkX graph)
    │     ├── CrewAI Crew        (user_A's agents + tools)
    │     ├── SkyfireClient      (user_A's spend limits)
    │     └── UserScheduler      (user_A's briefing time/tz)
    │
    ├── AgentRuntime[user_B]     ← completely separate
    │     ├── ComposioClient     (user_B's OAuth tokens)
    │     ├── RelationshipGraph  (user_B's NetworkX graph)
    │     ...
    └── ...
─────────────────────────────────────────────────────────────

Lifecycle:
  1. User clicks "Launch Agent" → RuntimeManager.launch_agent(user_id, agent_id)
  2. Creates AgentRuntime for that user
  3. Loads their config, Composio tools, NetworkX graph
  4. Instantiates a CrewAI crew with user-specific tools attached
  5. Registers per-user scheduled jobs (briefing at THEIR time, in THEIR timezone)
  6. Marks agent as "running"
  7. Webhooks route events → runtime_manager.route_event(user_id, ...) → user's runtime

On server restart:
  startup → RuntimeManager.recover_running_agents()
  Queries DB for all agents with status="running", re-launches each
"""

import logging
import json
import asyncio
from typing import Optional
from datetime import datetime, timezone, timedelta

from config import get_settings
from models.database import (
    AgentConfig, AgentAction, User, ContactRelationship,
    get_engine, create_session_factory,
)

settings = get_settings()
logger = logging.getLogger("kairo.runtime")
engine = get_engine(settings.database_url)
SessionLocal = create_session_factory(engine)


class AgentRuntime:
    """
    One instance per user's running agent.
    Completely isolated: own tools, graph, crew, scheduler jobs.
    """

    def __init__(self, user_id: str, agent_id: str):
        self.user_id = user_id
        self.agent_id = agent_id
        self.is_running = False

        # Per-user components (created on launch)
        self._config: Optional[AgentConfig] = None
        self._composio = None       # ComposioClient (user's OAuth)
        self._graph = None          # RelationshipGraph (user's contacts)
        self._skyfire = None        # SkyfireClient (user's spend limits)
        self._tools: list = []      # CrewAI tools (from user's Composio)
        self._crew = None           # CrewAI crew instance
        self._meeting_agent = None  # CrewAI meeting negotiation agent
        self._user_email: str = ""      # User's email (to skip self-replies)
        self._processed_email_ids: set = set()  # Track processed email IDs
        self._processed_email_keys: set = set()  # Track by subject+sender as fallback dedup
        import asyncio
        self._poll_lock = asyncio.Lock()  # Prevent overlapping poll cycles
        self._load_processed_ids()  # Restore from disk if available

    def _load_processed_ids(self):
        """Load processed email IDs from disk to survive restarts."""
        import json, os
        path = os.path.join(os.path.dirname(__file__), '..', f'.processed_emails_{self.user_id}.json')
        try:
            if os.path.exists(path):
                with open(path, 'r') as f:
                    self._processed_email_ids = set(json.load(f))
                logger.info(f"[{self.user_id}] Restored {len(self._processed_email_ids)} processed email IDs from disk")
        except Exception as e:
            logger.warning(f"[{self.user_id}] Could not load processed IDs: {e}")

    def _save_processed_ids(self):
        """Persist processed email IDs to disk."""
        import json, os
        path = os.path.join(os.path.dirname(__file__), '..', f'.processed_emails_{self.user_id}.json')
        try:
            ids_list = list(self._processed_email_ids)[-500:]  # Keep last 500
            with open(path, 'w') as f:
                json.dump(ids_list, f)
        except Exception:
            pass

    async def _seed_processed_emails(self):
        """
        On launch, fetch current inbox emails and mark them as already processed.
        This prevents old emails from being treated as new on first run or after
        the processed IDs file is deleted.
        """
        if not self._composio:
            return
        try:
            existing = await self._composio.fetch_recent_emails(max_results=10, max_age_hours=24)
            if existing:
                rm = get_runtime_manager()
                for email in existing:
                    eid = email.get("id", "")
                    if eid:
                        self._processed_email_ids.add(eid)
                        rm._global_processed_emails.add(eid)  # Cross-agent dedup
                self._save_processed_ids()
                logger.info(f"[{self.user_id}] Seeded {len(existing)} existing email IDs (won't re-process)")
        except Exception as e:
            logger.warning(f"[{self.user_id}] Email seed failed: {e}")

    # ──────────────────────────────────────────
    # LAUNCH — full startup sequence
    # ──────────────────────────────────────────

    async def launch(self) -> dict:
        """
        Launch this user's agent. Called when user clicks "Launch Agent".
        Each step creates user-isolated resources.
        """
        logger.info(f"🚀 Launching agent for user={self.user_id} agent={self.agent_id}")

        # 1. Load config from DB
        self._load_config()

        # 2. Initialize this user's Composio (their OAuth tokens)
        self._init_composio()

        # 3. Load this user's relationship graph
        self._init_graph()

        # 4. Get this user's CrewAI tools from their Composio
        self._load_tools()

        # 5. Create this user's CrewAI crew with their tools
        self._init_crew()

        # 6. Seed processed email IDs — mark all current inbox emails as "seen"
        #    so only truly NEW emails arriving after launch get processed.
        await self._seed_processed_emails()

        # 7. Register per-user scheduled jobs
        self._register_user_scheduler_jobs()

        # 7. Mark as running
        self._set_status("running")
        self.is_running = True

        # Log launch
        self._log_action(
            action_type="agent_launched",
            channel="dashboard",
            action_taken=(
                f"Agent launched — "
                f"{len(self._tools)} tools, "
                f"{len(self._graph.G.nodes) - 1} contacts, "  # -1 for "self" node
                f"ghost_mode={'ON' if self._config.ghost_mode_enabled else 'OFF'}"
            ),
            confidence=1.0,
        )

        result = {
            "status": "running",
            "user_id": self.user_id,
            "integrations": self._get_integration_status(),
            "contacts_loaded": len(self._graph.G.nodes) - 1,
            "tools_available": len(self._tools),
            "ghost_mode": self._config.ghost_mode_enabled,
            "briefing_time": self._config.briefing_time,
            "voice_language": self._config.voice_language,
        }
        logger.info(f"✅ Agent RUNNING for user={self.user_id}: {result}")
        return result

    # ──────────────────────────────────────────
    # INITIALIZATION STEPS (per-user isolated)
    # ──────────────────────────────────────────

    def _load_config(self):
        """Load this user's agent config from DB."""
        db = SessionLocal()
        try:
            self._config = db.query(AgentConfig).filter(
                AgentConfig.id == self.agent_id,
                AgentConfig.user_id == self.user_id,
            ).first()
            if not self._config:
                raise ValueError(f"Agent {self.agent_id} not found for user {self.user_id}")
            
            # Force load all lazy-loaded attributes while session is open
            # This prevents DetachedInstanceError later
            _ = self._config.relationship_graph_data
            _ = self._config.ghost_mode_vip_contacts
            _ = self._config.ghost_mode_blocked_contacts
            _ = self._config.ghost_mode_allowed_actions

            # Load the user's own email address (to skip self-generated replies)
            from models.database import User
            user = db.query(User).filter(User.id == self.user_id).first()
            if user:
                self._user_email = user.email
                logger.info(f"[{self.user_id}] User email: {self._user_email}")
            
        finally:
            db.close()

    def _init_composio(self):
        """Initialize Composio with this user's entity (their OAuth tokens)."""
        from services.composio_tools import ComposioClient
        self._composio = ComposioClient()
        # Each user gets a unique entity_id → their own OAuth tokens
        entity_id = f"kairo_{self.user_id}"
        self._composio.initialize(entity_id)

        # Sync connection status to DB
        status = self._composio.get_connection_status()
        db = SessionLocal()
        try:
            agent = db.query(AgentConfig).filter(AgentConfig.id == self.agent_id).first()
            if agent:
                agent.gmail_connected = status.get("gmail", False)
                agent.slack_connected = status.get("slack", False)
                agent.teams_connected = status.get("teams", False)
                agent.calendar_connected = status.get("calendar", False)
                agent.github_connected = status.get("github", False)
                agent.composio_connected = any(status.values())
                db.commit()
                # Don't reassign self._config here (would be detached object)
                # Just keep the original config loaded in _load_config()
        finally:
            db.close()

        logger.info(f"[{self.user_id}] Composio entity={entity_id} status={status}")

    def _init_graph(self):
        """Load or create this user's NetworkX relationship graph."""
        from services.relationship_graph import get_relationship_graph
        self._graph = get_relationship_graph(self.user_id)

        # Try to restore from DB if graph is empty
        if len(self._graph.G.nodes) <= 1 and self._config.relationship_graph_data:
            try:
                self._graph.from_json(json.dumps(self._config.relationship_graph_data))
                logger.info(f"[{self.user_id}] Restored graph: {len(self._graph.G.nodes)} nodes")
            except Exception as e:
                logger.warning(f"[{self.user_id}] Graph restore failed: {e}")

    def _load_tools(self):
        """Get CrewAI-compatible tools from this user's connected integrations."""
        connected_apps = []
        if self._config.gmail_connected:
            connected_apps.append("gmail")
        if self._config.calendar_connected:
            connected_apps.append("calendar")
        if self._config.slack_connected:
            connected_apps.append("slack")
        if self._config.teams_connected:
            connected_apps.append("teams")
        if self._config.github_connected:
            connected_apps.append("github")

        if connected_apps and self._composio:
            self._tools = self._composio.get_crewai_tools(apps=connected_apps)
        else:
            self._tools = []

        logger.info(f"[{self.user_id}] Loaded {len(self._tools)} tools for: {connected_apps}")

    def _init_crew(self):
        """Create this user's CrewAI crew with their tools attached."""
        try:
            from crewai import Agent, Crew, Process

            model = f"anthropic/{settings.anthropic_model}"
            logger.info(f"[{self.user_id}] Initializing CrewAI agents with model={model}")

            # Filter tools to only valid BaseTool instances (ActionModel objects from
            # composio get_action_schemas() are not compatible with CrewAI agents)
            valid_tools = []
            try:
                from crewai.tools import BaseTool as CrewAIBaseTool
                valid_tools = [t for t in self._tools if isinstance(t, CrewAIBaseTool)]
            except ImportError:
                pass
            if len(valid_tools) != len(self._tools):
                logger.info(f"[{self.user_id}] Filtered tools: {len(valid_tools)} valid of {len(self._tools)} total")

            # Each user's crew gets their own agent instances with their own tools
            self._observer = Agent(
                role="Relationship Intelligence Analyst",
                goal=f"Monitor communications for user {self.user_id}. Track tone shifts, language patterns.",
                backstory="Expert in human communication pattern detection.",
                llm=model,
                tools=valid_tools,
                verbose=False,
                allow_delegation=False,
            )

            self._reasoner = Agent(
                role="Decision Engine",
                goal=f"Evaluate signals and decide actions for user {self.user_id}. Consider relationship importance, energy state, language preference.",
                backstory="Strategic core of Kairo. Weighs factors to make nuanced decisions.",
                llm=model,
                tools=valid_tools,
                verbose=False,
                allow_delegation=True,
            )

            self._actor = Agent(
                role="Voice & Style Matcher",
                goal=f"Draft messages matching user {self.user_id}'s communication style per contact. Adapt tone, formality, language (EN/HI).",
                backstory="Communication chameleon. Writes as the user — indistinguishable from their own style.",
                llm=model,
                tools=valid_tools,
                verbose=False,
                allow_delegation=False,
            )

            # Meeting agent needs NO tools — it just analyzes text and returns JSON.
            # Actual email/calendar actions are executed by Python/Composio after parsing its output.
            self._meeting_agent = Agent(
                role="Meeting Negotiation Specialist",
                goal=(
                    f"Analyze incoming emails for user {self.user_id}. Detect genuine meeting requests, "
                    "extract proposed dates/times, check calendar availability, and decide whether to "
                    "accept, propose alternatives, or decline. Generate warm, professional reply emails."
                ),
                backstory=(
                    "You are an expert executive assistant who handles scheduling with finesse. "
                    "You can parse natural language meeting requests like 'Can we grab coffee at 3pm tomorrow?', "
                    "understand implicit scheduling intent, check calendar conflicts, and craft replies "
                    "that sound natural and not robotic. You never confuse promotional emails or newsletters "
                    "with real meeting requests."
                ),
                llm=model,
                tools=[],
                verbose=False,
                allow_delegation=False,
            )

            logger.info(f"[{self.user_id}] CrewAI agents initialized (including meeting agent) with {len(valid_tools)} tools")

        except ImportError as ie:
            logger.warning(f"[{self.user_id}] CrewAI not installed — agents will use fallback logic: {ie}")
        except Exception as e:
            logger.error(f"[{self.user_id}] CrewAI init failed: {e}", exc_info=True)

    def _register_user_scheduler_jobs(self):
        """Register per-user scheduled jobs using THEIR briefing time and timezone."""
        try:
            from apscheduler.triggers.cron import CronTrigger
            from services.scheduler import scheduler

            briefing_time = self._config.briefing_time or "07:00"
            hour, minute = map(int, briefing_time.split(":"))

            # Per-user morning briefing at their configured time
            job_id = f"briefing_{self.user_id}"
            if scheduler.get_job(job_id):
                scheduler.remove_job(job_id)

            if self._config.briefing_enabled:
                scheduler.add_job(
                    self._run_morning_briefing,
                    CronTrigger(hour=hour, minute=minute),
                    id=job_id,
                    replace_existing=True,
                )
                logger.info(f"[{self.user_id}] Briefing scheduled at {briefing_time}")

            # Per-user ghost mode triage every 30 min (only if ghost mode ON)
            triage_id = f"triage_{self.user_id}"
            if scheduler.get_job(triage_id):
                scheduler.remove_job(triage_id)

            if self._config.ghost_mode_enabled:
                scheduler.add_job(
                    self._run_ghost_triage,
                    CronTrigger(minute="*/30"),
                    id=triage_id,
                    replace_existing=True,
                )

            # Per-user email polling every 30 seconds (since webhooks can't reach localhost)
            poll_id = f"email_poll_{self.user_id}"
            if scheduler.get_job(poll_id):
                scheduler.remove_job(poll_id)
            
            from apscheduler.triggers.interval import IntervalTrigger
            scheduler.add_job(
                self._poll_emails,
                IntervalTrigger(seconds=30),
                id=poll_id,
                replace_existing=True,
            )
            logger.info(f"[{self.user_id}] Email polling started (every 30s)")

        except Exception as e:
            logger.warning(f"[{self.user_id}] Scheduler registration failed: {e}")

    def _deregister_user_scheduler_jobs(self):
        """Remove this user's scheduled jobs on stop/pause."""
        try:
            from services.scheduler import scheduler
            for job_id in [f"briefing_{self.user_id}", f"triage_{self.user_id}", f"email_poll_{self.user_id}"]:
                if scheduler.get_job(job_id):
                    scheduler.remove_job(job_id)
        except Exception:
            pass

    # ──────────────────────────────────────────
    # EVENT PROCESSING (per-user pipeline)
    # ──────────────────────────────────────────

    async def detect_and_negotiate_meeting(self, sender: str, message: str, subject: str, channel: str) -> dict:
        """
        Use CrewAI + Claude Sonnet to detect meeting requests and autonomously
        negotiate availability. The AI handles intent detection, time extraction,
        calendar analysis, and reply generation — replacing rigid if/else logic.
        
        Returns: {"is_meeting": True/False, "action": "accepted"/"proposed"/"declined", ...}
        """
        import re, json, asyncio
        from datetime import datetime, timedelta, timezone
        
        # ── Pre-filters (fast, deterministic — skip before calling AI) ──
        skip_senders = ["noreply", "no-reply", "newsletter", "promo", "deals@", "marketing@",
                        "notifications@", "info@", "support@", "billing@", "updates@",
                        "donotreply", "mailer-daemon", "postmaster",
                        "calendar-notification", "calendar.google.com"]
        sender_lower = sender.lower()
        if any(skip in sender_lower for skip in skip_senders):
            return {"is_meeting": False}
        
        # Skip Google Calendar invitation emails (auto-generated, not new requests)
        subject_lower = subject.lower()
        if any(kw in subject_lower for kw in ["invitation:", "accepted:", "declined:", "updated invitation", "canceled event"]):
            logger.info(f"[{self.user_id}] Skipping calendar notification: {subject}")
            return {"is_meeting": False}
        
        # Skip ALL reply emails — a new meeting request always has an original subject.
        # Replies (Re:) are responses to existing threads (including Kairo's own auto-replies),
        # which would cause infinite agent-to-agent reply loops.
        if subject_lower.startswith("re:"):
            logger.info(f"[{self.user_id}] Skipping reply email (not a new meeting request): {subject}")
            return {"is_meeting": False}
        
        # ── Gather context for AI ──
        calendar_events = await self._composio.get_calendar_events(days_ahead=7)
        logger.info(f"[{self.user_id}] Calendar has {len(calendar_events)} events in next 7 days")
        
        # Extract sender email
        sender_email = sender
        email_match = re.search(r'<([^>]+)>', sender)
        if email_match:
            sender_email = email_match.group(1)
        sender_name = sender.split('<')[0].strip() or sender_email
        
        # Format calendar and available slots for AI context
        calendar_summary = self._format_calendar_for_ai(calendar_events)
        
        deep_work_start = self._config.deep_work_start or "09:00"
        deep_work_end = self._config.deep_work_end or "11:00"
        
        available_slots = self._composio.find_available_slots(
            calendar_events=calendar_events,
            days_ahead=7,
            duration_minutes=30,
            skip_deep_work=True,
            deep_work_start=deep_work_start,
            deep_work_end=deep_work_end
        )
        slots_text = "\n".join([f"  - {s['date']} at {s['start']}" for s in available_slots[:10]])
        if not slots_text:
            slots_text = "  (No available slots found in the next 7 days)"
        
        today = datetime.now(timezone.utc)
        day_name = today.strftime("%A")
        
        # ── CrewAI Meeting Analysis ──
        try:
            if not hasattr(self, '_meeting_agent') or self._meeting_agent is None:
                logger.warning(f"[{self.user_id}] Meeting agent not initialized, skipping")
                return {"is_meeting": False}
            
            from crewai import Task, Crew, Process
            
            task_description = f"""Analyze this incoming email and determine if it contains a genuine meeting request from a real person.

EMAIL DETAILS:
From: {sender}
Subject: {subject}
Body:
{message}

TODAY'S DATE: {today.strftime('%Y-%m-%d')} ({day_name})
USER'S TIMEZONE: America/Chicago

DEEP WORK HOURS (BLOCKED — DO NOT SCHEDULE): {deep_work_start} to {deep_work_end} every weekday
The user protects this time for focused work. NEVER accept or propose meetings during these hours.

CURRENT CALENDAR (next 7 days):
{calendar_summary}

AVAILABLE 30-MIN SLOTS (already excludes deep work hours):
{slots_text}

INSTRUCTIONS:
1. Determine if this is a GENUINE meeting request from a real person.
   - Return is_meeting=false for: promotional emails, newsletters, automated notifications, 
     order confirmations, general inquiries without scheduling intent, spam.
   - Return is_meeting=true for: direct requests to meet, schedule a call, grab coffee/lunch/dinner, 
     sync up, catch up, get together, have a meeting, etc.

2. If it IS a meeting request:
   a. Extract the proposed date and time from the email (interpret relative references like 
      "tomorrow", "next Monday", "this Friday" relative to today's date above).
   b. Check if that time conflicts with any existing calendar events listed above.
   c. If the proposed time is AVAILABLE and NOT during deep work hours ({deep_work_start}-{deep_work_end}) → action="accept"
   d. If the proposed time is BUSY or falls during deep work hours → action="propose" and suggest 2-3 alternatives from the available slots above.
      When proposing alternatives for a deep-work conflict, politely mention that the requested time is reserved for focused work.
   e. If NO specific time was proposed → action="propose" and suggest 2-3 good meeting times.
   f. Only use action="decline" if there are absolutely no available slots in the next 7 days.

3. Generate a natural, warm, professional reply email body. Keep it conversational — not robotic.
   Use the sender's first name if apparent. Don't use overly formal language.

RESPOND WITH ONLY A VALID JSON OBJECT (no markdown, no extra text):
{{
    "is_meeting": true or false,
    "action": "accept" or "propose" or "decline",
    "proposed_time": "HH:MM" (24-hour format of accepted/main proposed time),
    "proposed_date": "YYYY-MM-DD",
    "alternative_times": [{{"date": "YYYY-MM-DD", "time": "HH:MM"}}, ...],
    "reply_subject": "Re: original subject",
    "reply_body": "the full email reply text",
    "event_title": "Meeting with Person Name",
    "reasoning": "one-line explanation of your decision"
}}

If is_meeting is false, you can omit all other fields except reasoning."""

            meeting_task = Task(
                description=task_description,
                agent=self._meeting_agent,
                expected_output="A JSON object with the meeting decision, action, reply text, and scheduling details."
            )
            
            crew = Crew(
                agents=[self._meeting_agent],
                tasks=[meeting_task],
                process=Process.sequential,
                verbose=False
            )
            
            # Run synchronous crew.kickoff() in thread pool to avoid blocking async loop
            logger.info(f"[{self.user_id}] Running CrewAI meeting analysis for email from {sender_email}")
            result = await asyncio.to_thread(crew.kickoff)
            result_text = str(result)
            
            logger.info(f"[{self.user_id}] CrewAI result: {result_text[:500]}")
            
            # Parse JSON from response (handle possible markdown wrapping)
            json_text = result_text
            # Strip markdown code fences if present
            md_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', json_text, re.DOTALL)
            if md_match:
                json_text = md_match.group(1)
            else:
                # Find first { to last }
                brace_match = re.search(r'\{.*\}', json_text, re.DOTALL)
                if brace_match:
                    json_text = brace_match.group()
            
            try:
                decision = json.loads(json_text)
            except json.JSONDecodeError as je:
                logger.warning(f"[{self.user_id}] Could not parse CrewAI JSON: {je}\nRaw: {result_text[:300]}")
                return {"is_meeting": False}
            
            # ── Act on AI decision ──
            if not decision.get("is_meeting"):
                logger.info(f"[{self.user_id}] AI determined not a meeting request: {decision.get('reasoning', 'N/A')}")
                return {"is_meeting": False}
            
            action = decision.get("action", "").lower()
            reply_subject = decision.get("reply_subject", f"Re: {subject}")
            reply_body = decision.get("reply_body", "")
            reasoning = decision.get("reasoning", "")
            
            logger.info(f"[{self.user_id}] AI decision: {action} | Reasoning: {reasoning}")
            
            if action == "accept":
                proposed_time = decision.get("proposed_time")
                proposed_date = decision.get("proposed_date")
                event_title = decision.get("event_title", f"Meeting with {sender_name}")
                
                # Send reply
                await self._composio.send_email(to=sender_email, subject=reply_subject, body=reply_body)
                logger.info(f"[{self.user_id}] Sent acceptance reply to {sender_email}")
                
                # Create calendar event
                if proposed_time and proposed_date:
                    try:
                        start_iso = f"{proposed_date}T{proposed_time}:00"
                        await self._composio.create_calendar_event(
                            title=event_title,
                            start_datetime=start_iso,
                            duration_minutes=30,
                            attendees=[sender_email],
                            timezone="America/Chicago"
                        )
                        logger.info(f"[{self.user_id}] Created calendar event: {event_title} at {start_iso}")
                    except Exception as e:
                        logger.warning(f"[{self.user_id}] Could not create calendar event: {e}")
                
                self._log_action(
                    action_type="email_meeting_accepted",
                    channel=channel,
                    target=sender,
                    action_taken=f"AI auto-accepted meeting at {proposed_time} on {proposed_date}. {reasoning}",
                    confidence=0.95,
                    status="executed",
                )
                return {"is_meeting": True, "action": "accepted", "time": proposed_time, "date": proposed_date}
            
            elif action == "propose":
                alternatives = decision.get("alternative_times", [])
                
                # Send reply with alternatives
                await self._composio.send_email(to=sender_email, subject=reply_subject, body=reply_body)
                logger.info(f"[{self.user_id}] Sent alternative proposal to {sender_email}")
                
                self._log_action(
                    action_type="email_meeting_negotiating",
                    channel=channel,
                    target=sender,
                    action_taken=f"AI proposed alternatives. {reasoning}",
                    confidence=0.85,
                    status="executed",
                )
                return {"is_meeting": True, "action": "proposed", "alternatives": alternatives}
            
            elif action == "decline":
                await self._composio.send_email(to=sender_email, subject=reply_subject, body=reply_body)
                logger.info(f"[{self.user_id}] Sent decline to {sender_email}")
                
                self._log_action(
                    action_type="email_meeting_declined",
                    channel=channel,
                    target=sender,
                    action_taken=f"AI declined meeting. {reasoning}",
                    confidence=0.90,
                    status="executed",
                )
                return {"is_meeting": True, "action": "declined", "reason": reasoning}
            
            else:
                logger.warning(f"[{self.user_id}] Unknown AI action: {action}")
                return {"is_meeting": False}
        
        except Exception as e:
            logger.error(f"[{self.user_id}] CrewAI meeting analysis failed: {e}", exc_info=True)
            return {"is_meeting": False}

    def _format_calendar_for_ai(self, calendar_events: list[dict]) -> str:
        """Format calendar events into a human-readable string for AI context."""
        from datetime import datetime
        
        if not calendar_events:
            return "  (No events scheduled in the next 7 days)"
        
        # Group events by date
        events_by_date: dict[str, list] = {}
        for event in calendar_events:
            start_str = event.get("start", "")
            title = event.get("title", event.get("summary", "Untitled"))
            end_str = event.get("end", "")
            
            try:
                start_dt = datetime.fromisoformat(start_str.replace('Z', '+00:00'))
                end_dt = datetime.fromisoformat(end_str.replace('Z', '+00:00')) if end_str else None
                
                date_key = start_dt.strftime("%A, %B %d")
                start_time = start_dt.strftime("%I:%M %p")
                end_time = end_dt.strftime("%I:%M %p") if end_dt else "?"
                
                if date_key not in events_by_date:
                    events_by_date[date_key] = []
                events_by_date[date_key].append(f"{title} ({start_time} - {end_time})")
            except Exception:
                continue
        
        lines = []
        for date, events in events_by_date.items():
            lines.append(f"  {date}:")
            for ev in events:
                lines.append(f"    - {ev}")
        
        return "\n".join(lines) if lines else "  (No events scheduled)"

    def _is_time_available(self, time_str: str, calendar_events: list[dict], check_date=None) -> bool:
        """Check if a specific time is available (no calendar conflicts)."""
        from datetime import datetime, timedelta, timezone
        
        try:
            time_parts = time_str.split(":")
            hour = int(time_parts[0])
            minute = int(time_parts[1]) if len(time_parts) > 1 else 0
            
            # Use provided date or default to tomorrow
            if check_date is None:
                check_date = datetime.now(timezone.utc) + timedelta(days=1)
            
            check_time = check_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
            check_time_end = check_time + timedelta(minutes=30)
            
            logger.info(f"[{self.user_id}] Checking availability: {check_time.isoformat()} to {check_time_end.isoformat()}")
            
            # Check for conflicts
            for event in calendar_events:
                event_start_str = event.get("start", "")
                event_end_str = event.get("end", "")
                
                if not event_start_str or not event_end_str:
                    continue
                
                try:
                    event_start = datetime.fromisoformat(event_start_str.replace('Z', '+00:00'))
                    event_end = datetime.fromisoformat(event_end_str.replace('Z', '+00:00'))
                    
                    # Convert both to UTC for comparison
                    if event_start.tzinfo is None:
                        event_start = event_start.replace(tzinfo=timezone.utc)
                    if event_end.tzinfo is None:
                        event_end = event_end.replace(tzinfo=timezone.utc)
                    
                    # Check overlap
                    if not (check_time_end <= event_start or check_time >= event_end):
                        logger.info(f"[{self.user_id}] Conflict with: {event.get('title', 'Unknown')} ({event_start_str} - {event_end_str})")
                        return False
                except Exception as parse_err:
                    logger.warning(f"Could not parse event time: {parse_err}")
            
            return True
        except Exception as e:
            logger.warning(f"Error checking time availability: {e}")
            return True  # Default to available if we can't check

    async def process_incoming(self, channel: str, payload: dict) -> dict:
        """
        Process an incoming message through THIS USER'S
        Observe → Reason → Act pipeline.

        Each user's runtime uses their own:
        - Relationship graph (their contacts, their sentiment history)
        - Composio tools (their OAuth tokens)
        - Ghost mode config (their thresholds, VIPs)
        - Voice style (their language preferences per contact)
        """
        if not self.is_running:
            return {"action": "ignored", "reason": "agent_not_running"}

        sender = payload.get("sender", "unknown")
        language = payload.get("language", "en")
        sentiment = payload.get("sentiment", 0.5)
        confidence = payload.get("estimated_confidence", 0.7)
        message = payload.get("message", "")
        summary = payload.get("summary", "")
        subject = payload.get("subject", "")

        # ✨ PRIORITY: MEETING NEGOTIATION — Check if this is a meeting request first
        if channel == "email":
            meeting_result = await self.detect_and_negotiate_meeting(
                sender=sender,
                message=message,
                subject=subject,
                channel=channel
            )
            if meeting_result.get("is_meeting"):
                # Meeting was detected and processed
                return meeting_result

        # ── ENERGY-AWARE SCHEDULING: check calendar events first ──
        if channel == "calendar":
            scheduling_decision = self._check_energy_scheduling(channel, payload)
            if scheduling_decision["action"] == "decline":
                return {"action": "auto_declined", "status": "executed", "reason": scheduling_decision["reason"]}

            # Also gather cross-context alerts for calendar events
            cross_alerts = self._check_cross_context(self.user_id)
            if cross_alerts:
                logger.info(f"[{self.user_id}] Cross-context alerts: {len(cross_alerts)}")

        # ── OBSERVE: Update this user's relationship graph ──
        self._graph.record_interaction(
            sender, sentiment, channel=channel, language=language
        )

        # Get this user's relationship data for this contact
        contact_data = {}
        if self._graph.G.has_node(sender):
            contact_data = dict(self._graph.G.nodes[sender])
        contact_language = contact_data.get("preferred_language", language)

        # ── REASON: Apply this user's decision rules ──
        config = self._config
        is_vip = sender in (config.ghost_mode_vip_contacts or [])

        if not config.ghost_mode_enabled:
            self._log_action(
                action_type=f"{channel}_queued", channel=channel,
                target=sender, language=language,
                action_taken=f"Queued {channel} from {sender} for briefing",
                confidence=confidence, status="queued_for_review",
            )
            return {"action": "queued_for_briefing", "status": "queued"}

        if is_vip:
            self._log_action(
                action_type=f"{channel}_vip_escalated", channel=channel,
                target=sender, language=language,
                action_taken=f"VIP escalation: {sender} on {channel}",
                confidence=confidence, status="queued_for_review",
                reasoning=f"{sender} is VIP — always escalated",
            )
            return {"action": "vip_escalated", "status": "queued"}

        if confidence < config.ghost_mode_confidence_threshold:
            self._log_action(
                action_type=f"{channel}_queued", channel=channel,
                target=sender, language=language,
                action_taken=f"Queued — confidence {confidence:.0%} < threshold {config.ghost_mode_confidence_threshold:.0%}",
                confidence=confidence, status="queued_for_review",
                reasoning=f"Below confidence threshold",
            )
            return {"action": "queued_low_confidence", "status": "queued"}

        # ── ACT: Auto-handle using this user's crew ──
        draft = await self._draft_reply(sender, contact_data, message, summary, contact_language, channel)

        # Ghost Mode Execution: if conditions are met, actually send the message
        ghost_executed = False
        if config.ghost_mode_enabled and confidence >= config.ghost_mode_confidence_threshold and not is_vip:
            ghost_executed = await self._execute_ghost_send(channel, sender, draft, payload)

        if ghost_executed:
            self._log_action(
                action_type=f"{channel}_reply", channel=channel,
                target=sender, language=contact_language,
                action_taken=f"Ghost Mode: sent reply to {sender} on {channel} ({contact_language.upper()})",
                confidence=confidence, status="executed",
                reasoning=f"Ghost Mode ON, confidence={confidence:.2f}, not VIP. Auto-sent via {channel}.",
                time_saved=3.0,
                draft=draft,
            )
            return {"action": "auto_replied", "status": "executed", "language": contact_language, "ghost_sent": True}
        else:
            # Confidence too low or VIP or send failed — queue for review
            status = "queued_for_review" if (confidence < config.ghost_mode_confidence_threshold or is_vip) else "executed"
            reason_parts = []
            if is_vip:
                reason_parts.append("contact is VIP")
            if confidence < config.ghost_mode_confidence_threshold:
                reason_parts.append(f"confidence {confidence:.2f} < threshold {config.ghost_mode_confidence_threshold:.2f}")
            if not reason_parts:
                reason_parts.append("send failed, queued for manual review")
            reasoning = f"Ghost Mode draft queued: {', '.join(reason_parts)}"

            self._log_action(
                action_type=f"{channel}_reply", channel=channel,
                target=sender, language=contact_language,
                action_taken=f"Drafted reply to {sender} on {channel} ({contact_language.upper()}) — queued for review",
                confidence=confidence, status=status,
                reasoning=reasoning,
                time_saved=3.0,
                draft=draft,
            )
            return {"action": "queued_for_review", "status": status, "language": contact_language}

    async def _draft_reply(self, sender: str, contact_data: dict,
                            message: str, summary: str, language: str,
                            channel: str) -> str:
        """
        Use this user's CrewAI crew to draft a reply in the right style.
        Falls back to a simple template if CrewAI is not available.
        """
        try:
            from crewai import Task, Crew, Process

            task = Task(
                description=(
                    f"Draft a reply to {sender} on {channel}.\n"
                    f"Their message: {summary or message[:200]}\n"
                    f"Contact profile: {contact_data}\n"
                    f"Language: {language}\n"
                    f"Match tone: {contact_data.get('tone', 'professional')}\n"
                    f"Formality: {contact_data.get('formality_score', 0.5)}\n"
                    f"Keep it concise. Use their greeting style: {contact_data.get('greeting_style', 'Hi')}"
                ),
                agent=self._actor,
                expected_output="A draft reply in the correct tone, style, and language",
            )

            crew = Crew(
                agents=[self._observer, self._reasoner, self._actor],
                tasks=[task],
                process=Process.sequential,
                verbose=False,
            )

            result = crew.kickoff()
            return str(result)

        except Exception as e:
            logger.warning(f"[{self.user_id}] CrewAI draft failed: {e}")
            # Fallback: simple template
            greeting = contact_data.get("greeting_style", "Hi")
            return f"{greeting} {sender.split()[0] if ' ' in sender else sender}, thanks for your message. I'll follow up shortly."

    async def _execute_ghost_send(self, channel: str, sender: str, draft: str, payload: dict) -> bool:
        """
        Actually send a ghost-mode reply via Composio tools.
        Returns True if the send succeeded.
        """
        if not self._composio:
            logger.warning(f"[{self.user_id}] Ghost send skipped — Composio not initialized")
            return False

        try:
            if channel == "email":
                to_email = payload.get("sender_email", payload.get("from", sender))
                subject = payload.get("subject", "Re: your message")
                if not subject.startswith("Re:"):
                    subject = f"Re: {subject}"
                return await self._composio.send_email(to=to_email, subject=subject, body=draft)

            elif channel == "slack":
                slack_channel = payload.get("channel_id", payload.get("channel", sender))
                return await self._composio.send_slack_message(channel=slack_channel, text=draft)

            elif channel == "teams":
                chat_id = payload.get("chat_id", payload.get("conversation_id", sender))
                return await self._composio.send_teams_message(chat_id=chat_id, content=draft)

            else:
                logger.warning(f"[{self.user_id}] Ghost send: unsupported channel '{channel}'")
                return False

        except Exception as e:
            logger.error(f"[{self.user_id}] Ghost send failed on {channel}: {e}")
            return False

    # ──────────────────────────────────────────
    # CROSS-CONTEXT AWARENESS (Feature 6)
    # ──────────────────────────────────────────

    def _check_cross_context(self, user_id: str) -> list:
        """
        Analyse today's actions and calendar events to detect cross-context issues:
        - Mix of personal and work items
        - Wellness nudges for >6 hours of meetings
        - Scheduling conflicts (overlapping events)
        Returns a list of alert dicts.
        """
        alerts = []
        db = SessionLocal()
        try:
            today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
            today_end = today_start + timedelta(days=1)

            today_actions = db.query(AgentAction).filter(
                AgentAction.user_id == user_id,
                AgentAction.timestamp >= today_start,
                AgentAction.timestamp < today_end,
            ).all()

            # --- Detect personal vs work mix ---
            personal_keywords = {"dentist", "doctor", "gym", "personal", "family", "kid", "school", "pickup", "appointment"}
            work_keywords = {"standup", "sprint", "review", "meeting", "sync", "deploy", "client", "project"}

            has_personal = False
            has_work = False
            meeting_minutes = 0
            calendar_events = []  # (start_str, end_str, summary)

            for action in today_actions:
                text = (
                    (action.action_taken or "") + " " +
                    (action.original_message_summary or "") + " " +
                    (action.draft_content or "")
                ).lower()

                if any(kw in text for kw in personal_keywords):
                    has_personal = True
                if any(kw in text for kw in work_keywords):
                    has_work = True

                # Count meeting time from calendar actions
                if action.channel == "calendar":
                    # Estimate 30 min per calendar action as default
                    meeting_minutes += 30
                    calendar_events.append({
                        "summary": action.action_taken,
                        "timestamp": action.timestamp,
                    })

            if has_personal and has_work:
                alerts.append({
                    "type": "cross_context",
                    "severity": "info",
                    "message": "You have both personal and work items today. Kairo will manage transitions.",
                })

            # --- Wellness nudge for heavy meeting days ---
            if meeting_minutes > 360:  # >6 hours
                alerts.append({
                    "type": "wellness",
                    "severity": "warning",
                    "message": f"You have ~{round(meeting_minutes / 60, 1)} hours of meetings today. Consider blocking time for a break.",
                })
            elif meeting_minutes > 240:  # >4 hours
                alerts.append({
                    "type": "wellness",
                    "severity": "info",
                    "message": f"Moderate meeting load today (~{round(meeting_minutes / 60, 1)} hours). Pace yourself.",
                })

            # --- Scheduling conflicts (overlapping timestamps within 30 min) ---
            sorted_events = sorted(calendar_events, key=lambda e: e["timestamp"])
            for i in range(len(sorted_events) - 1):
                curr = sorted_events[i]
                nxt = sorted_events[i + 1]
                gap = (nxt["timestamp"] - curr["timestamp"]).total_seconds() / 60
                if gap < 5:  # Less than 5 minutes between events
                    alerts.append({
                        "type": "conflict",
                        "severity": "warning",
                        "message": f"Potential scheduling conflict: '{curr['summary']}' and '{nxt['summary']}' overlap or are back-to-back.",
                    })

        except Exception as e:
            logger.error(f"[{user_id}] Cross-context check failed: {e}")
        finally:
            db.close()

        return alerts

    # ──────────────────────────────────────────
    # ENERGY-AWARE SCHEDULING (Feature 2)
    # ──────────────────────────────────────────

    def _check_energy_scheduling(self, channel: str, message_data: dict) -> dict:
        """
        Evaluate a calendar event against energy-aware scheduling rules:
        - Decline non-VIP meetings during deep work hours (if auto_decline_enabled)
        - Decline if daily meeting count exceeds max_meetings_per_day
        Returns a decision dict: {"action": "decline"|"allow", "reason": ...}
        """
        config = self._config
        if channel != "calendar" or not config.auto_decline_enabled:
            return {"action": "allow", "reason": "auto_decline not enabled or not a calendar event"}

        event_time_str = message_data.get("start_time", "")
        event_title = message_data.get("title", message_data.get("summary", ""))
        sender = message_data.get("sender", message_data.get("organizer", "unknown"))

        # --- Check if event falls during deep work hours ---
        is_during_deep_work = False
        try:
            if event_time_str:
                event_dt = datetime.fromisoformat(event_time_str.replace("Z", "+00:00"))
                event_hour_min = event_dt.strftime("%H:%M")
            else:
                event_hour_min = datetime.now(timezone.utc).strftime("%H:%M")

            deep_start = config.deep_work_start or "09:00"
            deep_end = config.deep_work_end or "11:00"
            if deep_start <= event_hour_min <= deep_end:
                is_during_deep_work = True
        except (ValueError, TypeError):
            pass

        # --- Check VIP status ---
        is_vip = sender in (config.ghost_mode_vip_contacts or [])

        # Also check ContactRelationship importance
        if not is_vip:
            db = SessionLocal()
            try:
                contact = db.query(ContactRelationship).filter(
                    ContactRelationship.user_id == self.user_id,
                    ContactRelationship.contact_name == sender,
                    ContactRelationship.importance_score > 0.8,
                ).first()
                if contact:
                    is_vip = True
            finally:
                db.close()

        # --- Deep work protection ---
        if is_during_deep_work and not is_vip:
            decline_reason = (
                f"Auto-declined '{event_title}' from {sender} — "
                f"falls during deep work hours ({config.deep_work_start}-{config.deep_work_end})"
            )
            self._log_action(
                action_type="meeting_decline",
                channel="calendar",
                target=sender,
                action_taken=decline_reason,
                confidence=0.9,
                status="executed",
                reasoning="Deep work protection: non-VIP meeting during focus hours",
                time_saved=30.0,
                draft=f"Hi, I'm currently in a deep work block ({config.deep_work_start}-{config.deep_work_end}). Could we reschedule to a later slot? Thanks!",
            )
            return {"action": "decline", "reason": decline_reason}

        # --- Max meetings per day check ---
        db = SessionLocal()
        try:
            today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
            today_meeting_count = db.query(AgentAction).filter(
                AgentAction.user_id == self.user_id,
                AgentAction.channel == "calendar",
                AgentAction.timestamp >= today_start,
                AgentAction.action_type.notin_(["meeting_decline"]),
            ).count()
        finally:
            db.close()

        max_meetings = config.max_meetings_per_day or 6
        if today_meeting_count >= max_meetings and not is_vip:
            decline_reason = (
                f"Auto-declined '{event_title}' from {sender} — "
                f"already at {today_meeting_count}/{max_meetings} meetings today"
            )
            self._log_action(
                action_type="meeting_decline",
                channel="calendar",
                target=sender,
                action_taken=decline_reason,
                confidence=0.85,
                status="executed",
                reasoning=f"Meeting cap reached: {today_meeting_count}/{max_meetings} for today",
                time_saved=30.0,
                draft=f"Hi, my schedule is fully booked today ({today_meeting_count} meetings). Can we find a slot tomorrow?",
            )
            return {"action": "decline", "reason": decline_reason}

        return {"action": "allow", "reason": "Passed all energy-scheduling checks"}

    # ──────────────────────────────────────────
    # SCHEDULED JOBS (per-user)
    # ──────────────────────────────────────────

    async def _run_morning_briefing(self):
        """Generate morning briefing for THIS user only."""
        tone_shifts = self._graph.detect_tone_shifts()
        neglected = self._graph.find_neglected_relationships()

        briefing_parts = []
        if tone_shifts:
            briefing_parts.append(f"{len(tone_shifts)} tone shift alert(s)")
        if neglected:
            briefing_parts.append(f"{len(neglected)} contact(s) need attention")

        db = SessionLocal()
        try:
            queued_count = db.query(AgentAction).filter(
                AgentAction.user_id == self.user_id,
                AgentAction.status == "queued_for_review",
            ).count()
            if queued_count:
                briefing_parts.append(f"{queued_count} item(s) awaiting review")
        finally:
            db.close()

        summary = "; ".join(briefing_parts) if briefing_parts else "All clear"
        lang = self._config.voice_language or "en"

        self._log_action(
            action_type="morning_briefing", channel="voice",
            action_taken=f"Morning briefing: {summary}",
            confidence=1.0, language=lang, time_saved=5.0,
        )
        logger.info(f"[{self.user_id}] Morning briefing: {summary}")

    async def _run_ghost_triage(self):
        """Process queued items for THIS user's Ghost Mode."""
        db = SessionLocal()
        try:
            queued = db.query(AgentAction).filter(
                AgentAction.user_id == self.user_id,
                AgentAction.agent_id == self.agent_id,
                AgentAction.status == "queued_for_review",
            ).count()
            if queued > 0:
                logger.info(f"[{self.user_id}] Ghost triage: {queued} items pending")
        finally:
            db.close()

    async def _poll_emails(self):
        """Poll Gmail for new unread emails and process meeting requests."""
        if not self._composio or not self.is_running:
            return
        
        # Prevent overlapping polls (CrewAI calls take 10-20s, poll runs every 30s)
        if self._poll_lock.locked():
            logger.debug(f"[{self.user_id}] Poll skipped — previous poll still running")
            return
        
        async with self._poll_lock:
            try:
                emails = await self._composio.fetch_recent_emails(max_results=5)
                if not emails:
                    return
                
                logger.info(f"[{self.user_id}] Polled {len(emails)} unread emails")
                
                for email in emails:
                    sender = email.get("from", "")
                    subject = email.get("subject", "")
                    body = email.get("body", "")
                    email_id = email.get("id", "")
                    
                    if not sender or not body:
                        continue
                    
                    # Compound dedup key: subject+sender (catches same email even if ID changes)
                    dedup_key = f"{sender.strip().lower()}|{subject.strip().lower()}"
                    
                    # Skip emails we've already processed (track by ID)
                    if email_id and email_id in self._processed_email_ids:
                        continue
                    
                    # Fallback dedup by subject+sender (Composio may return different IDs across calls)
                    if dedup_key in self._processed_email_keys:
                        logger.debug(f"[{self.user_id}] Skipping duplicate email (subject+sender match): {subject}")
                        if email_id:
                            self._processed_email_ids.add(email_id)
                        continue
                    
                    # Global cross-agent dedup: if ANY agent already claimed this email, skip
                    rm = get_runtime_manager()
                    if email_id and email_id in rm._global_processed_emails:
                        logger.debug(f"[{self.user_id}] Skipping email {email_id} — already claimed by another agent")
                        self._processed_email_ids.add(email_id)
                        self._processed_email_keys.add(dedup_key)
                        continue
                    if email_id:
                        rm._global_processed_emails.add(email_id)
                    
                    # Mark as processed BEFORE processing (prevents re-entry)
                    if email_id:
                        self._processed_email_ids.add(email_id)
                    self._processed_email_keys.add(dedup_key)
                    
                    # Keep sets from growing too large
                    if len(self._processed_email_ids) > 500:
                        self._processed_email_ids = set(list(self._processed_email_ids)[-200:])
                    if len(self._processed_email_keys) > 500:
                        self._processed_email_keys = set(list(self._processed_email_keys)[-200:])
                    self._save_processed_ids()  # Persist to survive restarts
                    # Also trim global set
                    if len(rm._global_processed_emails) > 1000:
                        rm._global_processed_emails = set(list(rm._global_processed_emails)[-500:])
                    
                    logger.info(f"[{self.user_id}] Processing email from {sender}: {subject} (id={email_id[:20] if email_id else 'NONE'})")
                    
                    # Build payload dict matching process_incoming's expected format
                    try:
                        payload = {
                            "sender": sender,
                            "subject": subject,
                            "message": body,
                            "summary": body[:200],
                            "language": "en",
                            "sentiment": 0.5,
                            "estimated_confidence": 0.7,
                        }
                        result = await self.process_incoming("email", payload)
                        logger.info(f"[{self.user_id}] Email processed: {result.get('action', 'unknown')}")
                        
                        # Mark email as read after processing to prevent re-fetching
                        if email_id:
                            try:
                                await self._composio.mark_email_read(email_id)
                            except Exception:
                                pass  # Non-critical — dedup sets are the primary safeguard
                        
                    except Exception as e:
                        logger.error(f"[{self.user_id}] Error processing email from {sender}: {e}")
                    
            except Exception as e:
                logger.error(f"[{self.user_id}] Email poll failed: {e}")

    # ──────────────────────────────────────────
    # STOP / PAUSE
    # ──────────────────────────────────────────

    async def stop(self):
        """Stop this user's agent. Persist graph, deregister jobs."""
        logger.info(f"⏹ Stopping agent for user={self.user_id}")
        self._persist_graph()
        self._deregister_user_scheduler_jobs()
        self._set_status("stopped")
        self.is_running = False
        self._log_action(
            action_type="agent_stopped", channel="dashboard",
            action_taken="Agent stopped, graph persisted", confidence=1.0,
        )

    async def pause(self):
        """Pause this user's agent. Keeps graph in memory."""
        self._deregister_user_scheduler_jobs()
        self._set_status("paused")
        self.is_running = False
        logger.info(f"⏸ Agent PAUSED for user={self.user_id}")

    # ──────────────────────────────────────────
    # HELPERS
    # ──────────────────────────────────────────

    def _set_status(self, status: str):
        db = SessionLocal()
        try:
            agent = db.query(AgentConfig).filter(AgentConfig.id == self.agent_id).first()
            if agent:
                agent.status = status
                db.commit()
        finally:
            db.close()

    def _persist_graph(self):
        """Save this user's NetworkX graph to DB."""
        db = SessionLocal()
        try:
            agent = db.query(AgentConfig).filter(AgentConfig.id == self.agent_id).first()
            if agent:
                agent.relationship_graph_data = json.loads(self._graph.to_json())
                db.commit()
                logger.info(f"[{self.user_id}] Graph persisted: {len(self._graph.G.nodes)} nodes")
        finally:
            db.close()

    def _get_integration_status(self) -> dict:
        if self._composio:
            return self._composio.get_connection_status()
        return {"gmail": False, "calendar": False, "slack": False, "teams": False, "github": False}

    def _log_action(self, action_type: str, channel: str, action_taken: str,
                     confidence: float, target: str = "", language: str = "",
                     status: str = "executed", reasoning: str = "",
                     time_saved: float = 0, amount: float = 0, draft: str = ""):
        db = SessionLocal()
        try:
            action = AgentAction(
                user_id=self.user_id,
                agent_id=self.agent_id,
                action_type=action_type,
                channel=channel,
                target_contact=target,
                language_used=language or self._config.voice_language or "en",
                action_taken=action_taken,
                draft_content=draft,
                confidence_score=confidence,
                reasoning=reasoning,
                status=status,
                estimated_time_saved_minutes=time_saved,
                amount_spent=amount,
            )
            db.add(action)
            db.commit()
        except Exception as e:
            logger.error(f"[{self.user_id}] Log action failed: {e}")
        finally:
            db.close()


# ══════════════════════════════════════════════
# RUNTIME MANAGER — one per server, manages ALL user runtimes
# ══════════════════════════════════════════════

class RuntimeManager:
    """
    Global singleton that manages all active AgentRuntimes.
    Each user's runtime is completely isolated.

    Key: agent_id → AgentRuntime
    Also maintains user_id → agent_id mapping for webhook routing.
    """

    def __init__(self):
        self._runtimes: dict[str, AgentRuntime] = {}    # agent_id → runtime
        self._user_agents: dict[str, str] = {}          # user_id → agent_id
        self._global_processed_emails: set = set()      # Cross-agent email dedup

    async def launch_agent(self, user_id: str, agent_id: str) -> dict:
        """Create and launch a per-user agent runtime."""
        if agent_id in self._runtimes:
            return {"error": "Agent already running", "agent_id": agent_id}

        runtime = AgentRuntime(user_id, agent_id)
        result = await runtime.launch()

        self._runtimes[agent_id] = runtime
        self._user_agents[user_id] = agent_id

        logger.info(f"RuntimeManager: {self.active_count} agents now running")
        return result

    async def stop_agent(self, agent_id: str):
        runtime = self._runtimes.get(agent_id)
        if runtime:
            await runtime.stop()
            self._user_agents.pop(runtime.user_id, None)
            del self._runtimes[agent_id]

    async def pause_agent(self, agent_id: str):
        runtime = self._runtimes.get(agent_id)
        if runtime:
            await runtime.pause()
            self._user_agents.pop(runtime.user_id, None)
            del self._runtimes[agent_id]

    def get_runtime(self, agent_id: str) -> Optional[AgentRuntime]:
        return self._runtimes.get(agent_id)

    def get_runtime_by_user(self, user_id: str) -> Optional[AgentRuntime]:
        """Get a user's runtime by user_id (used by webhooks)."""
        agent_id = self._user_agents.get(user_id)
        if agent_id:
            return self._runtimes.get(agent_id)
        return None

    def is_running(self, agent_id: str) -> bool:
        return agent_id in self._runtimes

    @property
    def active_count(self) -> int:
        return len(self._runtimes)

    async def recover_running_agents(self):
        """
        Called on server startup.
        Finds all agents with status="running" in the DB and re-launches them.
        This handles Railway restarts, deploys, etc.
        """
        db = SessionLocal()
        try:
            running_agents = db.query(AgentConfig).filter(
                AgentConfig.status == "running"
            ).all()

            if not running_agents:
                logger.info("No agents to recover on startup")
                return

            logger.info(f"Recovering {len(running_agents)} running agent(s)...")

            for agent_config in running_agents:
                try:
                    await self.launch_agent(agent_config.user_id, agent_config.id)
                    logger.info(f"Recovered agent for user={agent_config.user_id}")
                except Exception as e:
                    logger.error(f"Failed to recover agent {agent_config.id}: {e}")
                    # Mark as paused if recovery fails
                    agent_config.status = "paused"
                    db.commit()

        finally:
            db.close()

        logger.info(f"Recovery complete: {self.active_count} agents running")


# ── Singleton ──

_runtime_manager: Optional[RuntimeManager] = None


def get_runtime_manager() -> RuntimeManager:
    global _runtime_manager
    if _runtime_manager is None:
        _runtime_manager = RuntimeManager()
    return _runtime_manager
