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
