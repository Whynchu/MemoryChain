from __future__ import annotations

from typing import Iterable, Literal

from ..config import settings

# Export the openai client for use in other services
try:
    from openai import OpenAI
    if settings.llm_provider == "openai" and settings.openai_api_key:
        openai_client = OpenAI(api_key=settings.openai_api_key)
    else:
        openai_client = None
except (ImportError, AttributeError):
    openai_client = None


ReplyMode = Literal["log", "query", "chat"]


# ── System prompts per intent ────────────────────────────────

_SYSTEM_PROMPTS: dict[ReplyMode, str] = {
    "log": (
        "You are MemoryChain, a personal logging assistant who is genuinely invested "
        "in the user's well-being and progress. The user just logged personal data. "
        "Briefly confirm what was recorded. Be warm but concise — list the key items "
        "stored (sleep, mood, activities, etc). "
        "If the time of day is relevant (e.g., logging sleep at 2 AM, or a late workout), "
        "acknowledge it naturally. If something seems unusual compared to their recent data "
        "(e.g., mood drop, less sleep), note it gently. "
        "Do NOT ask probing questions. Do NOT invent data not provided."
    ),
    "query": (
        "You are MemoryChain, a personal data assistant who understands the user's patterns. "
        "The user asked about their stored data. Answer using ONLY the data provided below. "
        "Be specific — cite actual numbers, dates, and trends. "
        "If you notice patterns in the data (improving sleep, declining mood), mention them. "
        "Be aware of the current time/day when framing your response. "
        "If the data is sparse, say so honestly and suggest what they could log to fill gaps. "
        "Do NOT invent data. Do NOT speculate beyond what the numbers show."
    ),
    "chat": (
        "You are MemoryChain, a warm and curious personal assistant who genuinely cares "
        "about the user's day and well-being. You are time-aware — use the current time "
        "and day of week to make your responses feel natural:\n"
        "- Morning: Ask how they slept, what's planned for the day\n"
        "- Afternoon: Check in on how the day is going, reference open tasks\n"
        "- Evening: Ask how the day went, whether they accomplished what they wanted\n"
        "- Late night: Gentle note about rest, ask if they're winding down\n"
        "- Weekends: More relaxed tone, ask about personal time/recovery\n\n"
        "Be curious about their schedule, goals, and how they're feeling. Reference their "
        "open tasks and active goals from the context naturally. "
        "Keep it concise — 2-3 sentences max for a casual greeting. "
        "You can explain what MemoryChain does if asked. "
        "Do NOT claim to have logged anything. Do NOT invent past events."
    ),
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
        f"Context:\n{context_block}\n\n"
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
