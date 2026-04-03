"""MemoryChain duotone theme — #064DD1 blue + greys."""

from __future__ import annotations

from prompt_toolkit.styles import Style as PtStyle
from rich.theme import Theme as RichTheme

# ── Brand palette ────────────────────────────────────────────
BLUE = "#064DD1"
BLUE_BRIGHT = "#3B7BF7"
BLUE_DIM = "#043A9E"

GREY_LIGHT = "#b0b8c4"
GREY_MID = "#6b7280"
GREY_DARK = "#2d3748"
GREY_BG = "#1a202c"

# Semantic (keep recognizable)
GREEN = "#22c55e"
RED = "#ef4444"
YELLOW = "#eab308"

# ── Rich theme ───────────────────────────────────────────────
RICH_THEME = RichTheme({
    "mc.blue": BLUE,
    "mc.bright": BLUE_BRIGHT,
    "mc.dim": BLUE_DIM,
    "mc.grey": GREY_MID,
    "mc.grey_light": GREY_LIGHT,
    "mc.ok": GREEN,
    "mc.err": RED,
    "mc.warn": YELLOW,
})

# ── prompt_toolkit style ─────────────────────────────────────
PT_STYLE = PtStyle.from_dict({
    "bottom-toolbar": f"bg:{GREY_BG} {GREY_MID}",
    "prompt": f"bold {BLUE}",
})
