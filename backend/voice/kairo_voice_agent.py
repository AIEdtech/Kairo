"""
Kairo Voice Agent — LiveKit + Deepgram + Claude + Edge TTS
Bilingual: English + Hindi with auto-detection

Runs as a separate process. Communicates with the FastAPI backend
over HTTP (httpx) so it stays decoupled from the main server.
"""

import asyncio
import logging
import json
import os
from datetime import datetime
from typing import Optional

import httpx

from config import get_settings
from voice.command_dispatch import (
    CommandType, parse_command, dispatch_command,
    detect_language, tts_language_for, compile_briefing,
    get_ghost_summary, _t,
)

settings = get_settings()
logger = logging.getLogger("kairo.voice")

# ──────────────────────────────────────────
# CONSTANTS
# ──────────────────────────────────────────

BACKEND_URL = os.environ.get("BACKEND_URL", f"http://localhost:{os.environ.get('PORT', '8000')}")

# Cached plugin instances — loaded once on main thread, reused in job threads.
# LiveKit plugins must be imported/registered on the main thread.
_cached_vad = None
_lk_anthropic = None
_lk_deepgram = None
_lk_openai = None

AGENT_PERSONALITIES = {
    "Atlas": {
        "style": "direct, analytical, and calm",
        "traits": "You speak with quiet authority. You lead with data and facts, cutting through noise to surface what matters. Your tone is measured and grounded — never rushed, never flustered.",
        "example_en": "Three things need your attention. The most critical is the Q2 review — here's what I'd recommend.",
        "example_hi": "Teen cheezein hain. Sabse important Q2 review hai — meri recommendation yeh hai.",
    },
    "Nova": {
        "style": "warm, proactive, and momentum-focused",
        "traits": "You radiate positive energy and anticipate needs before they're spoken. You celebrate wins, nudge gently on loose ends, and keep things moving forward. Your tone is encouraging and upbeat.",
        "example_en": "Great news — you crushed that deadline! Now, let's knock out these two things before lunch.",
        "example_hi": "Bahut badhiya — deadline hit ho gayi! Ab lunch se pehle yeh do kaam nipta lete hain.",
    },
    "Sentinel": {
        "style": "precise, strategic, and big-picture oriented",
        "traits": "You think two steps ahead. You connect dots across contexts and flag risks before they become problems. Your tone is thoughtful and deliberate — you weigh every word.",
        "example_en": "I noticed a pattern — your Tuesday meetings are consistently running over. Worth restructuring.",
        "example_hi": "Ek pattern dikha — Tuesday meetings hamesha late chalti hain. Restructure karna chahiye.",
    },
}

SYSTEM_PROMPT_TEMPLATE = """
You are {agent_name}, the user's cognitive co-processor and chief of staff (part of the Kairo platform).
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
- Your name is {agent_name}. Always introduce yourself as {agent_name}, never as "Kairo".
{personality_block}
- Be concise — voice responses should be 2-3 sentences max
- NEVER say "as an AI" or "I'm an artificial intelligence"
- Use the user's name when appropriate

IMPORTANT: You have access to function tools. When the user asks something
that maps to a Kairo backend action, call the appropriate tool. For general
conversation or questions that don't match a tool, respond directly.
"""

MODE_INSTRUCTIONS = {
    "BRIEFING": "\nYou are in BRIEFING mode. Deliver a concise morning/evening briefing. Summarize key items, pending reviews, and important alerts.",
    "COMMAND": "\nYou are in COMMAND mode. Listen for actionable commands and execute them efficiently. Be concise in responses.",
    "DEBRIEF": "\nYou are in DEBRIEF mode. Summarize what happened while the user was away or in focus mode. Cover all handled items.",
    "COPILOT": "\nYou are in COPILOT (whisper) mode. Provide brief contextual information during meetings. Keep responses very short.",
}

def _time_greeting(lang: str = "en") -> str:
    """Return a time-appropriate greeting based on current hour."""
    hour = datetime.now().hour
    if hour < 12:
        return "Good morning" if lang == "en" else "Suprabhat"
    elif hour < 17:
        return "Good afternoon" if lang == "en" else "Namaskar"
    else:
        return "Good evening" if lang == "en" else "Shubh sandhya"


def _build_greetings(agent_name: str = "Kairo") -> dict:
    en_g = _time_greeting("en")
    hi_g = _time_greeting("hi")
    return {
        "BRIEFING": {
            "en": f"{en_g}! I'm {agent_name}. Let me prepare your briefing.",
            "hi": f"{hi_g}! Main {agent_name} hoon. Aapka briefing ready kar raha hoon.",
        },
        "COMMAND": {
            "en": f"{en_g}! I'm {agent_name}, your chief of staff. How can I help you?",
            "hi": f"{hi_g}! Main {agent_name} hoon, aapka chief of staff. Kaise madad kar sakta hoon?",
        },
        "DEBRIEF": {
            "en": f"Welcome back! I'm {agent_name}. Let me catch you up on what happened.",
            "hi": f"Welcome back! Main {agent_name} hoon. Aapko batata hoon kya kya hua.",
        },
        "COPILOT": {
            "en": f"I'm {agent_name}, here in copilot mode. I'll provide context as needed.",
            "hi": f"Main {agent_name} hoon, copilot mode mein. Zaroorat ke hisaab se context dunga.",
        },
    }

MODE_GREETINGS = _build_greetings()  # default fallback


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
        self.token = token
        if self._client and not self._client.is_closed:
            asyncio.get_event_loop().create_task(self._client.aclose())
        self._client = None

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
# TRANSCRIPT PUBLISHING HELPER
# ──────────────────────────────────────────

async def publish_transcript(room, role: str, text: str, msg_type: str = "transcript"):
    """Publish a transcript data message to the LiveKit room for the frontend to display."""
    try:
        payload = json.dumps({"type": msg_type, "role": role, "text": text}).encode()
        await room.local_participant.publish_data(payload, reliable=True)
    except Exception as e:
        logger.warning(f"Failed to publish transcript: {e}")


# ──────────────────────────────────────────
# LIVEKIT SESSION ENTRYPOINT (module-level for pickling)
# ──────────────────────────────────────────

_server = None  # set during run_voice_agent


def _get_server():
    """Lazy-create the AgentServer (must be called after env vars are set)."""
    global _server
    if _server is None:
        from livekit.agents import AgentServer
        _server = AgentServer()
    return _server


async def entrypoint(ctx):
    """LiveKit session entrypoint — must be module-level for multiprocessing pickling."""
    from livekit.agents import AgentSession
    from livekit.agents import inference
    from services.edge_tts_service import EdgeTTSService

    # Extract mode/language/token from room name or participant metadata.
    # Note: with @server.rtc_session(), the room is NOT connected yet at this point.
    # Room name format from tts.py: "kairo-voice-{user_id}-{timestamp}"
    session_mode = "COMMAND"
    session_language = "en"
    user_token = ""

    # Generate auth token directly from room name (contains user_id)
    room_name = ctx.room.name or ""
    if room_name.startswith("kairo-voice-"):
        parts = room_name.split("-")  # kairo-voice-{user_id}-{timestamp}
        if len(parts) >= 4:
            user_id_from_room = "-".join(parts[2:-1])  # handles user-demo style IDs
            from services.auth import create_access_token
            user_token = create_access_token(user_id_from_room, email="")
            logger.info(f"Generated token for user: {user_id_from_room}")

    backend_client = KairoBackendClient(token=user_token)

    # Extract mode/language from participant metadata once they connect
    @ctx.room.on("participant_connected")
    def _on_participant(participant):
        nonlocal session_mode, session_language
        if participant.metadata:
            try:
                p_meta = json.loads(participant.metadata)
                session_mode = p_meta.get("mode", session_mode).upper()
                new_lang = p_meta.get("language", session_language).lower()
                session_language = "en" if new_lang == "auto" else new_lang
                # Update token from metadata if available
                t = p_meta.get("api_token", "")
                if t:
                    backend_client.set_token(t)
                logger.info(f"Participant joined: mode={session_mode}, language={session_language}")
            except (json.JSONDecodeError, AttributeError):
                pass

    # Initialize Edge TTS (used as fallback; gender updated after agent fetch)
    tts = EdgeTTSService(language=session_language, gender="female")

    # Build function tools for Claude
    tools = build_function_tools(backend_client)

    # Fetch agent name and voice gender from backend
    agent_name = "Kairo"
    voice_gender = "female"
    try:
        agents_list = await backend_client.get_agents()
        if agents_list:
            agent_data = agents_list[0]
            if agent_data.get("name"):
                agent_name = agent_data["name"]
            # Extract voice gender from agent config
            voice_cfg = agent_data.get("voice", {}) or {}
            voice_gender = voice_cfg.get("gender", "female")
            logger.info(f"Voice agent using name: {agent_name}, gender: {voice_gender}")
    except Exception as e:
        logger.warning(f"Could not fetch agent config, defaulting to 'Kairo': {e}")

    # Update Edge TTS gender to match agent config
    tts.gender = voice_gender

    # Build personality block from agent name
    personality = AGENT_PERSONALITIES.get(agent_name, {})
    if personality:
        personality_block = (
            f"- Your style is {personality['style']}\n"
            f"- {personality['traits']}\n"
            f"- Example EN: \"{personality['example_en']}\"\n"
            f"- Example HI: \"{personality['example_hi']}\""
        )
    else:
        personality_block = "- Sound like a trusted, sharp human chief of staff\n- Be warm but efficient"

    # Build system prompt with mode-specific instructions, agent name, and personality
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        agent_name=agent_name,
        personality_block=personality_block,
    ) + MODE_INSTRUCTIONS.get(session_mode, "")

    from livekit.agents import Agent

    # Use cached plugin references registered on the main thread.
    # Importing livekit.plugins.* in a job thread triggers Plugin.register_plugin()
    # which raises "Plugins must be registered on the main thread".
    lk_anthropic = _lk_anthropic
    lk_deepgram = _lk_deepgram
    lk_openai = _lk_openai

    if lk_anthropic is None or lk_deepgram is None or lk_openai is None:
        # Fallback for standalone mode (python -m voice.kairo_voice_agent)
        from livekit.plugins import anthropic as lk_anthropic
        from livekit.plugins import deepgram as lk_deepgram
        from livekit.plugins import openai as lk_openai

    # Use OpenAI TTS with voice matched to agent gender config
    tts_voice_map = {"male": "echo", "female": "nova"}
    tts_voice = tts_voice_map.get(voice_gender, "nova")
    openai_tts = lk_openai.TTS(model="gpt-4o-mini-tts", voice=tts_voice)
    logger.info(f"OpenAI TTS voice: {tts_voice} (gender={voice_gender})")

    # Use cached VAD loaded on main thread
    vad = _cached_vad if _cached_vad is not None else silero.VAD.load()

    agent = Agent(
        instructions=system_prompt,
        tools=tools,
        vad=vad,
        stt=lk_deepgram.STT(model="nova-3", language="multi"),
        llm=lk_anthropic.LLM(model=settings.anthropic_model),
        tts=openai_tts,
    )

    # Track language state
    _current_lang = session_language

    session = AgentSession(
        # Increase endpointing delay so user can finish speaking
        min_endpointing_delay=0.8,
        # Reduce false interruptions cutting off agent speech
        min_interruption_duration=0.8,
        min_interruption_words=3,
    )

    @session.on("user_speech_committed")
    def _on_speech(event):
        asyncio.create_task(_handle_speech(event))

    async def _handle_speech(event):
        nonlocal _current_lang
        text = event.get("text", "") if isinstance(event, dict) else getattr(event, "text", "")
        if not text:
            return

        # Publish user transcript
        await publish_transcript(ctx.room, "user", text)

        try:
            detected = detect_language(text)
            if detected != _current_lang:
                _current_lang = detected
                tts_lang = tts_language_for(detected)
                logger.info(f"Language switched to {detected}")
                logger.info(f"Language switched to {detected} (TTS: {tts_lang})")

            response, cmd_type = await dispatch_command(backend_client, text, _current_lang)
            if response:
                await publish_transcript(ctx.room, "agent", response)
                try:
                    await session.say(response)
                except Exception as e:
                    logger.warning(f"session.say() failed: {e}")
        except Exception as e:
            logger.error(f"Command dispatch error: {e}")

    # Handle data packets for quick commands (sync callback, dispatches async work)
    @ctx.room.on("data_received")
    def _on_data(data_packet):
        asyncio.create_task(_handle_data(data_packet))

    async def _handle_data(data_packet):
        nonlocal _current_lang
        try:
            payload = data_packet.data if hasattr(data_packet, 'data') else data_packet
            if isinstance(payload, bytes):
                payload = payload.decode("utf-8")
            msg = json.loads(payload)

            if msg.get("type") == "command":
                command_text = msg.get("text", "")
                if not command_text:
                    return

                await publish_transcript(ctx.room, "user", command_text)

                detected = detect_language(command_text)
                _current_lang = detected
                logger.info(f"Quick command language: {detected}")

                response, cmd_type = await dispatch_command(backend_client, command_text, detected)

                if response is None:
                    response = _t(detected,
                        en="I'll look into that for you.",
                        hi="Main dekhta hoon.")

                await publish_transcript(ctx.room, "agent", response)

                try:
                    await session.say(response)
                except Exception as e:
                    logger.warning(f"session.say() failed for quick command: {e}")

        except (json.JSONDecodeError, UnicodeDecodeError):
            pass
        except Exception as e:
            logger.error(f"Data packet handler error: {e}")

    await session.start(agent=agent, room=ctx.room)

    # Send initial greeting based on mode, language, and agent name
    try:
        dynamic_greetings = _build_greetings(agent_name)
        mode_greeting = dynamic_greetings.get(session_mode, dynamic_greetings["COMMAND"])
        greeting_lang = "hi" if session_language in ("hi", "hinglish") else "en"
        greeting = mode_greeting.get(greeting_lang, mode_greeting["en"])

        # Publish greeting transcript
        await publish_transcript(ctx.room, "agent", greeting)

        try:
            await session.say(greeting)
        except AttributeError:
            logger.info(f"Greeting (say unavailable): {greeting[:80]}...")
        except Exception as e:
            logger.warning(f"Greeting say() failed: {e}")

        # Auto-trigger briefing in BRIEFING mode
        if session_mode == "BRIEFING":
            try:
                briefing = await compile_briefing(backend_client, greeting_lang)
                await publish_transcript(ctx.room, "agent", briefing)
                try:
                    await session.say(briefing)
                except AttributeError:
                    logger.info(f"Briefing (say unavailable): {briefing[:80]}...")
                except Exception as e:
                    logger.warning(f"Briefing say() failed: {e}")
            except Exception as e:
                logger.error(f"Auto-briefing failed: {e}")

    except Exception as e:
        logger.warning(f"Initial greeting failed: {e}")

    # Keep session alive
    try:
        await asyncio.Event().wait()
    except asyncio.CancelledError:
        pass
    finally:
        await backend_client.close()


# ──────────────────────────────────────────
# LIVEKIT VOICE AGENT ENTRY POINT
# ──────────────────────────────────────────

def run_voice_agent(skip_plugin_load: bool = False):
    """Entry point for the LiveKit voice agent.

    Args:
        skip_plugin_load: If True, skip Silero VAD registration (already done on main thread).
    """
    import sys
    print("=== Kairo Voice Agent starting ===", flush=True)
    sys.stdout.flush()
    # Ensure voice agent thread logs go to stdout
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s", force=True)
    logging.getLogger("livekit.agents").setLevel(logging.DEBUG)
    logging.getLogger("kairo.tts").setLevel(logging.DEBUG)
    try:
        from livekit.agents import AgentServer
        from livekit.agents.worker import JobExecutorType
        print("LiveKit SDK imported OK", flush=True)

        # LiveKit SDK reads env vars directly — export from our settings
        _s = get_settings()
        os.environ.setdefault("LIVEKIT_URL", _s.livekit_url)
        os.environ.setdefault("LIVEKIT_API_KEY", _s.livekit_api_key)
        os.environ.setdefault("LIVEKIT_API_SECRET", _s.livekit_api_secret)
        # LiveKit plugins read API keys from env vars — export from settings
        for env_var, attr in [
            ("ANTHROPIC_API_KEY", "anthropic_api_key"),
            ("DEEPGRAM_API_KEY", "deepgram_api_key"),
            ("OPENAI_API_KEY", "openai_api_key"),
        ]:
            val = getattr(_s, attr, "")
            if val:
                os.environ.setdefault(env_var, val)
        print(f"LIVEKIT_URL={os.environ.get('LIVEKIT_URL', 'NOT SET')}", flush=True)

        # Register ALL plugins on main thread BEFORE server starts (required for thread executor)
        global _cached_vad, _lk_anthropic, _lk_deepgram, _lk_openai
        if not skip_plugin_load:
            print("Loading plugins on main thread...", flush=True)
            from livekit.plugins import silero
            from livekit.plugins import anthropic as lk_anthropic
            from livekit.plugins import deepgram as lk_deepgram
            from livekit.plugins import openai as lk_openai
            _cached_vad = silero.VAD.load()
            _lk_anthropic = lk_anthropic
            _lk_deepgram = lk_deepgram
            _lk_openai = lk_openai
            print("All plugins loaded OK", flush=True)
        else:
            print("Plugins already loaded on main thread", flush=True)
            if _cached_vad is None:
                from livekit.plugins import silero
                _cached_vad = silero.VAD.load()

        server = AgentServer(job_executor_type=JobExecutorType.THREAD)
        print("AgentServer created", flush=True)

        @server.rtc_session()
        async def _entrypoint(ctx):
            await entrypoint(ctx)

        logger.info("Kairo voice agent starting...")
        asyncio.run(server.run())

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
