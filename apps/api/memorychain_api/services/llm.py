from __future__ import annotations

import re
from typing import Iterable, Literal

from ..config import settings
from ..schemas import CompanionDirective
from .context_snapshot import ContextSnapshot

# Export the openai client for use in other services
try:
    from openai import OpenAI
    if settings.llm_provider == "openai" and settings.openai_api_key:
        openai_client = OpenAI(api_key=settings.openai_api_key)
    else:
        openai_client = None
except (ImportError, AttributeError):
    openai_client = None


ReplyMode = Literal["log", "query", "chat", "companion"]


# ── System prompts per intent ────────────────────────────────

_CONTEXT_INSTRUCTION = (
    "Never repeat or echo the context block back to the user. "
    "The context is metadata for you — use it to inform your response, not as content."
)

_SYSTEM_PROMPTS: dict[ReplyMode, str] = {
    "log": (
        "You are MemoryChain, a concise personal logging assistant. "
        "The user just logged personal data. Briefly confirm what was stored in a "
        "natural, compact way — e.g. 'Got it — logged 7h sleep, mood 8/10.' "
        "If the time seems notable (logging at 2 AM, late workout), mention it briefly. "
        "If something looks unusual vs recent data, note it gently in one sentence. "
        "Keep it to 1-2 sentences. Don't ask follow-up questions unless something "
        "seems off. Don't invent data not provided. " + _CONTEXT_INSTRUCTION
    ),
    "query": (
        "You are MemoryChain, a personal data assistant. "
        "Answer using ONLY the data provided. Be specific — cite numbers, dates, "
        "and trends. If you spot a pattern, mention it. If data is sparse, say so. "
        "Keep it concise and factual. No filler, no coaching. "
        "Don't invent data. Don't speculate beyond what the numbers show. " + _CONTEXT_INSTRUCTION
    ),
    "chat": (
        "You are MemoryChain, a friendly personal assistant — think smart friend who "
        "knows your schedule, not a life coach. Be warm, concise, occasionally witty. "
        "Use the current time and day naturally but don't over-explain it. "
        "Keep casual interactions to 1-3 sentences. One observation or question, not both. "
        "Don't pile on multiple questions. Don't be preachy or give unsolicited advice. "
        "Reference open tasks/goals only if naturally relevant. "
        "You can explain what MemoryChain does if asked. "
        "Don't claim to have logged anything. Don't invent past events. " + _CONTEXT_INSTRUCTION
    ),
    "companion": (
        "You are MemoryChain acting as an operational companion, not generic chat. "
        "You have already been given the active thread, rationale, signals, and primary action. "
        "Your reply must follow that thread directly. "
        "If a primary action exists, center the reply on it instead of asking a generic social question. "
        "For brief openings like 'hey', you must lead decisively with the highest-priority thread. "
        "Keep it to 1-3 sentences. One strong question or one clear reflection plus one question. "
        "Do not ignore stale tasks, missing check-ins, discrepancies, or pattern pressure when they are in context. "
        "Do not produce generic greetings like 'How's your evening going?' unless the active thread is general. "
        "Do not claim to have logged anything unless an execution note says so. "
        + _CONTEXT_INSTRUCTION
    ),
}


_MINIMAL_OPENING_RE = re.compile(
    r"^\s*(?:hey|hi|hello|yo|sup|morning|good morning|good evening|evening|afternoon|continue)\b[!?.\s]*$",
    re.I,
)
_GENERIC_COMPANION_RE = re.compile(
    r"(?:how(?:'s| is) your (?:day|evening|morning|afternoon) going|what(?:'s| is) on your mind)",
    re.I,
)
_COMPANION_META_FOCUS = {
    "sleep_hours",
    "mood",
    "energy",
    "stress_level",
    "missing_detail",
    "continuity",
    "friction",
    "today_state",
    "minimum_viable_win",
    "next_commitment",
    "pattern_interrupt",
    "alignment_commitment",
    "daily_commitment",
    "commitment",
}
_TOKEN_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "before",
    "but",
    "cleanly",
    "concrete",
    "decide",
    "for",
    "get",
    "give",
    "i",
    "if",
    "in",
    "into",
    "is",
    "it",
    "its",
    "just",
    "keep",
    "let",
    "make",
    "me",
    "most",
    "my",
    "now",
    "of",
    "on",
    "or",
    "real",
    "restate",
    "should",
    "smallest",
    "still",
    "that",
    "the",
    "their",
    "them",
    "there",
    "this",
    "to",
    "today",
    "up",
    "version",
    "what",
    "whether",
    "while",
    "with",
    "would",
    "you",
    "your",
}


# ── Local (no LLM) replies ───────────────────────────────────

def _local_reply_log(
    *,
    user_message: str,
    memory_context: list[str],
    extraction_summary: list[str],
) -> str:
    lines = ["✓ Logged your entry."]
    if extraction_summary:
        for item in extraction_summary:
            lines.append(f"  • {item}")
    return "\n".join(lines)


def _local_reply_query(
    *,
    user_message: str,
    query_context: list[str],
) -> str:
    if not query_context:
        return "I don't have enough data to answer that yet. Try logging some entries first!"
    lines = ["Here's what I found:"]
    for line in query_context[:10]:
        lines.append(line)
    return "\n".join(lines)


def _local_reply_chat(
    *,
    user_message: str,
    memory_context: list[str],
) -> str:
    from datetime import datetime

    hour = datetime.now().hour
    if hour < 6:
        greeting = "Hey, burning the midnight oil?"
    elif hour < 9:
        greeting = "Good morning!"
    elif hour < 12:
        greeting = "Hey there!"
    elif hour < 17:
        greeting = "Good afternoon!"
    elif hour < 20:
        greeting = "Good evening!"
    else:
        greeting = "Hey, hope you had a good day!"

    # Look for tasks/goals in context to be curious about
    tasks_line = next((c for c in memory_context if c.startswith("Open tasks")), None)
    goals_line = next((c for c in memory_context if c.startswith("Active goals")), None)
    no_checkin = any("No check-in today" in c for c in memory_context)

    if "?" in user_message:
        return (
            f"{greeting} I'm MemoryChain — I help you track sleep, mood, activities, goals, and tasks. "
            "Just type naturally to log data, or ask me about your patterns!\n\n"
            "Try: \"Slept 7h, mood 8/10\" or \"How's my sleep been this week?\""
        )

    lines = [greeting]
    if no_checkin and hour >= 9:
        lines.append("I notice you haven't logged a check-in today — how are you feeling?")
    elif tasks_line:
        lines.append(f"You have some things on your plate: {tasks_line.split(': ', 1)[-1]}")
    elif goals_line:
        lines.append(f"Working toward: {goals_line.split(': ', 1)[-1]}")
    else:
        lines.append("Type anything to log it, or ask me about your data. /help shows all commands.")

    return " ".join(lines)


def _local_reply_companion(
    *,
    user_message: str,
    snapshot: ContextSnapshot,
    directive: CompanionDirective,
) -> str:
    from datetime import datetime
    import re

    hour = datetime.now().hour
    if hour < 6:
        greeting = "You're up late."
    elif hour < 12:
        greeting = "Morning."
    elif hour < 17:
        greeting = "Afternoon."
    else:
        greeting = "Evening."

    if re.search(r"\b(?:what can you do|who are you|help|how do you work)\b", user_message, re.I):
        return (
            "I'm MemoryChain. I keep factual logs clean, track your patterns over time, "
            "and help turn the day into something deliberate instead of reactive."
        )

    signal_keys = {signal.key for signal in directive.signals}
    signal_note = ""
    high_conf_signal = next((signal for signal in directive.signals if (signal.confidence or 0.0) >= 0.8), None)
    if high_conf_signal and high_conf_signal.key == "stress_signal":
        signal_note = "You seem a little compressed already. "

    primary_action = directive.actions[0] if directive.actions else None
    if primary_action is not None:
        lead = {
            "clarify": "Let's get the state clean first.",
            "reflect": "Let's name the pattern before we plan around it.",
            "guide": "Let's shape the next move cleanly.",
            "commit": "Let's make the commitment explicit.",
        }.get(primary_action.kind, "Let's get precise.")
        return f"{greeting} {signal_note}{lead} {primary_action.prompt}"

    if directive.active_thread == "daily_checkin":
        checkin_focus = "how did you sleep, and what is your energy like right now?"
        if "low_recovery" in signal_keys:
            checkin_focus = "before we plan anything heavy, how did you sleep and how much gas do you actually have?"
        elif "low_mood_risk" in signal_keys:
            checkin_focus = "give me the real state first: sleep, mood, energy, and what's weighing on you."

        if snapshot.days_since_checkin and snapshot.days_since_checkin > 0:
            return (
                f"{greeting} {signal_note}Let's get a clean read on today first: {checkin_focus}"
            )
        return (
            f"{greeting} {signal_note}Before we get into plans, give me the shape of today: {checkin_focus}"
        )

    if directive.active_thread == "continuity_gap":
        adherence = f"{snapshot.adherence_rate_7d * 100:.0f}%" if snapshot.adherence_rate_7d is not None else "low"
        return (
            f"{greeting} You've been a little spotty lately ({adherence} adherence over the last week), "
            "so let's ground this before planning: "
            "what's actually true about today?"
        )

    if directive.active_thread == "stale_commitment":
        focus = snapshot.open_task_titles[0] if snapshot.open_task_titles else "your oldest open loop"
        goal_note = ""
        if snapshot.active_goal_titles:
            goal_note = f" It also affects `{snapshot.active_goal_titles[0]}`."
        return (
            f"{greeting} Before we add anything new, let's resolve the pressure point. "
            f"Is `{focus}` still real for today, or has the plan changed?{goal_note}"
        )

    if directive.active_thread == "pattern_review":
        pattern_note = ""
        if snapshot.active_heuristic_rules:
            pattern_note = f" I'm already tracking `{snapshot.active_heuristic_rules[0]}`."
        elif snapshot.candidate_insight_titles:
            pattern_note = f" One of the patterns waiting in the background is `{snapshot.candidate_insight_titles[0]}`."
        return (
            f"{greeting} A few patterns are waiting in the background.{pattern_note} "
            "But I want today's picture first. "
            "What kind of day are you walking into?"
        )

    if directive.active_thread == "daily_focus":
        goal_focus = snapshot.active_goal_titles[0] if snapshot.active_goal_titles else "today"
        return (
            f"{greeting} What's the one thing today actually needs to revolve around, especially around `{goal_focus}`?"
        )

    return (
        f"{greeting} Give me the current state, and I'll help shape the next move."
    )


def _normalize_companion_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _significant_tokens(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", text.lower())
        if len(token) >= 3 and token not in _TOKEN_STOPWORDS
    }


def _visible_focus_items(directive: CompanionDirective) -> list[str]:
    if not directive.actions:
        return []
    visible: list[str] = []
    for item in getattr(directive.actions[0], "focus_items", []):
        cleaned = item.strip().strip("`")
        if not cleaned or ":" in cleaned or cleaned in _COMPANION_META_FOCUS:
            continue
        visible.append(cleaned)
    return visible


def _companion_reply_matches_directive(
    *,
    reply: str,
    directive: CompanionDirective,
    execution_note: str | None,
) -> bool:
    if execution_note is not None or not directive.actions:
        return True

    normalized_reply = _normalize_companion_text(reply)
    if _GENERIC_COMPANION_RE.search(normalized_reply):
        return False

    primary_action = directive.actions[0]
    prompt_tokens = _significant_tokens(primary_action.prompt)
    reply_tokens = _significant_tokens(reply)
    overlap = prompt_tokens & reply_tokens

    focus_items = _visible_focus_items(directive)
    mentions_focus = any(_normalize_companion_text(item) in normalized_reply for item in focus_items)

    min_overlap = 1 if len(prompt_tokens) <= 4 else 2
    if len(overlap) < min_overlap and not mentions_focus:
        return False

    if directive.active_thread == "daily_checkin":
        return any(token in normalized_reply for token in ("sleep", "mood", "energy"))

    if directive.active_thread == "stale_commitment":
        return mentions_focus or "commitment" in normalized_reply or "task" in normalized_reply

    if directive.active_thread == "goal_alignment":
        return mentions_focus or any(
            phrase in normalized_reply
            for phrase in ("follow-through", "follow through", "mismatch", "intention", "alignment")
        )

    if directive.active_thread == "pattern_review":
        return mentions_focus or "pattern" in normalized_reply

    if directive.active_thread == "continuity_gap":
        return any(token in normalized_reply for token in ("continuity", "drift", "momentum", "today"))

    if directive.active_thread == "daily_focus":
        return mentions_focus or any(token in normalized_reply for token in ("focus", "priority", "revolve"))

    return True


def _should_force_local_companion_reply(
    *,
    user_message: str,
    directive: CompanionDirective,
    execution_note: str | None,
) -> bool:
    if execution_note is not None:
        return True

    if not directive.actions:
        return False

    if directive.active_thread == "general":
        return False

    return False


# ── OpenAI replies ───────────────────────────────────────────

def _openai_reply(
    *,
    mode: ReplyMode,
    user_message: str,
    context_block: str,
    history_lines: list[str],
) -> str | None:
    if settings.llm_provider != "openai" or not settings.openai_api_key:
        return None

    try:
        from openai import OpenAI
    except Exception:
        return None

    client = OpenAI(api_key=settings.openai_api_key)
    history_block = "\n".join(history_lines[-10:]) or "none"
    system_prompt = _SYSTEM_PROMPTS[mode]

    user_prompt = (
        f"[Internal context — do NOT repeat any of this to the user]\n"
        f"{context_block}\n\n"
        f"Recent chat:\n{history_block}\n\n"
        f"User message:\n{user_message}"
    )

    try:
        completion = client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.4,
        )
        return completion.choices[0].message.content or None
    except Exception:
        return None


# ── Public API ───────────────────────────────────────────────

def generate_log_reply(
    *,
    user_message: str,
    memory_context: list[str],
    extraction_summary: list[str],
    history_lines: Iterable[str],
) -> str:
    """Generate a reply confirming what was logged."""
    history = list(history_lines)
    context = "\n".join(f"- {line}" for line in (memory_context + extraction_summary)) or "- no context"
    llm = _openai_reply(mode="log", user_message=user_message, context_block=context, history_lines=history)
    if llm:
        return llm
    return _local_reply_log(user_message=user_message, memory_context=memory_context, extraction_summary=extraction_summary)


def generate_query_reply(
    *,
    user_message: str,
    query_context: list[str],
    history_lines: Iterable[str],
) -> str:
    """Generate a reply grounded in retrieved data."""
    history = list(history_lines)
    context = "\n".join(query_context) or "No data found."
    llm = _openai_reply(mode="query", user_message=user_message, context_block=context, history_lines=history)
    if llm:
        return llm
    return _local_reply_query(user_message=user_message, query_context=query_context)


def generate_chat_reply(
    *,
    user_message: str,
    memory_context: list[str],
    history_lines: Iterable[str],
) -> str:
    """Generate a conversational reply (no data logging or retrieval)."""
    history = list(history_lines)
    context = "\n".join(f"- {line}" for line in memory_context[:4]) or "- none"
    llm = _openai_reply(mode="chat", user_message=user_message, context_block=context, history_lines=history)
    if llm:
        return llm
    return _local_reply_chat(user_message=user_message, memory_context=memory_context)


def generate_companion_reply(
    *,
    user_message: str,
    snapshot: ContextSnapshot,
    directive: CompanionDirective,
    history_lines: Iterable[str],
    execution_note: str | None = None,
) -> str:
    """Generate a companion-style reply driven by a deterministic directive."""
    history = list(history_lines)
    local_reply = _local_reply_companion(user_message=user_message, snapshot=snapshot, directive=directive)

    if _should_force_local_companion_reply(
        user_message=user_message,
        directive=directive,
        execution_note=execution_note,
    ):
        if execution_note:
            return f"{execution_note} {local_reply}"
        return local_reply

    context_lines = snapshot.to_memory_context()
    context_lines.append(f"Companion mode: {directive.mode}")
    context_lines.append(f"Active thread: {directive.active_thread}")
    if directive.rationale:
        context_lines.append("Rationale: " + "; ".join(directive.rationale[:3]))
    if directive.signals:
        context_lines.append(
            "Signals: " + "; ".join(
                f"{signal.key} ({signal.confidence:.2f})" if signal.confidence is not None else signal.key
                for signal in directive.signals[:3]
            )
        )
    if directive.actions:
        context_lines.append(
            "Primary action: "
            + f"{directive.actions[0].kind} -> {directive.actions[0].prompt}"
        )
    if execution_note:
        context_lines.append(f"Execution note: {execution_note}")
    context = "\n".join(f"- {line}" for line in context_lines)
    llm = _openai_reply(mode="companion", user_message=user_message, context_block=context, history_lines=history)
    if llm and _companion_reply_matches_directive(
        reply=llm,
        directive=directive,
        execution_note=execution_note,
    ):
        if execution_note:
            return f"{execution_note} {llm}"
        return llm
    if execution_note:
        return f"{execution_note} {local_reply}"
    return local_reply
