"""Intent classification — determines whether a message is a log, query, or chat.

This is the first step in the chat pipeline. Classification happens BEFORE
any extraction or storage, so questions never become journal entries.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Literal

from ..config import settings


Intent = Literal["log", "query", "chat"]


@dataclass
class ClassificationResult:
    intent: Intent
    confidence: float
    query_params: dict = field(default_factory=dict)
    reasoning: str = ""


# ── Keyword patterns for local fallback ──────────────────────

# Strong log signals: numeric data that only makes sense as a personal entry
_LOG_PATTERNS = [
    re.compile(r"sleep\s*\d", re.I),
    re.compile(r"slept\s*\d", re.I),
    re.compile(r"mood\s*\d", re.I),
    re.compile(r"energy\s*\d", re.I),
    re.compile(r"\d+\s*/\s*10", re.I),
    re.compile(r"\d+(?:\.\d+)?\s*(?:hrs?|hours?)\b", re.I),
    re.compile(r"\d+\s*(?:lbs?|kg|pounds?)\b", re.I),
    re.compile(r"\b(?:did|completed|finished)\s+\d+\s*(?:min|rounds?|sets?|reps?)", re.I),
    re.compile(r"\b(?:todo|goal)\s*:", re.I),
    re.compile(r"- \[ ?]", re.I),
    re.compile(r"\b(?:woke|dreamt|trained|sparred|ran|lifted|meditat)", re.I),
    re.compile(r"\bbody\s*weight\s*[:\s]+\d", re.I),
    re.compile(r"\bheart\s*rate\s*[:\s]+\d", re.I),
]

# Query signals: asking about stored data
_QUERY_PATTERNS = [
    re.compile(r"\b(?:how|what|when|where|show|tell|list|get|pull up|display|summarize|summary)\b.*\b(?:my|i|me)\b", re.I),
    re.compile(r"\b(?:my|i|me)\b.*\b(?:how|what|when|where|show|tell|list|get)\b", re.I),
    re.compile(r"\b(?:show|list|get|display|pull up|look up)\b.*\b(?:goal|task|insight|checkin|check-in|review|activit|metric|heuristic|journal|log|sleep|mood|data)\b", re.I),
    re.compile(r"\bhow\s+(?:has|have|is|was|were|did|do)\b.*\b(?:sleep|mood|energy|weight|training|exercise)\b", re.I),
    re.compile(r"\b(?:this|last|past)\s+(?:week|month|day)\b", re.I),
    re.compile(r"\b(?:average|trend|pattern|history|progress)\b", re.I),
    re.compile(r"\bhow\s+(?:am|many|much|often)\b", re.I),
]

# Chat signals: conversational, no data content
_CHAT_PATTERNS = [
    re.compile(r"^(?:hey|hi|hello|yo|sup|thanks|thank you|ok|okay|cool|nice|great|bye|goodbye)\s*[!?.]*$", re.I),
    re.compile(r"^(?:what can you|how do you|help|what are you|who are you)", re.I),
    re.compile(r"^(?:yes|no|yep|nope|sure|maybe|alright)\s*[!?.]*$", re.I),
]


def _classify_local(message: str) -> ClassificationResult:
    """Keyword-based classification when no LLM is available."""
    text = message.strip()

    # Short messages with no data → chat
    if len(text) < 15:
        for pat in _CHAT_PATTERNS:
            if pat.search(text):
                return ClassificationResult(intent="chat", confidence=0.9, reasoning="short conversational message")

    # Check for strong log signals (numeric data)
    log_hits = sum(1 for pat in _LOG_PATTERNS if pat.search(text))
    query_hits = sum(1 for pat in _QUERY_PATTERNS if pat.search(text))

    # Question mark is a strong query signal
    has_question = "?" in text
    if has_question:
        query_hits += 2

    if log_hits > 0 and log_hits >= query_hits:
        return ClassificationResult(intent="log", confidence=min(0.6 + log_hits * 0.1, 0.95), reasoning=f"{log_hits} log pattern matches")

    if query_hits > 0 and query_hits > log_hits:
        return ClassificationResult(intent="query", confidence=min(0.6 + query_hits * 0.1, 0.95), reasoning=f"{query_hits} query pattern matches")

    # Message with a question mark but no strong patterns → likely query
    if has_question:
        return ClassificationResult(intent="query", confidence=0.7, reasoning="contains question mark")

    # Longer messages without clear signals → default to chat (safe, no storage)
    if len(text) < 40:
        return ClassificationResult(intent="chat", confidence=0.5, reasoning="short message, no clear intent")

    # Long messages without data patterns → still might be logging narrative
    # But we err on the side of NOT storing to avoid the current problem
    return ClassificationResult(intent="chat", confidence=0.4, reasoning="no clear log or query patterns")


def _classify_llm(message: str) -> ClassificationResult | None:
    """LLM-based classification using OpenAI."""
    if settings.llm_provider != "openai" or not settings.openai_api_key:
        return None

    try:
        from openai import OpenAI
    except ImportError:
        return None

    client = OpenAI(api_key=settings.openai_api_key)

    system_prompt = (
        "You are an intent classifier for a personal logging and memory system. "
        "Classify the user's message into exactly one of three categories:\n\n"
        '- "log": The user is recording personal data, activities, metrics, moods, '
        "sleep, goals, tasks, journal entries, or describing what they did/experienced. "
        "They want this information STORED.\n\n"
        '- "query": The user is asking about their stored data, requesting summaries, '
        "looking up past entries, asking about trends or patterns, or wants to see "
        "their goals/tasks/insights. They want INFORMATION RETRIEVED.\n\n"
        '- "chat": The user is making conversation, asking about the system itself, '
        "saying hello/goodbye, giving feedback, or their message has no personal data "
        "to store and no data to retrieve.\n\n"
        "Respond with ONLY a JSON object, no other text."
    )

    user_prompt = (
        f'Classify this message:\n\n"{message}"\n\n'
        "Respond with JSON:\n"
        '{"intent": "log"|"query"|"chat", "confidence": 0.0-1.0, '
        '"reasoning": "brief explanation"}'
    )

    try:
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0,
            max_tokens=150,
        )
        raw = completion.choices[0].message.content or ""
        # Extract JSON from response
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        data = json.loads(raw)
        intent = data.get("intent", "chat")
        if intent not in ("log", "query", "chat"):
            intent = "chat"
        return ClassificationResult(
            intent=intent,
            confidence=float(data.get("confidence", 0.8)),
            reasoning=data.get("reasoning", ""),
        )
    except Exception:
        return None


def classify_intent(message: str) -> ClassificationResult:
    """Classify a user message as log, query, or chat.

    Tries LLM classification first (fast, cheap with gpt-4o-mini),
    falls back to keyword heuristics if LLM unavailable.
    """
    llm_result = _classify_llm(message)
    if llm_result is not None:
        return llm_result
    return _classify_local(message)
