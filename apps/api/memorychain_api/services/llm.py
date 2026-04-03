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
        "You are MemoryChain, a personal logging assistant. "
        "The user just logged personal data. Briefly confirm what was recorded. "
        "Be warm but concise — list the key items stored (sleep, mood, activities, etc). "
        "If anything seems unusual or notable, mention it briefly. "
        "Do NOT ask probing questions. Do NOT invent data not provided."
    ),
    "query": (
        "You are MemoryChain, a personal data assistant. "
        "The user asked about their stored data. Answer using ONLY the data provided below. "
        "Be specific — cite actual numbers, dates, and trends. "
        "If the data is sparse, say so honestly. "
        "Do NOT invent data. Do NOT speculate beyond what the numbers show."
    ),
    "chat": (
        "You are MemoryChain, a friendly personal assistant. "
        "The user is making conversation. Be warm, helpful, and concise. "
        "You can explain what MemoryChain does: track sleep, mood, activities, goals, "
        "tasks, and detect behavioral patterns. Suggest things the user can try. "
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
    if "?" in user_message:
        return (
            "I'm MemoryChain — I help you track sleep, mood, activities, goals, and tasks. "
            "Just type naturally to log data, or ask me about your patterns!\n\n"
            "Try: \"Slept 7h, mood 8/10\" or \"How's my sleep been this week?\""
        )
    return "Hey! Type anything to log it, or ask me about your data. /help shows all commands."


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
