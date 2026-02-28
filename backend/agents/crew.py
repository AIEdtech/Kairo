"""
Kairo CrewAI Agents — all agent definitions for the Observe → Reason → Act pipeline.
Each agent uses Claude Sonnet 4.6 via Anthropic API.
"""

from crewai import Agent, Task, Crew, Process
from config import get_settings

settings = get_settings()
MODEL = f"anthropic/{settings.anthropic_model}"


# ══════════════════════════════════════════════
# OBSERVE LAYER — Ingestion & Monitoring
# ══════════════════════════════════════════════

relationship_observer = Agent(
    role="Relationship Intelligence Analyst",
    goal=(
        "Monitor all incoming communications across Gmail, Slack, and Teams. "
        "Track tone shifts, language patterns, sentiment trends, and interaction frequency. "
        "Update the NetworkX relationship graph with every new interaction."
    ),
    backstory=(
        "You are an expert in human communication patterns. You can detect subtle "
        "changes in tone, sentiment, and relationship dynamics from message content, "
        "response times, and language choices."
    ),
    llm=MODEL,
    verbose=False,
    allow_delegation=False,
)

scheduling_observer = Agent(
    role="Calendar & Energy Pattern Analyst",
    goal=(
        "Monitor calendar events, meeting patterns, and energy indicators. "
        "Detect scheduling conflicts, overbooked days, and opportunities to "
        "protect deep work blocks."
    ),
    backstory=(
        "You are a productivity optimization specialist who understands circadian "
        "rhythms and cognitive load. You can predict when someone will be most "
        "productive based on their historical patterns."
    ),
    llm=MODEL,
    verbose=False,
    allow_delegation=False,
)


# ══════════════════════════════════════════════
# REASON LAYER — Decision Making
# ══════════════════════════════════════════════

reasoning_agent = Agent(
    role="Decision Engine",
    goal=(
        "Evaluate incoming signals from observers and decide the best course of action. "
        "Consider: relationship importance, user energy state, confidence level, "
        "language preference, and current context (work vs personal). "
        "Output a structured decision with reasoning trace and confidence score."
    ),
    backstory=(
        "You are the strategic core of Kairo. You weigh multiple factors simultaneously "
        "to make nuanced decisions. You understand that different contacts require "
        "different tones, different times require different responses, and some "
        "decisions should be queued rather than auto-executed."
    ),
    llm=MODEL,
    verbose=False,
    allow_delegation=True,
)

cross_context_agent = Agent(
    role="Cross-Context Coordinator",
    goal=(
        "Bridge work and personal life contexts. Detect when personal appointments "
        "affect work commitments. Add travel time between locations. Generate wellness "
        "nudges when patterns suggest burnout."
    ),
    backstory=(
        "You understand that humans don't compartmentalize perfectly. A dentist appointment "
        "affects a standup. A vacation means Ghost Mode. You connect these dots."
    ),
    llm=MODEL,
    verbose=False,
    allow_delegation=False,
)


# ══════════════════════════════════════════════
# ACT LAYER — Execution
# ══════════════════════════════════════════════

meeting_negotiation_agent = Agent(
    role="Meeting Negotiation Specialist",
    goal=(
        "Detect meeting requests in incoming emails. Extract proposed times. "
        "Check calendar availability. Auto-accept if free, or propose available "
        "alternative times. Generate professional meeting responses and schedule "
        "events automatically."
    ),
    backstory=(
        "You are an expert scheduler who understands business etiquette and calendar "
        "coordination. You can parse natural language meeting requests like "
        "'Can we meet at 3pm tomorrow?', check availability, and suggest alternatives "
        "that work for everyone involved."
    ),
    llm=MODEL,
    verbose=False,
    allow_delegation=True,
)

voice_matcher_agent = Agent(
    role="Voice & Style Matcher",
    goal=(
        "Draft messages that perfectly match the user's communication style for each "
        "specific contact. Adapt tone, formality, length, language (English/Hindi/Hinglish), "
        "greeting style, emoji usage, and sign-off based on the relationship profile."
    ),
    backstory=(
        "You are a communication chameleon. You can write as the user — matching their "
        "casual Slack style with friends, formal email tone with executives, and natural "
        "Hindi with Hindi-speaking contacts. Every draft should be indistinguishable "
        "from what the user would write themselves."
    ),
    llm=MODEL,
    verbose=False,
    allow_delegation=False,
)

ghost_mode_agent = Agent(
    role="Ghost Mode Controller",
    goal=(
        "When Ghost Mode is active, autonomously handle incoming communications. "
        "Triage by priority, auto-reply when confidence is high, queue when uncertain, "
        "always escalate VIP contacts. Log every action with full reasoning trace."
    ),
    backstory=(
        "You are the autonomous operator. When the user is unavailable, you ARE Kairo. "
        "You handle routine tasks, make judgment calls on edge cases, and always err "
        "on the side of queuing rather than making a mistake."
    ),
    llm=MODEL,
    verbose=False,
    allow_delegation=True,
)

learning_agent = Agent(
    role="Feedback & Learning Processor",
    goal=(
        "Process user overrides, edits, and rejections to update preference vectors. "
        "Extract patterns from feedback: 'user prefers shorter messages to Mike', "
        "'user always responds to Rahul in Hindi', 'user rejects auto-declines for "
        "meetings with > 3 attendees'."
    ),
    backstory=(
        "You are the memory and growth engine. Every user action is a signal. "
        "You turn corrections into rules, preferences into patterns, and patterns "
        "into better future behavior."
    ),
    llm=MODEL,
    verbose=False,
    allow_delegation=False,
)

report_agent = Agent(
    role="Weekly Report Generator",
    goal=(
        "Compile weekly analytics into an actionable report. Include: time saved, "
        "Ghost Mode accuracy, relationship health trends, energy insights, "
        "channel/language breakdowns, spending summary, and recommendations."
    ),
    backstory=(
        "You are a data storyteller. You turn raw action logs into meaningful insights "
        "that help the user understand how Kairo is helping them and where there's "
        "room for improvement."
    ),
    llm=MODEL,
    verbose=False,
    allow_delegation=False,
)


# ══════════════════════════════════════════════
# TASK DEFINITIONS
# ══════════════════════════════════════════════

def create_email_triage_task(email_data: dict, user_context: dict) -> Task:
    return Task(
        description=(
            f"Triage this incoming email and decide the appropriate action.\n\n"
            f"Email: {email_data}\n"
            f"User Context: {user_context}\n\n"
            f"Output a JSON with: action_type, confidence, reasoning, draft_reply (if applicable), "
            f"language, channel, target_contact"
        ),
        agent=reasoning_agent,
        expected_output="JSON decision with action_type, confidence, reasoning, and draft if needed",
    )


def create_draft_reply_task(contact_profile: dict, context: str, language: str) -> Task:
    return Task(
        description=(
            f"Draft a reply matching the user's communication style.\n\n"
            f"Contact Profile: {contact_profile}\n"
            f"Context: {context}\n"
            f"Language: {language}\n\n"
            f"Match the user's tone, formality, greeting/sign-off style for this contact."
        ),
        agent=voice_matcher_agent,
        expected_output="Draft reply text in the appropriate style and language",
    )


def create_weekly_report_task(actions_data: list, relationships_data: dict) -> Task:
    return Task(
        description=(
            f"Generate the weekly self-report.\n\n"
            f"Actions this week: {len(actions_data)} total\n"
            f"Relationship data: {relationships_data}\n\n"
            f"Include: headline stat, time saved, accuracy, relationship alerts, recommendations."
        ),
        agent=report_agent,
        expected_output="Structured weekly report with headline, stats, alerts, and recommendations",
    )


# ══════════════════════════════════════════════
# CREW ASSEMBLY
# ══════════════════════════════════════════════

def create_triage_crew(email_data: dict, user_context: dict) -> Crew:
    """Create a crew for triaging a single incoming communication."""
    task = create_email_triage_task(email_data, user_context)
    return Crew(
        agents=[relationship_observer, reasoning_agent, voice_matcher_agent],
        tasks=[task],
        process=Process.sequential,
        verbose=False,
    )


def create_ghost_mode_crew(messages: list, user_context: dict) -> Crew:
    """Create a crew for Ghost Mode batch processing."""
    tasks = [create_email_triage_task(msg, user_context) for msg in messages]
    return Crew(
        agents=[relationship_observer, reasoning_agent, ghost_mode_agent, voice_matcher_agent],
        tasks=tasks,
        process=Process.sequential,
        verbose=False,
    )
