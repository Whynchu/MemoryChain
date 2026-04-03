"""Tests for terminal environment module and REPL UX features."""

import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from memorychain_cli.terminal import (
    get_cwd,
    get_short_cwd,
    detect_git,
    get_terminal_width,
    get_account_display,
    get_data_dir,
    set_title,
    restore_title,
    clear_screen,
)


class TestGetCwd:
    def test_returns_string(self):
        result = get_cwd()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_home_uses_tilde(self):
        home = Path.home()
        with patch("memorychain_cli.terminal.Path") as MockPath:
            MockPath.cwd.return_value = home / "projects" / "test"
            MockPath.home.return_value = home
            result = get_cwd()
            assert result.startswith("~/") or result.startswith("~\\")


class TestGetShortCwd:
    def test_returns_string(self):
        result = get_short_cwd()
        assert isinstance(result, str)

    def test_respects_max_parts(self):
        result = get_short_cwd(max_parts=1)
        parts = result.replace("…/", "").split("/")
        # Should have at most max_parts path components
        assert len(parts) <= 2  # could have the tilde prefix


class TestDetectGit:
    def test_returns_none_outside_repo(self):
        with patch("memorychain_cli.terminal.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=128, stdout="", stderr="")
            result = detect_git()
            assert result is None

    def test_returns_dict_in_repo(self):
        with patch("memorychain_cli.terminal.subprocess.run") as mock_run:
            root_result = MagicMock(returncode=0, stdout="/home/user/repo\n")
            branch_result = MagicMock(returncode=0, stdout="main\n")
            mock_run.side_effect = [root_result, branch_result]
            result = detect_git()
            assert result is not None
            assert result["branch"] == "main"
            assert result["root"] == "/home/user/repo"

    def test_handles_git_not_found(self):
        with patch("memorychain_cli.terminal.subprocess.run", side_effect=FileNotFoundError):
            result = detect_git()
            assert result is None


class TestGetTerminalWidth:
    def test_returns_positive_int(self):
        width = get_terminal_width()
        assert isinstance(width, int)
        assert width > 0

    def test_fallback_on_error(self):
        with patch("memorychain_cli.terminal.os.get_terminal_size", side_effect=OSError):
            width = get_terminal_width()
            assert width == 80


class TestGetAccountDisplay:
    def test_with_name(self):
        with patch("memorychain_cli.settings.load_config", return_value={"account_name": "John Doe"}):
            result = get_account_display()
            assert result == "John Doe"

    def test_with_email(self):
        with patch("memorychain_cli.settings.load_config", return_value={"account_email": "john@test.com"}):
            result = get_account_display()
            assert result == "john@test.com"

    def test_with_key_only(self):
        with patch("memorychain_cli.settings.load_config", return_value={"openai_api_key": "sk-xxx"}):
            result = get_account_display()
            assert result == "API key configured"

    def test_not_configured(self):
        with patch("memorychain_cli.settings.load_config", return_value={}):
            result = get_account_display()
            assert result == "not configured"


class TestTerminalTitle:
    @patch("memorychain_cli.terminal.sys")
    def test_set_title_unix(self, mock_sys):
        mock_sys.platform = "linux"
        mock_sys.stdout = MagicMock()
        set_title("TestTitle")
        mock_sys.stdout.write.assert_called()
        mock_sys.stdout.flush.assert_called()

    @patch("memorychain_cli.terminal.sys")
    def test_restore_title_unix(self, mock_sys):
        mock_sys.platform = "linux"
        mock_sys.stdout = MagicMock()
        restore_title()
        mock_sys.stdout.write.assert_called()


class TestReplFunctions:
    """Test REPL module functions that don't require a running REPL."""

    def test_slash_commands_list(self):
        from memorychain_cli.repl import SLASH_COMMANDS
        assert "/today" in SLASH_COMMANDS
        assert "/help" in SLASH_COMMANDS
        assert "/quit" in SLASH_COMMANDS
        assert "/clear" in SLASH_COMMANDS
        assert "/exit" in SLASH_COMMANDS

    def test_help_text_has_examples(self):
        from memorychain_cli.repl import HELP_TEXT
        assert "How has my sleep" in HELP_TEXT
        assert "/clear" in HELP_TEXT

    def test_build_prompt_returns_html(self):
        from memorychain_cli.repl import _build_prompt
        prompt = _build_prompt()
        # prompt_toolkit HTML object
        assert prompt is not None

    @patch("memorychain_cli.repl.detect_git")
    def test_build_prompt_with_git(self, mock_git):
        from memorychain_cli.repl import _build_prompt
        mock_git.return_value = {"branch": "main", "root": "/test"}
        prompt = _build_prompt()
        assert prompt is not None
        # Minimal prompt is just a chevron
        assert "›" in str(prompt.value)

    @patch("memorychain_cli.repl.detect_git")
    def test_build_prompt_without_git(self, mock_git):
        from memorychain_cli.repl import _build_prompt
        mock_git.return_value = None
        prompt = _build_prompt()
        assert prompt is not None
        assert "›" in str(prompt.value)

    @patch("memorychain_cli.repl.client")
    def test_build_header_connected(self, mock_client):
        from memorychain_cli.repl import _build_header
        mock_client.health.return_value = {"status": "ok"}
        panel = _build_header()
        assert panel is not None

    @patch("memorychain_cli.repl.client")
    def test_build_header_disconnected(self, mock_client):
        from memorychain_cli.repl import _build_header
        mock_client.health.side_effect = Exception("down")
        panel = _build_header()
        assert panel is not None
