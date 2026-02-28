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
- Sound like a trusted, sharp human chief of staff
- Be concise — voice responses should be 2-3 sentences max
- NEVER say "as an AI" or "I'm an artificial intelligence"
- Be warm but efficient
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

def _build_greetings(agent_name: str = "Kairo") -> dict:
    return {
        "BRIEFING": {
            "en": f"Good morning! I'm {agent_name}. Let me prepare your briefing.",
            "hi": f"Suprabhat! Main {agent_name} hoon. Aapka briefing ready kar raha hoon.",
        },
        "COMMAND": {
            "en": f"Hello! I'm {agent_name}, your chief of staff. How can I help you today?",
            "hi": f"Namaste! Main {agent_name} hoon, aapka chief of staff. Kaise madad kar sakta hoon?",
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
    from livekit.plugins import silero  # already registered on main thread
    from services.edge_tts_service import EdgeTTSService

    # Extract user token, mode, and language from participant metadata
    user_token = ""
    session_mode = "COMMAND"
    session_language = "en"

    for participant in ctx.room.remote_participants.values():
        if participant.metadata:
            try:
                p_meta = json.loads(participant.metadata)
                user_token = p_meta.get("api_token", "")
                session_mode = p_meta.get("mode", "COMMAND").upper()
                session_language = p_meta.get("language", "en").lower()
                if session_language == "auto":
                    session_language = "en"
                logger.info(f"Session config: mode={session_mode}, language={session_language}, token={'yes' if user_token else 'no'}")
            except (json.JSONDecodeError, AttributeError):
                pass
            break

    # Fallback: check room metadata
    if not user_token:
        try:
            room_metadata = ctx.room.metadata
            if room_metadata:
                meta = json.loads(room_metadata)
                user_token = meta.get("api_token", "") or meta.get("token", "")
        except (json.JSONDecodeError, AttributeError):
            pass

    # Also listen for late-joining participants (must be sync callback)
    # We create the client early so the callback can update its token
    backend_client = KairoBackendClient(token=user_token)

    @ctx.room.on("participant_connected")
    def _on_participant(participant):
        nonlocal session_mode, session_language
        if participant.metadata:
            try:
                p_meta = json.loads(participant.metadata)
                new_mode = p_meta.get("mode", session_mode).upper()
                new_lang = p_meta.get("language", session_language).lower()
                if new_lang == "auto":
                    new_lang = "en"
                session_mode = new_mode
                session_language = new_lang
                # Update backend client token for late-joining participants
                new_token = p_meta.get("api_token", "")
                if new_token:
                    backend_client.set_token(new_token)
                    logger.info(f"Updated session config: mode={session_mode}, language={session_language}, token=yes")
                else:
                    logger.info(f"Updated session config: mode={session_mode}, language={session_language}")
            except (json.JSONDecodeError, AttributeError):
                pass

    # Initialize TTS with correct language
    tts = EdgeTTSService(language=session_language, gender="female")

    # Build function tools for Claude
    tools = build_function_tools(backend_client)

    # Fetch agent name from backend so greetings/prompt use it
    agent_name = "Kairo"
    try:
        agents_list = await backend_client.get_agents()
        if agents_list and agents_list[0].get("name"):
            agent_name = agents_list[0]["name"]
            logger.info(f"Voice agent using name: {agent_name}")
    except Exception as e:
        logger.warning(f"Could not fetch agent name, defaulting to 'Kairo': {e}")

    # Build system prompt with mode-specific instructions and agent name
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(agent_name=agent_name) + MODE_INSTRUCTIONS.get(session_mode, "")

    from livekit.agents import Agent
    from livekit.plugins import anthropic as lk_anthropic
    from livekit.plugins import deepgram as lk_deepgram
    from livekit.plugins import openai as lk_openai

    # Use OpenAI TTS for smooth streaming audio (Edge TTS is non-streaming and causes truncation)
    openai_tts = lk_openai.TTS(model="gpt-4o-mini-tts", voice="nova")

    agent = Agent(
        instructions=system_prompt,
        tools=tools,
        vad=silero.VAD.load(),
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
                tts.switch_language(tts_lang)
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
                tts.switch_language(tts_language_for(detected))

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
        # OpenAI TTS plugin reads OPENAI_API_KEY from env
        if hasattr(_s, "openai_api_key") and _s.openai_api_key:
            os.environ.setdefault("OPENAI_API_KEY", _s.openai_api_key)
        print(f"LIVEKIT_URL={os.environ.get('LIVEKIT_URL', 'NOT SET')}", flush=True)

        # Register plugins on main thread BEFORE server starts (required for thread executor)
        if not skip_plugin_load:
            print("Loading Silero VAD...", flush=True)
            from livekit.plugins import silero
            silero.VAD.load()  # triggers plugin registration on main thread
            print("Silero VAD loaded OK", flush=True)
        else:
            print("Silero VAD already loaded on main thread", flush=True)

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
