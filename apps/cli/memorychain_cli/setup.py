"""Setup wizard — first-run configuration and 'memorychain setup' command."""

from __future__ import annotations

import httpx
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from . import settings

console = Console()
err_console = Console(stderr=True)


def validate_openai_key(api_key: str) -> dict | None:
    """Validate an OpenAI API key by calling /v1/me. Returns account info or None."""
    try:
        resp = httpx.get(
            "https://api.openai.com/v1/me",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10.0,
        )
        if resp.status_code == 200:
            return resp.json()
        return None
    except (httpx.ConnectError, httpx.TimeoutException):
        return None


def show_account_info(account: dict) -> None:
    """Display authenticated account details."""
    name = account.get("name", "Unknown")
    email = account.get("email", "")
    orgs = account.get("orgs", {}).get("data", [])

    info = Text()
    info.append("✓ Authenticated\n", style="bold green")
    info.append(f"  Name:  {name}\n")
    if email:
        info.append(f"  Email: {email}\n")
    if orgs:
        org_names = ", ".join(o.get("title", o.get("id", "?")) for o in orgs)
        info.append(f"  Org:   {org_names}\n")

    console.print(Panel(info, title="[bold]OpenAI Account[/bold]", border_style="green"))


def run_setup(*, interactive: bool = True) -> bool:
    """Run the setup wizard. Returns True if setup completed successfully."""
    console.print()
    console.print(Panel(
        "[bold cyan]MemoryChain Setup[/bold cyan]\n\n"
        "MemoryChain uses OpenAI's API for natural language understanding.\n"
        "You'll need an API key from [link=https://platform.openai.com/api-keys]platform.openai.com/api-keys[/link]",
        border_style="cyan",
    ))
    console.print()

    if not interactive:
        return False

    # Prompt for API key with masked input
    from prompt_toolkit import prompt as pt_prompt

    while True:
        try:
            api_key = pt_prompt(
                "  OpenAI API Key (paste here, hidden): ",
                is_password=True,
            ).strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Setup cancelled.[/dim]")
            return False

        if not api_key:
            console.print("[dim]  No key entered. Try again or Ctrl+C to cancel.[/dim]")
            continue

        if not api_key.startswith("sk-"):
            console.print("[yellow]  That doesn't look like an OpenAI key (should start with sk-). Try again.[/yellow]")
            continue

        # Validate the key
        console.print("[dim]  Validating key…[/dim]")
        account = validate_openai_key(api_key)

        if account is None:
            console.print("[red]  ✗ Key validation failed. Check the key and try again.[/red]")
            continue

        # Success — save and show account
        settings.save_config({
            **settings.load_config(),
            "openai_api_key": api_key,
            "llm_provider": "openai",
            "account_name": account.get("name", ""),
            "account_email": account.get("email", ""),
        })

        console.print()
        show_account_info(account)
        console.print()
        console.print(f"[green]✓[/green] Config saved to [dim]{settings.CONFIG_FILE}[/dim]")
        console.print()
        return True


def check_and_prompt_setup() -> None:
    """Called on REPL launch — if not configured, offer to run setup."""
    if settings.is_configured():
        # Already configured — show a brief account line
        config = settings.load_config()
        name = config.get("account_name", "")
        if name:
            console.print(f"  [dim]Account:[/dim] {name}")
        return

    console.print("[yellow]  ⚠ No OpenAI API key configured.[/yellow]")
    console.print("[dim]  MemoryChain works best with an LLM connection.[/dim]")
    console.print()

    from prompt_toolkit import prompt as pt_prompt
    try:
        answer = pt_prompt("  Run setup now? (Y/n): ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        console.print()
        return

    if answer in ("", "y", "yes"):
        run_setup()
    else:
        console.print("[dim]  Skipping setup. Run 'memorychain setup' anytime.[/dim]\n")
