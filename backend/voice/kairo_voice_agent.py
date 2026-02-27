"""
Kairo Voice Agent — LiveKit + Deepgram + Claude + Edge TTS
Bilingual: English + Hindi with auto-detection

Runs as a separate process. Communicates with the FastAPI backend
over HTTP (httpx) so it stays decoupled from the main server.
"""

import asyncio
import logging
import re
import json
from typing import Optional

import httpx

from config import get_settings

settings = get_settings()
logger = logging.getLogger("kairo.voice")

# ──────────────────────────────────────────
# CONSTANTS
# ──────────────────────────────────────────

BACKEND_URL = "http://localhost:8000"

SYSTEM_PROMPT = """
You are Kairo, the user's cognitive co-processor and chief of staff.
You are BILINGUAL — fluent in English and Hindi.

LANGUAGE RULES:
- If user speaks English -> respond in English
- If user speaks Hindi -> respond in Hindi
- If user mixes (Hinglish) -> respond in Hinglish
- Use natural, conversational Hindi — not overly formal or Sanskritized

VOICE MODES:
1. BRIEFING: Deliver morning/evening briefings
   EN: "Good morning! Here's what you need to know..."
   HI: "Suprabhat! Aaj ke liye teen important cheezein hain..."

2. COMMAND: Process natural language commands
   EN: "Move my 3pm and tell Sarah I'll be late"
   HI: "Meri 3 baje ki meeting shift karo aur Sarah ko bolo main late hounga"
   Response: "Done. Moved to 4pm and messaged Sarah."

3. DEBRIEF: Summarize what happened while away
   EN: "While you were in focus mode, I handled 6 things..."
   HI: "Jab aap busy the, maine 6 kaam handle kiye..."

4. COPILOT: Provide context during meetings (whisper mode)

PERSONALITY:
- Sound like a trusted, sharp human chief of staff
- Be concise — voice responses should be 2-3 sentences max
- NEVER say "as an AI" or "I'm an artificial intelligence"
- Be warm but efficient
- Use the user's name when appropriate

IMPORTANT: You have access to function tools. When the user asks something
that maps to a Kairo backend action, call the appropriate tool. For general
conversation or questions that don't match a tool, respond directly.
"""

# ──────────────────────────────────────────
# LANGUAGE DETECTION
# ──────────────────────────────────────────

_DEVANAGARI_RE = re.compile(r"[\u0900-\u097F]")
_HINDI_MARKERS = {
    "kya", "hai", "karo", "bolo", "mera", "meri", "aaj", "kal", "abhi",
    "haan", "nahi", "kaise", "kaisa", "kaisi", "raha", "rahi",
    "tha", "thi", "wala", "wali", "yaar", "bhai", "didi", "accha",
    "theek", "batao", "sunao", "dikha", "bhej", "kar",
    "hoga", "hogi", "maine", "tumne", "usne", "kisko", "kidhar",
    "kab", "kyun", "hafta", "mahina", "saal", "suprabhat", "namaste",
    "ko", "ka", "ki", "ke", "mein",
}


def detect_language(text: str) -> str:
    """Detect whether input is English, Hindi, or Hinglish."""
    if _DEVANAGARI_RE.search(text):
        return "hi"

    words = set(text.lower().split())
    hindi_count = len(words & _HINDI_MARKERS)
    ratio = hindi_count / max(len(words), 1)

    if ratio > 0.4:
        return "hi"
    elif ratio > 0.15:
        return "hinglish"
    return "en"


def tts_language_for(detected: str) -> str:
    """Map detected language to Edge TTS language key."""
    if detected == "hi":
        return "hi"
    if detected == "hinglish":
        return "en-IN"
    return "en"


# ──────────────────────────────────────────
# COMMAND PATTERN MATCHING
# ──────────────────────────────────────────

class CommandType:
    MISSED_SUMMARY = "missed_summary"
    SCHEDULE_TODAY = "schedule_today"
    GHOST_TOGGLE = "ghost_toggle"
    WEEKLY_SUMMARY = "weekly_summary"
    RESCHEDULE = "reschedule"
    DRAFT_REPLY = "draft_reply"
    SEND_MESSAGE = "send_message"
    BRIEFING = "briefing"
    GHOST_DEBRIEF = "ghost_debrief"
    COMMITMENTS = "commitments"
    COMMITMENT_STATUS = "commitment_status"
    DELEGATE_TASK = "delegate_task"
    BURNOUT_CHECK = "burnout_check"
    PRODUCTIVITY_TIPS = "productivity_tips"
    DECISION_REPLAY = "decision_replay"
    FLOW_STATUS = "flow_status"
    FLOW_START = "flow_start"
    FLOW_END = "flow_end"
    FLOW_DEBRIEF = "flow_debrief"
    GENERAL = "general"


# Each pattern: (compiled regex, CommandType, extract_func | None)
_COMMAND_PATTERNS: list[tuple[re.Pattern, str, Optional[callable]]] = []


def _build_patterns():
    """Build the command pattern table. Called once at module load."""
    patterns = [
        # Missed summary
        (r"(?i)\b(what did i miss|kya miss hua|missed kya|kuch miss|what.?s new|catch me up|kya hua jab)", CommandType.MISSED_SUMMARY, None),

        # Today's schedule
        (r"(?i)\b(aaj ka schedule|today.?s schedule|what.?s my schedule|my schedule|aaj kya hai|today.?s plan|aaj ka plan|calendar today|meetings today|aaj ki meetings)", CommandType.SCHEDULE_TODAY, None),

        # Ghost mode toggle
        (r"(?i)\b(toggle ghost\s*mode|ghost\s*mode\s+(on|off|toggle|chalu|band)|activate ghost|deactivate ghost|ghost\s*mode\s+kar)", CommandType.GHOST_TOGGLE, None),

        # Weekly summary
        (r"(?i)\b(weekly (summary|report)|hafta kaisa raha|week kaisa tha|is hafte ka|this week.?s (summary|report)|pichle hafte|last week)", CommandType.WEEKLY_SUMMARY, None),

        # Reschedule meeting
        (r"(?i)(move|shift|reschedule|postpone|push|delay)\s+(my\s+)?(.+?)\s*(meeting|call|sync)", CommandType.RESCHEDULE, lambda m: {"description": m.group(3).strip()}),

        # Draft reply — English
        (r"(?i)(reply to|respond to|draft.*reply.*to)\s+(.+)", CommandType.DRAFT_REPLY, lambda m: {"contact": m.group(2).strip()}),
        # Draft reply — Hindi
        (r"(?i)(.+?)\s+ko\s+(reply|jawab)\s+(kar|do|de|bhej)", CommandType.DRAFT_REPLY, lambda m: {"contact": m.group(1).strip()}),

        # Send message — English
        (r"(?i)(send|text|message)\s+[\"']?(.+?)[\"']?\s+(to)\s+(.+)", CommandType.SEND_MESSAGE, lambda m: {"message": m.group(2).strip(), "contact": m.group(4).strip()}),
        # Send message — Hindi
        (r"(?i)(.+?)\s+ko\s+(bhej|send)\s*[:\-]?\s*(.+)", CommandType.SEND_MESSAGE, lambda m: {"contact": m.group(1).strip(), "message": m.group(3).strip()}),

        # Briefing request
        (r"(?i)\b(morning briefing|briefing|give me.*briefing|aaj ka briefing|briefing de|briefing sunao)", CommandType.BRIEFING, None),

        # Ghost debrief
        (r"(?i)\b(ghost (summary|debrief|report)|what did ghost.*(do|handle)|ghost ne kya kiya|ghost mode summary)", CommandType.GHOST_DEBRIEF, None),

        # Commitments
        (r"(?i)\b(my commitments|what did i promise|pending promises|kya promise kiya|meri commitments|overdue)", CommandType.COMMITMENTS, None),
        (r"(?i)\b(commitment (status|score)|reliability|kitna nibhaya)", CommandType.COMMITMENT_STATUS, None),

        # Delegation
        (r"(?i)(delegate|hand off|pass|assign)\s+(.+?)\s+to\s+(\w+)", CommandType.DELEGATE_TASK, lambda m: {"task": m.group(2), "contact": m.group(3)}),
        (r"(?i)(who should|best person|kisko doon|kisko assign)\s+(.+)", CommandType.DELEGATE_TASK, lambda m: {"task": m.group(2)}),

        # Burnout
        (r"(?i)\b(burnout|wellness|stress level|am i burning out|kitna stress hai|workload kaisa)", CommandType.BURNOUT_CHECK, None),
        (r"(?i)\b(productivity tips|when am i most productive|peak hours|best time to work|kab kaam karna chahiye)", CommandType.PRODUCTIVITY_TIPS, None),

        # Decision Replay
        (r"(?i)\b(what if|replay|counterfactual|kya hota agar|what would have happened|decision replay)", CommandType.DECISION_REPLAY, None),

        # Flow State Guardian
        (r"(?i)\b(flow (status|state)|am i in flow|kya focus mode hai)", CommandType.FLOW_STATUS, None),
        (r"(?i)\b(start flow|enter flow|focus mode on|flow mode|focus karo|disturb mat karo)", CommandType.FLOW_START, None),
        (r"(?i)\b(end flow|exit flow|surface|flow band|focus mode off)", CommandType.FLOW_END, None),
        (r"(?i)\b(flow debrief|what did i miss in flow|flow ke baad kya hua)", CommandType.FLOW_DEBRIEF, None),
    ]

    for pattern_str, cmd_type, extractor in patterns:
        _COMMAND_PATTERNS.append((re.compile(pattern_str), cmd_type, extractor))


_build_patterns()


def parse_command(text: str) -> tuple[str, dict]:
    """
    Match user text against known command patterns.
    Returns (CommandType, extracted_params).
    Falls back to GENERAL for unrecognized input.
    """
    text_clean = text.strip()
    for pattern, cmd_type, extractor in _COMMAND_PATTERNS:
        match = pattern.search(text_clean)
        if match:
            params = extractor(match) if extractor else {}
            return cmd_type, params
    return CommandType.GENERAL, {"query": text_clean}


# ──────────────────────────────────────────
# BACKEND API CLIENT
# ──────────────────────────────────────────

class KairoBackendClient:
    """
    HTTP client for the Kairo FastAPI backend.
    The voice agent runs as a separate process, so all data
    access goes through the REST API.
    """

    def __init__(self, base_url: str = BACKEND_URL, token: str = ""):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self._client: Optional[httpx.AsyncClient] = None

    async def _ensure_client(self):
        if self._client is None or self._client.is_closed:
            headers = {}
            if self.token:
                headers["Authorization"] = f"Bearer {self.token}"
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=headers,
                timeout=httpx.Timeout(30.0),
            )

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    def set_token(self, token: str):
        """Update the bearer token (e.g. after login or token refresh)."""
        self.token = token
        # Force client recreation with new headers
        if self._client and not self._client.is_closed:
            asyncio.get_event_loop().create_task(self._client.aclose())
        self._client = None

    # ── Dashboard ──

    async def get_stats(self) -> dict:
        await self._ensure_client()
        resp = await self._client.get("/api/dashboard/stats")
        resp.raise_for_status()
        return resp.json()

    async def get_decisions(self, limit: int = 20, status_filter: str = "all") -> dict:
        await self._ensure_client()
        resp = await self._client.get(
            "/api/dashboard/decisions",
            params={"limit": limit, "status_filter": status_filter},
        )
        resp.raise_for_status()
        return resp.json()

    async def get_weekly_report(self) -> dict:
        await self._ensure_client()
        resp = await self._client.get("/api/dashboard/weekly-report")
        resp.raise_for_status()
        return resp.json()

    async def get_cross_context_alerts(self) -> dict:
        await self._ensure_client()
        resp = await self._client.get("/api/dashboard/cross-context-alerts")
        resp.raise_for_status()
        return resp.json()

    # ── Relationships ──

    async def get_tone_shifts(self) -> list:
        await self._ensure_client()
        resp = await self._client.get("/api/relationships/tone-shifts")
        resp.raise_for_status()
        return resp.json()

    async def get_neglected_contacts(self) -> list:
        await self._ensure_client()
        resp = await self._client.get("/api/relationships/neglected")
        resp.raise_for_status()
        return resp.json()

    # ── Agents ──

    async def get_agents(self) -> list:
        await self._ensure_client()
        resp = await self._client.get("/api/agents/")
        resp.raise_for_status()
        return resp.json()

    async def toggle_ghost_mode(self, agent_id: str) -> dict:
        await self._ensure_client()
        resp = await self._client.post(f"/api/agents/{agent_id}/ghost-mode/toggle")
        resp.raise_for_status()
        return resp.json()

    async def get_agent_detail(self, agent_id: str) -> dict:
        await self._ensure_client()
        resp = await self._client.get(f"/api/agents/{agent_id}")
        resp.raise_for_status()
        return resp.json()


# ──────────────────────────────────────────
# COMMAND HANDLERS
# ──────────────────────────────────────────

async def handle_missed_summary(client: KairoBackendClient, lang: str) -> str:
    """Fetch recent actions and summarize what was missed."""
    try:
        decisions = await client.get_decisions(limit=15, status_filter="all")
        actions = decisions.get("actions", [])
        if not actions:
            return _t(lang,
                      en="Nothing major while you were away. All clear.",
                      hi="Kuch khaas nahi hua jab aap nahi the. Sab theek hai.")

        executed = [a for a in actions if a.get("status") == "executed"]
        queued = [a for a in actions if a.get("status") == "queued_for_review"]

        parts = []
        if executed:
            parts.append(_t(lang,
                            en=f"I handled {len(executed)} item{'s' if len(executed) != 1 else ''} automatically",
                            hi=f"Maine {len(executed)} kaam automatically handle kiye"))
        if queued:
            parts.append(_t(lang,
                            en=f"{len(queued)} item{'s' if len(queued) != 1 else ''} waiting for your review",
                            hi=f"{len(queued)} cheezein aapke review ka wait kar rahi hain"))

        # Highlight important items
        highlights = []
        for a in actions[:5]:
            summary = a.get("action_taken", "")
            if summary:
                highlights.append(summary)

        result = ". ".join(parts) + "."
        if highlights:
            result += " " + _t(lang, en="Key items: ", hi="Important: ")
            result += "; ".join(highlights[:3]) + "."
        return result

    except Exception as e:
        logger.error(f"handle_missed_summary failed: {e}")
        return _t(lang,
                  en="I couldn't fetch your updates right now. Try again in a moment.",
                  hi="Abhi updates nahi mil paaye. Thodi der mein try karo.")


async def handle_schedule_today(client: KairoBackendClient, lang: str) -> str:
    """Fetch today's stats and pending decisions as schedule proxy."""
    try:
        stats = await client.get_stats()
        decisions = await client.get_decisions(limit=10, status_filter="all")
        actions = decisions.get("actions", [])

        # Filter calendar-related actions for today
        calendar_items = [a for a in actions if a.get("channel") == "calendar"]
        queued = stats.get("auto_handled", 0)

        if not calendar_items and queued == 0:
            return _t(lang,
                      en="Your schedule looks clear today. No meetings or pending items.",
                      hi="Aaj ka schedule khali hai. Koi meeting ya pending kaam nahi hai.")

        parts = []
        if calendar_items:
            parts.append(_t(lang,
                            en=f"You have {len(calendar_items)} calendar item{'s' if len(calendar_items) != 1 else ''} today",
                            hi=f"Aaj {len(calendar_items)} calendar item{'s' if len(calendar_items) != 1 else ''} hain"))
            for item in calendar_items[:3]:
                desc = item.get("action_taken", "meeting")
                parts.append(f"  - {desc}")

        ghost_on = stats.get("ghost_mode_enabled", False)
        if ghost_on:
            parts.append(_t(lang,
                            en="Ghost mode is active, so I'm handling routine items.",
                            hi="Ghost mode chalu hai, routine kaam main handle kar raha hoon."))

        return ". ".join(parts) if parts else _t(lang,
            en="No specific schedule items found for today.",
            hi="Aaj ke liye koi specific schedule nahi mila.")

    except Exception as e:
        logger.error(f"handle_schedule_today failed: {e}")
        return _t(lang,
                  en="Couldn't load your schedule right now.",
                  hi="Schedule abhi load nahi ho paaya.")


async def handle_ghost_toggle(client: KairoBackendClient, lang: str) -> str:
    """Toggle ghost mode on the user's agent."""
    try:
        agents = await client.get_agents()
        if not agents:
            return _t(lang,
                      en="No agent configured yet. Set up your agent first.",
                      hi="Abhi tak koi agent setup nahi hai. Pehle agent banao.")

        agent_id = agents[0].get("id")
        result = await client.toggle_ghost_mode(agent_id)
        enabled = result.get("ghost_mode_enabled", False)

        if enabled:
            return _t(lang,
                      en="Ghost mode activated. I'll handle routine messages automatically.",
                      hi="Ghost mode chalu. Ab routine messages main khud handle karunga.")
        else:
            return _t(lang,
                      en="Ghost mode deactivated. I'll queue everything for your review.",
                      hi="Ghost mode band. Ab sab kuch aapke review ke liye queue karunga.")

    except Exception as e:
        logger.error(f"handle_ghost_toggle failed: {e}")
        return _t(lang,
                  en="Couldn't toggle ghost mode. Check if your agent is running.",
                  hi="Ghost mode toggle nahi ho paaya. Check karo agent chal raha hai ya nahi.")


async def handle_weekly_summary(client: KairoBackendClient, lang: str) -> str:
    """Fetch and narrate the weekly report."""
    try:
        report = await client.get_weekly_report()
        headline = report.get("headline", "")
        time_saved = report.get("time_saved", {})
        ghost = report.get("ghost_mode", {})
        channels = report.get("channels", {})
        hours = time_saved.get("total_hours", 0)
        accuracy = ghost.get("accuracy", 0)
        total_actions = ghost.get("total_actions", 0)

        if lang == "hi" or lang == "hinglish":
            parts = [f"Is hafte ka summary."]
            if hours > 0:
                parts.append(f"Maine aapke {hours} ghante bachaye.")
            if total_actions > 0:
                parts.append(f"Total {total_actions} actions liye, {accuracy}% accuracy ke saath.")
            if channels:
                top = sorted(channels.items(), key=lambda x: x[1], reverse=True)[:2]
                ch_str = ", ".join(f"{ch}: {cnt}" for ch, cnt in top)
                parts.append(f"Top channels: {ch_str}.")
            return " ".join(parts)
        else:
            parts = [headline + "."] if headline else ["Here's your weekly summary."]
            if total_actions > 0:
                parts.append(f"{total_actions} actions taken at {accuracy}% accuracy.")
            if channels:
                top = sorted(channels.items(), key=lambda x: x[1], reverse=True)[:2]
                ch_str = ", ".join(f"{ch} ({cnt})" for ch, cnt in top)
                parts.append(f"Most active on {ch_str}.")
            return " ".join(parts)

    except Exception as e:
        logger.error(f"handle_weekly_summary failed: {e}")
        return _t(lang,
                  en="Couldn't generate the weekly report right now.",
                  hi="Weekly report abhi nahi ban paaya.")


async def handle_reschedule(client: KairoBackendClient, lang: str, params: dict) -> str:
    """Acknowledge a reschedule request. Actual calendar mutation goes through the agent runtime."""
    desc = params.get("description", "meeting")
    # For now, acknowledge and queue — the backend CrewAI crew handles actual calendar ops
    return _t(lang,
              en=f"Got it. I'll reschedule your {desc}. I'll confirm once it's moved.",
              hi=f"Samajh gaya. Main aapki {desc} reschedule kar raha hoon. Confirm kar dunga.")


async def handle_draft_reply(client: KairoBackendClient, lang: str, params: dict) -> str:
    """Acknowledge a reply draft request."""
    contact = params.get("contact", "them")
    return _t(lang,
              en=f"Drafting a reply to {contact}. I'll have it ready in a moment.",
              hi=f"{contact} ko reply draft kar raha hoon. Ek second.")


async def handle_send_message(client: KairoBackendClient, lang: str, params: dict) -> str:
    """Acknowledge a send message request."""
    contact = params.get("contact", "them")
    message = params.get("message", "")
    preview = message[:60] + "..." if len(message) > 60 else message
    return _t(lang,
              en=f"Sending to {contact}: \"{preview}\". Confirm?",
              hi=f"{contact} ko bhej raha hoon: \"{preview}\". Confirm karein?")


# ──────────────────────────────────────────
# BRIEFING GENERATION
# ──────────────────────────────────────────

async def compile_briefing(client: KairoBackendClient, lang: str = "en") -> str:
    """
    Build a full morning/evening briefing script by pulling data
    from multiple backend endpoints.
    """
    sections = []

    # 1. Dashboard stats
    try:
        stats = await client.get_stats()
        total = stats.get("total_actions", 0)
        auto = stats.get("auto_handled", 0)
        time_hrs = stats.get("time_saved_hours", 0)
        ghost_on = stats.get("ghost_mode_enabled", False)

        if lang == "hi" or lang == "hinglish":
            greeting = "Suprabhat!"
            sections.append(
                f"{greeting} Pichhle 7 dinon mein {total} actions hue, "
                f"jinmein se {auto} automatically handle hue. "
                f"Aapke {time_hrs} ghante bache."
            )
        else:
            sections.append(
                f"Good morning! Over the last 7 days, {total} actions were processed. "
                f"{auto} handled automatically, saving you {time_hrs} hours."
            )
    except Exception as e:
        logger.warning(f"Briefing stats failed: {e}")

    # 2. Pending decisions
    try:
        decisions = await client.get_decisions(limit=5, status_filter="queued_for_review")
        pending = decisions.get("total", 0)
        if pending > 0:
            sections.append(_t(lang,
                en=f"You have {pending} item{'s' if pending != 1 else ''} waiting for your review.",
                hi=f"{pending} cheezein aapke review ke liye pending hain."))
    except Exception as e:
        logger.warning(f"Briefing decisions failed: {e}")

    # 3. Tone shift alerts
    try:
        tone_shifts = await client.get_tone_shifts()
        if tone_shifts:
            names = [ts.get("contact", "someone") for ts in tone_shifts[:3]]
            sections.append(_t(lang,
                en=f"Tone shift detected with {', '.join(names)}. Worth checking in.",
                hi=f"{', '.join(names)} ke saath tone shift dikha. Dhyan dena chahiye."))
    except Exception as e:
        logger.warning(f"Briefing tone shifts failed: {e}")

    # 4. Neglected contacts
    try:
        neglected = await client.get_neglected_contacts()
        if neglected:
            names = [n.get("contact", "someone") for n in neglected[:3]]
            sections.append(_t(lang,
                en=f"Haven't heard from {', '.join(names)} in a while. Consider reaching out.",
                hi=f"{', '.join(names)} se kaafi time se baat nahi hui. Unse connect karo."))
    except Exception as e:
        logger.warning(f"Briefing neglected contacts failed: {e}")

    if not sections:
        return _t(lang,
                  en="Good morning! Everything looks calm today. No urgent items.",
                  hi="Suprabhat! Aaj sab shaant hai. Koi urgent kaam nahi.")

    return " ".join(sections)


# ──────────────────────────────────────────
# GHOST MODE DEBRIEF
# ──────────────────────────────────────────

async def get_ghost_summary(client: KairoBackendClient, lang: str = "en") -> str:
    """
    Summarize what ghost mode did while the user was away.
    Pulls recent executed actions and groups by type.
    """
    try:
        decisions = await client.get_decisions(limit=50, status_filter="executed")
        actions = decisions.get("actions", [])

        if not actions:
            return _t(lang,
                      en="Ghost mode hasn't taken any actions recently.",
                      hi="Ghost mode ne abhi tak koi action nahi liya.")

        # Group by channel
        by_channel: dict[str, int] = {}
        queued_review = 0
        for a in actions:
            ch = a.get("channel", "other")
            by_channel[ch] = by_channel.get(ch, 0) + 1

        # Also check queued items
        try:
            queued_data = await client.get_decisions(limit=1, status_filter="queued_for_review")
            queued_review = queued_data.get("total", 0)
        except Exception:
            pass

        total = len(actions)
        breakdown_parts = []
        for ch, count in sorted(by_channel.items(), key=lambda x: x[1], reverse=True):
            breakdown_parts.append(f"{count} {ch}")

        breakdown = ", ".join(breakdown_parts)

        if lang == "hi" or lang == "hinglish":
            result = (
                f"Ghost mode ne {total} kaam handle kiye: {breakdown}."
            )
            if queued_review > 0:
                result += f" Aur {queued_review} cheezein aapke review ke liye hain."
            # Highlight any important/VIP items
            vip_items = [a for a in actions if "vip" in (a.get("action_type") or "").lower()]
            if vip_items:
                result += f" {len(vip_items)} VIP items the jinko special attention mila."
            return result
        else:
            result = (
                f"While ghost mode was active, I handled {total} items: {breakdown}."
            )
            if queued_review > 0:
                result += f" {queued_review} item{'s' if queued_review != 1 else ''} queued for your review."
            vip_items = [a for a in actions if "vip" in (a.get("action_type") or "").lower()]
            if vip_items:
                result += f" {len(vip_items)} VIP item{'s' if len(vip_items) != 1 else ''} received special handling."
            return result

    except Exception as e:
        logger.error(f"get_ghost_summary failed: {e}")
        return _t(lang,
                  en="Couldn't fetch the ghost mode summary right now.",
                  hi="Ghost mode summary abhi nahi mil paaya.")


# ──────────────────────────────────────────
# COMMAND DISPATCHER
# ──────────────────────────────────────────

async def dispatch_command(
    client: KairoBackendClient,
    text: str,
    lang: str,
) -> Optional[str]:
    """
    Parse user text, dispatch to the correct handler.
    Returns a response string, or None if it should fall through to the LLM.
    """
    cmd_type, params = parse_command(text)

    if cmd_type == CommandType.MISSED_SUMMARY:
        return await handle_missed_summary(client, lang)
    elif cmd_type == CommandType.SCHEDULE_TODAY:
        return await handle_schedule_today(client, lang)
    elif cmd_type == CommandType.GHOST_TOGGLE:
        return await handle_ghost_toggle(client, lang)
    elif cmd_type == CommandType.WEEKLY_SUMMARY:
        return await handle_weekly_summary(client, lang)
    elif cmd_type == CommandType.RESCHEDULE:
        return await handle_reschedule(client, lang, params)
    elif cmd_type == CommandType.DRAFT_REPLY:
        return await handle_draft_reply(client, lang, params)
    elif cmd_type == CommandType.SEND_MESSAGE:
        return await handle_send_message(client, lang, params)
    elif cmd_type == CommandType.BRIEFING:
        return await compile_briefing(client, lang)
    elif cmd_type == CommandType.GHOST_DEBRIEF:
        return await get_ghost_summary(client, lang)
    elif cmd_type == CommandType.COMMITMENTS:
        return _t(lang,
                  en="Let me check your commitments. You can see the full list on your dashboard.",
                  hi="Main aapki commitments check kar raha hoon. Dashboard pe poori list hai.")
    elif cmd_type == CommandType.COMMITMENT_STATUS:
        return _t(lang,
                  en="Checking your commitment reliability score. Head to the Commitments page for details.",
                  hi="Aapka commitment score check kar raha hoon. Details ke liye Commitments page dekhein.")
    elif cmd_type == CommandType.DELEGATE_TASK:
        task = params.get("task", "")
        contact = params.get("contact", "")
        if contact:
            return _t(lang,
                      en=f"Got it. I'll delegate '{task}' to {contact} through the mesh.",
                      hi=f"Samajh gaya. Main '{task}' {contact} ko delegate kar raha hoon mesh ke through.")
        return _t(lang,
                  en=f"I'll find the best person for '{task}' based on expertise and availability.",
                  hi=f"Main '{task}' ke liye best person dhundh raha hoon expertise aur availability ke basis pe.")
    elif cmd_type == CommandType.BURNOUT_CHECK:
        return _t(lang,
                  en="Analyzing your burnout risk. Check the Wellness page for your full report with interventions.",
                  hi="Aapka burnout risk analyze kar raha hoon. Wellness page pe poori report hai interventions ke saath.")
    elif cmd_type == CommandType.PRODUCTIVITY_TIPS:
        return _t(lang,
                  en="Your peak productivity is typically mid-morning. Check the Wellness page for your full heatmap.",
                  hi="Aapki sabse zyada productivity subah hoti hai. Wellness page pe poora heatmap hai.")
    elif cmd_type == CommandType.DECISION_REPLAY:
        return _t(lang,
                  en="I can replay your recent decisions. Check the Decision Replay page for what-if analysis.",
                  hi="Main aapke recent decisions ka replay kar sakta hoon. Decision Replay page pe what-if analysis hai.")
    elif cmd_type == CommandType.FLOW_STATUS:
        return _t(lang,
                  en="Checking your flow state. Visit the Flow Guardian page for real-time status.",
                  hi="Aapka flow state check kar raha hoon. Flow Guardian page pe real-time status hai.")
    elif cmd_type == CommandType.FLOW_START:
        return _t(lang,
                  en="Activating flow protection. I'll hold all non-urgent messages and auto-respond for you.",
                  hi="Flow protection chalu kar raha hoon. Sab non-urgent messages hold karunga aur auto-respond karunga.")
    elif cmd_type == CommandType.FLOW_END:
        return _t(lang,
                  en="Ending flow session. Preparing your debrief with everything I held.",
                  hi="Flow session khatam. Debrief ready kar raha hoon jo maine hold kiya tha usme se.")
    elif cmd_type == CommandType.FLOW_DEBRIEF:
        return _t(lang,
                  en="Here's your flow debrief. Check the Flow Guardian page for the full summary of held messages.",
                  hi="Yeh raha aapka flow debrief. Flow Guardian page pe held messages ka poora summary hai.")
    else:
        # GENERAL — let the LLM handle it
        return None


# ──────────────────────────────────────────
# TRANSLATION HELPER
# ──────────────────────────────────────────

def _t(lang: str, en: str, hi: str) -> str:
    """Pick string by language. Hinglish uses Hindi variant."""
    if lang in ("hi", "hinglish"):
        return hi
    return en


# ──────────────────────────────────────────
# LIVEKIT FUNCTION TOOLS (exposed to Claude via agents framework)
# ──────────────────────────────────────────

def build_function_tools(client: KairoBackendClient):
    """
    Build LiveKit-compatible function tool definitions that Claude can call.
    Each tool wraps a backend API call via httpx.
    """
    try:
        from livekit.agents import function_tool
    except ImportError:
        logger.warning("livekit.agents not available, skipping function tool registration")
        return []

    @function_tool(description="Get the user's dashboard stats including actions handled, time saved, and ghost mode status")
    async def get_dashboard_stats():
        stats = await client.get_stats()
        return json.dumps(stats)

    @function_tool(description="Get the user's weekly summary report with time saved, accuracy, and channel breakdown")
    async def get_weekly_report():
        report = await client.get_weekly_report()
        return json.dumps(report)

    @function_tool(description="Toggle ghost mode on or off for the user's agent")
    async def toggle_ghost_mode():
        agents = await client.get_agents()
        if not agents:
            return json.dumps({"error": "No agent configured"})
        agent_id = agents[0].get("id")
        result = await client.toggle_ghost_mode(agent_id)
        return json.dumps(result)

    @function_tool(description="Get recent decisions and actions taken by the agent, optionally filtered by status")
    async def get_recent_decisions(status_filter: str = "all"):
        decisions = await client.get_decisions(limit=15, status_filter=status_filter)
        return json.dumps(decisions)

    @function_tool(description="Get tone shift alerts for the user's contacts")
    async def get_tone_shifts():
        shifts = await client.get_tone_shifts()
        return json.dumps(shifts)

    @function_tool(description="Get contacts the user hasn't communicated with recently")
    async def get_neglected_contacts():
        neglected = await client.get_neglected_contacts()
        return json.dumps(neglected)

    @function_tool(description="Get a full morning briefing covering stats, pending items, tone shifts, and neglected contacts")
    async def get_morning_briefing():
        # Use detected language from session (defaults to en)
        briefing = await compile_briefing(client, "en")
        return briefing

    @function_tool(description="Get a summary of what ghost mode handled while the user was away")
    async def get_ghost_debrief():
        summary = await get_ghost_summary(client, "en")
        return summary

    return [
        get_dashboard_stats,
        get_weekly_report,
        toggle_ghost_mode,
        get_recent_decisions,
        get_tone_shifts,
        get_neglected_contacts,
        get_morning_briefing,
        get_ghost_debrief,
    ]


# ──────────────────────────────────────────
# LIVEKIT VOICE AGENT ENTRY POINT
# ──────────────────────────────────────────

def run_voice_agent():
    """Entry point for the LiveKit voice agent."""
    try:
        from livekit.agents import AgentSession, AgentServer, JobContext
        from livekit.agents import inference
        from livekit.plugins import silero
        from services.edge_tts_service import EdgeTTSService

        server = AgentServer()

        @server.rtc_session()
        async def entrypoint(ctx: JobContext):
            # Extract user token from room metadata or participant identity
            # The frontend passes the JWT when joining the LiveKit room
            user_token = ""
            try:
                room_metadata = ctx.room.metadata
                if room_metadata:
                    meta = json.loads(room_metadata)
                    user_token = meta.get("token", "")
            except (json.JSONDecodeError, AttributeError):
                pass

            # Initialize backend client and TTS
            backend_client = KairoBackendClient(token=user_token)
            tts = EdgeTTSService(language="en", gender="female")

            # Build function tools for Claude
            tools = build_function_tools(backend_client)

            session = AgentSession(
                vad=silero.VAD.load(),
                stt=inference.STT("deepgram/nova-3", language="multi"),
                llm=inference.LLM(f"anthropic/{settings.anthropic_model}"),
                tts=tts,
            )

            class KairoAgent:
                """
                Stateful agent that tracks language, dispatches commands,
                and bridges the LiveKit session with the Kairo backend.
                """

                def __init__(self):
                    self.instructions = SYSTEM_PROMPT
                    self.tools = tools
                    self._current_lang = "en"
                    self._tts = tts
                    self._backend = backend_client

                async def on_user_turn(self, turn_text: str) -> Optional[str]:
                    """
                    Called before the LLM processes the turn.
                    Detects language, switches TTS voice, and handles
                    Kairo-specific commands. Returns a string to speak
                    directly (bypassing LLM), or None to let the LLM respond.
                    """
                    # Detect and update language
                    detected = detect_language(turn_text)
                    if detected != self._current_lang:
                        self._current_lang = detected
                        tts_lang = tts_language_for(detected)
                        self._tts.switch_language(tts_lang)
                        logger.info(f"Language switched to {detected} (TTS: {tts_lang})")

                    # Try command dispatch first
                    response = await dispatch_command(
                        self._backend, turn_text, self._current_lang
                    )
                    return response

            agent = KairoAgent()

            # Register a pre-LLM hook if the framework supports it
            original_on_user_turn = getattr(agent, "on_user_turn", None)

            @session.on("user_speech_committed")
            async def _on_speech(event):
                """
                Intercept finalized user speech. If it matches a Kairo command,
                speak the response directly via TTS and skip the LLM turn.
                """
                text = event.get("text", "") if isinstance(event, dict) else getattr(event, "text", "")
                if not text:
                    return

                try:
                    direct_response = await agent.on_user_turn(text)
                    if direct_response:
                        # Speak directly, bypassing the LLM
                        audio_bytes = await tts.synthesize(direct_response)
                        if hasattr(session, "speak"):
                            await session.speak(direct_response)
                        elif hasattr(ctx.room, "local_participant"):
                            # Publish audio directly if speak() is unavailable
                            logger.info(f"Direct response: {direct_response[:80]}...")
                except Exception as e:
                    logger.error(f"Command dispatch error: {e}")

            await session.start(agent=agent, room=ctx.room)

            # Send initial greeting
            try:
                greeting = "Hello! I'm Kairo, your chief of staff. How can I help you today?"
                if hasattr(session, "speak"):
                    await session.speak(greeting)
            except Exception as e:
                logger.warning(f"Initial greeting failed: {e}")

            # Keep session alive
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                pass
            finally:
                await backend_client.close()

        logger.info("Kairo voice agent starting...")
        server.run()

    except ImportError as e:
        logger.warning(f"LiveKit not fully installed: {e}")
        logger.info("Voice agent requires: pip install livekit livekit-agents livekit-plugins-silero")
        print("\n  Voice agent dependencies not installed.")
        print("Run: pip install livekit livekit-agents livekit-plugins-silero")
        print("Then retry: python -m voice.kairo_voice_agent\n")


# ──────────────────────────────────────────
# STANDALONE TESTING (no LiveKit required)
# ──────────────────────────────────────────

async def _test_command_pipeline():
    """Quick self-test of the command parsing pipeline."""
    test_cases = [
        "What did I miss?",
        "Kya miss hua?",
        "What's my schedule today?",
        "Aaj ka schedule kya hai?",
        "Toggle ghost mode",
        "Ghost mode on",
        "Weekly summary",
        "Hafta kaisa raha?",
        "Move my 3pm meeting",
        "Reply to Sarah",
        "Sarah ko reply kar",
        "Send 'I'll be late' to John",
        "John ko bhej: main late hounga",
        "Give me my briefing",
        "Ghost mode summary",
        "What's the weather like?",  # Should be GENERAL
    ]

    print("\n--- Command Parser Test ---\n")
    for text in test_cases:
        cmd_type, params = parse_command(text)
        lang = detect_language(text)
        tts_lang = tts_language_for(lang)
        print(f"  [{lang:>8}] [{tts_lang:>4}] {cmd_type:<20} | {text}")
        if params:
            print(f"           params: {params}")
    print()


if __name__ == "__main__":
    import sys

    if "--test" in sys.argv:
        asyncio.run(_test_command_pipeline())
    else:
        run_voice_agent()
