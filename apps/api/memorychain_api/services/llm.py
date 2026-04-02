from __future__ import annotations

from typing import Iterable

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


def _local_reply(
    *,
    user_message: str,
    memory_context: list[str],
    history_lines: list[str],
) -> str:
    lines = [
        "I logged that and updated your memory.",
    ]

    if memory_context:
        lines.append("Current context:")
        for item in memory_context[:4]:
            lines.append(f"- {item}")

    if "?" in user_message:
        lines.append("Answering directly: I can use this chat to track goals, tasks, check-ins, and weekly patterns.")

    lines.append("What is the single most important next action you want to commit to right now?")
    return "\n".join(lines)


def _openai_reply(
    *,
    user_message: str,
    memory_context: list[str],
    history_lines: list[str],
) -> str | None:
    if settings.llm_provider != "openai" or not settings.openai_api_key:
        return None

    try:
        from openai import OpenAI
    except Exception:
        return None

    client = OpenAI(api_key=settings.openai_api_key)
    memory_block = "\n".join(f"- {line}" for line in memory_context[:8]) or "- none"
    history_block = "\n".join(history_lines[-10:]) or "none"

    system_prompt = (
        "You are MemoryChain, a high-agency personal accountability companion. "
        "Be concise, concrete, and action-oriented. "
        "Use only memory facts provided. "
        "Never invent past events."
    )

    user_prompt = (
        f"Memory context:\n{memory_block}\n\n"
        f"Recent chat:\n{history_block}\n\n"
        f"User message:\n{user_message}\n\n"
        "Respond with: 1) direct response, 2) one concrete next step, 3) one follow-up question."
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


def generate_chat_reply(
    *,
    user_message: str,
    memory_context: list[str],
    history_lines: Iterable[str],
) -> str:
    history = list(history_lines)
    llm_output = _openai_reply(
        user_message=user_message,
        memory_context=memory_context,
        history_lines=history,
    )
    if llm_output:
        return llm_output
    return _local_reply(
        user_message=user_message,
        memory_context=memory_context,
        history_lines=history,
    )
