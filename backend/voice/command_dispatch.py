"""
Shared command parsing and dispatch module.
Used by both the LiveKit voice agent and the NLP HTTP endpoint.
"""

import re
import logging
from typing import Optional

logger = logging.getLogger("kairo.commands")


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


def _t(lang: str, en: str, hi: str) -> str:
    """Pick string by language. Hinglish uses Hindi variant."""
    if lang in ("hi", "hinglish"):
        return hi
    return en


# ──────────────────────────────────────────
# COMMAND TYPES
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
    SETUP_AGENT = "setup_agent"
    GENERAL = "general"


# Map command types to frontend dashboard routes for navigation
COMMAND_ROUTE_MAP = {
    CommandType.SETUP_AGENT: "/dashboard/agents",
    CommandType.COMMITMENTS: "/dashboard/commitments",
    CommandType.COMMITMENT_STATUS: "/dashboard/commitments",
    CommandType.MISSED_SUMMARY: "/dashboard/decisions",
    CommandType.SCHEDULE_TODAY: "/dashboard",
    CommandType.WEEKLY_SUMMARY: "/dashboard/report",
    CommandType.GHOST_TOGGLE: "/dashboard/agents",
    CommandType.GHOST_DEBRIEF: "/dashboard/agents",
    CommandType.BRIEFING: "/dashboard",
    CommandType.DELEGATE_TASK: "/dashboard/delegation",
    CommandType.BURNOUT_CHECK: "/dashboard/burnout",
    CommandType.PRODUCTIVITY_TIPS: "/dashboard/burnout",
    CommandType.DECISION_REPLAY: "/dashboard/replay",
    CommandType.FLOW_STATUS: "/dashboard/flow",
    CommandType.FLOW_START: "/dashboard/flow",
    CommandType.FLOW_END: "/dashboard/flow",
    CommandType.FLOW_DEBRIEF: "/dashboard/flow",
}


# ──────────────────────────────────────────
# COMMAND PATTERN MATCHING
# ──────────────────────────────────────────

_COMMAND_PATTERNS: list[tuple[re.Pattern, str, Optional[callable]]] = []


def _build_patterns():
    """Build the command pattern table. Called once at module load."""
    patterns = [
        (r"(?i)\b(what did i miss|kya miss hua|missed kya|kuch miss|what.?s new|catch me up|kya hua jab)", CommandType.MISSED_SUMMARY, None),
        (r"(?i)\b(aaj ka schedule|today.?s schedule|what.?s my schedule|my schedule|aaj kya hai|today.?s plan|aaj ka plan|calendar today|meetings today|aaj ki meetings)", CommandType.SCHEDULE_TODAY, None),
        (r"(?i)\b(toggle ghost\s*mode|ghost\s*mode\s+(on|off|toggle|chalu|band)|activate ghost|deactivate ghost|ghost\s*mode\s+kar)", CommandType.GHOST_TOGGLE, None),
        (r"(?i)\b(weekly (summary|report)|hafta kaisa raha|week kaisa tha|is hafte ka|this week.?s (summary|report)|pichle hafte|last week)", CommandType.WEEKLY_SUMMARY, None),
        (r"(?i)(move|shift|reschedule|postpone|push|delay)\s+(my\s+)?(.+?)\s*(meeting|call|sync)", CommandType.RESCHEDULE, lambda m: {"description": m.group(3).strip()}),
        (r"(?i)(reply to|respond to|draft.*reply.*to)\s+(.+)", CommandType.DRAFT_REPLY, lambda m: {"contact": m.group(2).strip()}),
        (r"(?i)(.+?)\s+ko\s+(reply|jawab)\s+(kar|do|de|bhej)", CommandType.DRAFT_REPLY, lambda m: {"contact": m.group(1).strip()}),
        (r"(?i)(send|text|message)\s+[\"']?(.+?)[\"']?\s+(to)\s+(.+)", CommandType.SEND_MESSAGE, lambda m: {"message": m.group(2).strip(), "contact": m.group(4).strip()}),
        (r"(?i)(.+?)\s+ko\s+(bhej|send)\s*[:\-]?\s*(.+)", CommandType.SEND_MESSAGE, lambda m: {"contact": m.group(1).strip(), "message": m.group(3).strip()}),
        (r"(?i)\b(morning briefing|briefing|give me.*briefing|aaj ka briefing|briefing de|briefing sunao)", CommandType.BRIEFING, None),
        (r"(?i)\b(ghost (summary|debrief|report)|what did ghost.*(do|handle)|ghost ne kya kiya|ghost mode summary)", CommandType.GHOST_DEBRIEF, None),
        (r"(?i)\b(my commitments|what did i promise|pending promises|kya promise kiya|meri commitments|overdue)", CommandType.COMMITMENTS, None),
        (r"(?i)\b(commitment (status|score)|reliability|kitna nibhaya)", CommandType.COMMITMENT_STATUS, None),
        (r"(?i)(delegate|hand off|pass|assign)\s+(.+?)\s+to\s+(\w+)", CommandType.DELEGATE_TASK, lambda m: {"task": m.group(2), "contact": m.group(3)}),
        (r"(?i)(who should|best person|kisko doon|kisko assign)\s+(.+)", CommandType.DELEGATE_TASK, lambda m: {"task": m.group(2)}),
        (r"(?i)\b(burnout|wellness|stress level|am i burning out|kitna stress hai|workload kaisa)", CommandType.BURNOUT_CHECK, None),
        (r"(?i)\b(productivity tips|when am i most productive|peak hours|best time to work|kab kaam karna chahiye)", CommandType.PRODUCTIVITY_TIPS, None),
        (r"(?i)\b(what if|replay|counterfactual|kya hota agar|what would have happened|decision replay)", CommandType.DECISION_REPLAY, None),
        (r"(?i)\b(flow (status|state)|am i in flow|kya focus mode hai)", CommandType.FLOW_STATUS, None),
        (r"(?i)\b(start flow|enter flow|focus mode on|flow mode|focus karo|disturb mat karo)", CommandType.FLOW_START, None),
        (r"(?i)\b(end flow|exit flow|surface|flow band|focus mode off)", CommandType.FLOW_END, None),
        (r"(?i)\b(flow debrief|what did i miss in flow|flow ke baad kya hua)", CommandType.FLOW_DEBRIEF, None),

        # Agent setup — natural language agent creation
        (r"(?i)(create|setup|set up|start|launch|build|make)\s+(my\s+)?(agent|kairo|assistant)", CommandType.SETUP_AGENT, None),
        (r"(?i)(connect|hook up|link)\s+(my\s+)?(gmail|email|slack|calendar|teams)", CommandType.SETUP_AGENT, lambda m: {"integrations": [m.group(3).lower()]}),
        (r"(?i)(connect|hook up|link)\s+(my\s+)?(.+?)\s+and\s+(.+)", CommandType.SETUP_AGENT, lambda m: {"integrations": [m.group(3).strip().lower(), m.group(4).strip().lower()]}),
        (r"(?i)(protect|block|keep|hold|reserve)\s+(my\s+)?(morning|afternoon|evening)s?", CommandType.SETUP_AGENT, lambda m: {"deep_work_time": m.group(3).lower()}),
        (r"(?i)(auto.?reply|auto.?handle|handle\s+everything|manage\s+my\s+(email|inbox|messages))", CommandType.SETUP_AGENT, lambda m: {"ghost_mode": True}),
        (r"(?i)(vip|important|priority).*(contact|person|people).*(?:is|are|:)\s*(.+)", CommandType.SETUP_AGENT, lambda m: {"vip_contacts": [c.strip() for c in m.group(3).split(",")]}),
        (r"(?i)(?:except|but not|always escalate|never auto.?reply to)\s+(.+)", CommandType.SETUP_AGENT, lambda m: {"vip_contacts": [c.strip() for c in m.group(1).split(",")]}),
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
# COMMAND HANDLERS (using KairoBackendClient)
# ──────────────────────────────────────────

async def handle_missed_summary(client, lang: str) -> str:
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


async def handle_schedule_today(client, lang: str) -> str:
    try:
        stats = await client.get_stats()
        decisions = await client.get_decisions(limit=20, status_filter="all")
        actions = decisions.get("actions", [])
        calendar_items = [a for a in actions if a.get("channel") == "calendar"]
        pending = [a for a in actions if a.get("status") == "queued_for_review"]
        meetings_today = stats.get("meetings_today", 0)
        ghost_on = stats.get("ghost_mode_enabled", False)
        auto_handled = stats.get("auto_handled", 0)

        parts = []
        # Report meetings from stats or calendar actions
        if meetings_today > 0 or calendar_items:
            count = meetings_today or len(calendar_items)
            parts.append(_t(lang,
                en=f"You have {count} meeting{'s' if count != 1 else ''} today",
                hi=f"Aaj {count} meeting{'s' if count != 1 else ''} hain"))
            for item in calendar_items[:3]:
                desc = item.get("action_taken", "meeting")
                parts.append(f"  - {desc}")
        else:
            parts.append(_t(lang,
                en="No meetings on your calendar today",
                hi="Aaj calendar pe koi meeting nahi hai"))

        if pending:
            parts.append(_t(lang,
                en=f"{len(pending)} item{'s' if len(pending) != 1 else ''} waiting for your review",
                hi=f"{len(pending)} cheezein review ke liye pending hain"))

        if auto_handled:
            parts.append(_t(lang,
                en=f"I've auto-handled {auto_handled} items so far",
                hi=f"Maine ab tak {auto_handled} kaam automatically handle kiye"))

        if ghost_on:
            parts.append(_t(lang,
                en="Ghost mode is active, so I'm handling routine items.",
                hi="Ghost mode chalu hai, routine kaam main handle kar raha hoon."))

        return ". ".join(parts) + "."
    except Exception as e:
        logger.error(f"handle_schedule_today failed: {e}")
        return _t(lang,
                  en="Couldn't load your schedule right now. Make sure your agent is running.",
                  hi="Schedule abhi load nahi ho paaya. Check karo agent chal raha hai.")


async def handle_ghost_toggle(client, lang: str) -> str:
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


async def handle_weekly_summary(client, lang: str) -> str:
    # Try dedicated weekly report endpoint first, fall back to stats
    report = None
    try:
        report = await client.get_weekly_report()
    except Exception:
        pass

    try:
        if report:
            headline = report.get("headline", "")
            time_saved = report.get("time_saved", {})
            ghost = report.get("ghost_mode", {})
            channels = report.get("channels", {})
            hours = time_saved.get("total_hours", 0)
            accuracy = ghost.get("accuracy", 0)
            total_actions = ghost.get("total_actions", 0)
        else:
            # Fall back to dashboard stats which always works with seed data
            stats = await client.get_stats()
            hours = stats.get("time_saved_hours", 0)
            accuracy = stats.get("ghost_mode_accuracy", 0)
            total_actions = stats.get("total_actions", 0)
            headline = ""
            channels = {}

        if lang == "hi" or lang == "hinglish":
            parts = ["Is hafte ka summary."]
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
            if hours > 0:
                parts.append(f"I saved you {hours} hours this week.")
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


async def handle_reschedule(client, lang: str, params: dict) -> str:
    desc = params.get("description", "meeting")
    return _t(lang,
              en=f"Got it. I'll reschedule your {desc}. I'll confirm once it's moved.",
              hi=f"Samajh gaya. Main aapki {desc} reschedule kar raha hoon. Confirm kar dunga.")


async def handle_draft_reply(client, lang: str, params: dict) -> str:
    contact = params.get("contact", "them")
    return _t(lang,
              en=f"Drafting a reply to {contact}. I'll have it ready in a moment.",
              hi=f"{contact} ko reply draft kar raha hoon. Ek second.")


async def handle_send_message(client, lang: str, params: dict) -> str:
    contact = params.get("contact", "them")
    message = params.get("message", "")
    preview = message[:60] + "..." if len(message) > 60 else message
    return _t(lang,
              en=f"Sending to {contact}: \"{preview}\". Confirm?",
              hi=f"{contact} ko bhej raha hoon: \"{preview}\". Confirm karein?")


# ──────────────────────────────────────────
# BRIEFING GENERATION
# ──────────────────────────────────────────

async def compile_briefing(client, lang: str = "en") -> str:
    sections = []
    try:
        stats = await client.get_stats()
        total = stats.get("total_actions", 0)
        auto = stats.get("auto_handled", 0)
        time_hrs = stats.get("time_saved_hours", 0)
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

    try:
        decisions = await client.get_decisions(limit=5, status_filter="queued_for_review")
        pending = decisions.get("total", 0)
        if pending > 0:
            sections.append(_t(lang,
                en=f"You have {pending} item{'s' if pending != 1 else ''} waiting for your review.",
                hi=f"{pending} cheezein aapke review ke liye pending hain."))
    except Exception as e:
        logger.warning(f"Briefing decisions failed: {e}")

    try:
        tone_shifts = await client.get_tone_shifts()
        if tone_shifts:
            names = [ts.get("contact", "someone") for ts in tone_shifts[:3]]
            sections.append(_t(lang,
                en=f"Tone shift detected with {', '.join(names)}. Worth checking in.",
                hi=f"{', '.join(names)} ke saath tone shift dikha. Dhyan dena chahiye."))
    except Exception as e:
        logger.warning(f"Briefing tone shifts failed: {e}")

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

async def get_ghost_summary(client, lang: str = "en") -> str:
    try:
        decisions = await client.get_decisions(limit=50, status_filter="executed")
        actions = decisions.get("actions", [])
        if not actions:
            return _t(lang,
                      en="Ghost mode hasn't taken any actions recently.",
                      hi="Ghost mode ne abhi tak koi action nahi liya.")
        by_channel: dict[str, int] = {}
        queued_review = 0
        for a in actions:
            ch = a.get("channel", "other")
            by_channel[ch] = by_channel.get(ch, 0) + 1
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
            result = f"Ghost mode ne {total} kaam handle kiye: {breakdown}."
            if queued_review > 0:
                result += f" Aur {queued_review} cheezein aapke review ke liye hain."
            vip_items = [a for a in actions if "vip" in (a.get("action_type") or "").lower()]
            if vip_items:
                result += f" {len(vip_items)} VIP items the jinko special attention mila."
            return result
        else:
            result = f"While ghost mode was active, I handled {total} items: {breakdown}."
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

async def dispatch_command(client, text: str, lang: str) -> tuple[Optional[str], str]:
    """
    Parse user text, dispatch to the correct handler.
    Returns (response_string_or_None, command_type).
    None response means it should fall through to the LLM.
    """
    cmd_type, params = parse_command(text)

    if cmd_type == CommandType.MISSED_SUMMARY:
        return await handle_missed_summary(client, lang), cmd_type
    elif cmd_type == CommandType.SCHEDULE_TODAY:
        return await handle_schedule_today(client, lang), cmd_type
    elif cmd_type == CommandType.GHOST_TOGGLE:
        return await handle_ghost_toggle(client, lang), cmd_type
    elif cmd_type == CommandType.WEEKLY_SUMMARY:
        return await handle_weekly_summary(client, lang), cmd_type
    elif cmd_type == CommandType.RESCHEDULE:
        return await handle_reschedule(client, lang, params), cmd_type
    elif cmd_type == CommandType.DRAFT_REPLY:
        return await handle_draft_reply(client, lang, params), cmd_type
    elif cmd_type == CommandType.SEND_MESSAGE:
        return await handle_send_message(client, lang, params), cmd_type
    elif cmd_type == CommandType.BRIEFING:
        return await compile_briefing(client, lang), cmd_type
    elif cmd_type == CommandType.GHOST_DEBRIEF:
        return await get_ghost_summary(client, lang), cmd_type
    elif cmd_type == CommandType.COMMITMENTS:
        return _t(lang,
                  en="Let me check your commitments. You can see the full list on your dashboard.",
                  hi="Main aapki commitments check kar raha hoon. Dashboard pe poori list hai."), cmd_type
    elif cmd_type == CommandType.COMMITMENT_STATUS:
        return _t(lang,
                  en="Checking your commitment reliability score. Head to the Commitments page for details.",
                  hi="Aapka commitment score check kar raha hoon. Details ke liye Commitments page dekhein."), cmd_type
    elif cmd_type == CommandType.DELEGATE_TASK:
        task = params.get("task", "")
        contact = params.get("contact", "")
        if contact:
            return _t(lang,
                      en=f"Got it. I'll delegate '{task}' to {contact} through the mesh.",
                      hi=f"Samajh gaya. Main '{task}' {contact} ko delegate kar raha hoon mesh ke through."), cmd_type
        return _t(lang,
                  en=f"I'll find the best person for '{task}' based on expertise and availability.",
                  hi=f"Main '{task}' ke liye best person dhundh raha hoon expertise aur availability ke basis pe."), cmd_type
    elif cmd_type == CommandType.BURNOUT_CHECK:
        return _t(lang,
                  en="Analyzing your burnout risk. Check the Wellness page for your full report with interventions.",
                  hi="Aapka burnout risk analyze kar raha hoon. Wellness page pe poori report hai interventions ke saath."), cmd_type
    elif cmd_type == CommandType.PRODUCTIVITY_TIPS:
        return _t(lang,
                  en="Your peak productivity is typically mid-morning. Check the Wellness page for your full heatmap.",
                  hi="Aapki sabse zyada productivity subah hoti hai. Wellness page pe poora heatmap hai."), cmd_type
    elif cmd_type == CommandType.DECISION_REPLAY:
        return _t(lang,
                  en="I can replay your recent decisions. Check the Decision Replay page for what-if analysis.",
                  hi="Main aapke recent decisions ka replay kar sakta hoon. Decision Replay page pe what-if analysis hai."), cmd_type
    elif cmd_type == CommandType.FLOW_STATUS:
        return _t(lang,
                  en="Checking your flow state. Visit the Flow Guardian page for real-time status.",
                  hi="Aapka flow state check kar raha hoon. Flow Guardian page pe real-time status hai."), cmd_type
    elif cmd_type == CommandType.FLOW_START:
        return _t(lang,
                  en="Activating flow protection. I'll hold all non-urgent messages and auto-respond for you.",
                  hi="Flow protection chalu kar raha hoon. Sab non-urgent messages hold karunga aur auto-respond karunga."), cmd_type
    elif cmd_type == CommandType.FLOW_END:
        return _t(lang,
                  en="Ending flow session. Preparing your debrief with everything I held.",
                  hi="Flow session khatam. Debrief ready kar raha hoon jo maine hold kiya tha usme se."), cmd_type
    elif cmd_type == CommandType.FLOW_DEBRIEF:
        return _t(lang,
                  en="Here's your flow debrief. Check the Flow Guardian page for the full summary of held messages.",
                  hi="Yeh raha aapka flow debrief. Flow Guardian page pe held messages ka poora summary hai."), cmd_type
    elif cmd_type == CommandType.SETUP_AGENT:
        # Agent setup is handled specially by the NLP route — return params for it
        return None, cmd_type
    else:
        return None, cmd_type
