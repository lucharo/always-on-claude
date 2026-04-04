"""Tests for happier_tui.client."""

from __future__ import annotations

import json
import time
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio

from happier_tui.client import (
    AGENT_FLAVORS,
    COMMON_MODELS,
    PERMISSION_MODES,
    Session,
    _infer_flavor_from_pid,
    _summarize_tool_use,
    archive_session,
    can_resume_locally,
    get_local_hostname,
    merge_local_into_relay,
    normalize_path_for_local,
    parse_history_messages,
    relative_time,
    send_notification,
    set_session_model,
    set_session_permission_mode,
    set_session_title,
    unarchive_session,
)


# ---------------------------------------------------------------------------
# relative_time
# ---------------------------------------------------------------------------


def test_relative_time_zero():
    assert relative_time(0) == "?"


def test_relative_time_just_now():
    now_ms = int(time.time() * 1000)
    assert relative_time(now_ms) == "just now"


def test_relative_time_minutes():
    ms = int((time.time() - 300) * 1000)  # 5 min ago
    assert "m ago" in relative_time(ms)


def test_relative_time_hours():
    ms = int((time.time() - 7200) * 1000)  # 2 hours ago
    assert "h ago" in relative_time(ms)


def test_relative_time_days():
    ms = int((time.time() - 86400 * 3) * 1000)  # 3 days ago
    assert "d ago" in relative_time(ms)


def test_relative_time_yesterday():
    ms = int((time.time() - 86400) * 1000)
    assert relative_time(ms) == "yesterday"


# ---------------------------------------------------------------------------
# _summarize_tool_use
# ---------------------------------------------------------------------------


def test_summarize_read():
    assert _summarize_tool_use("Read", {"file_path": "/foo/bar.py"}) == "Read /foo/bar.py"


def test_summarize_edit():
    assert _summarize_tool_use("Edit", {"file_path": "/foo.py"}) == "Edit /foo.py"


def test_summarize_bash():
    result = _summarize_tool_use("Bash", {"command": "ls -la"})
    assert result.startswith("Bash: ls")


def test_summarize_unknown():
    assert _summarize_tool_use("CustomTool", {}) == "Tool: CustomTool"


# ---------------------------------------------------------------------------
# parse_history_messages
# ---------------------------------------------------------------------------


def test_parse_empty():
    assert parse_history_messages([]) == []


def test_parse_user_message():
    raw = [
        {
            "id": "1",
            "createdAt": 1000,
            "role": "user",
            "text": "hello",
        }
    ]
    result = parse_history_messages(raw)
    assert len(result) == 1
    assert result[0]["role"] == "user"
    assert result[0]["text"] == "hello"


def test_parse_agent_text_message():
    raw = [
        {
            "id": "2",
            "createdAt": 2000,
            "role": "agent",
            "raw": {
                "content": {
                    "data": {
                        "type": "assistant",
                        "message": {
                            "content": [
                                {"type": "text", "text": "Here is my response"}
                            ]
                        },
                    }
                }
            },
        }
    ]
    result = parse_history_messages(raw)
    assert len(result) == 1
    assert result[0]["role"] == "assistant"
    assert result[0]["text"] == "Here is my response"


def test_parse_agent_tool_use():
    raw = [
        {
            "id": "3",
            "createdAt": 3000,
            "role": "agent",
            "raw": {
                "content": {
                    "data": {
                        "type": "assistant",
                        "message": {
                            "content": [
                                {
                                    "type": "tool_use",
                                    "name": "Read",
                                    "input": {"file_path": "/tmp/test.py"},
                                }
                            ]
                        },
                    }
                }
            },
        }
    ]
    result = parse_history_messages(raw)
    assert len(result) == 1
    assert result[0]["kind"] == "tool_use"
    assert "Read" in result[0]["text"]


def test_parse_skips_system_messages():
    raw = [
        {
            "id": "4",
            "createdAt": 4000,
            "role": "agent",
            "raw": {
                "content": {
                    "data": {"type": "system", "subtype": "stop_hook_summary"}
                }
            },
        }
    ]
    result = parse_history_messages(raw)
    assert len(result) == 0


def test_parse_reverses_order():
    """Messages come newest-first from API, should be oldest-first after parsing."""
    raw = [
        {"id": "2", "createdAt": 2000, "role": "user", "text": "second"},
        {"id": "1", "createdAt": 1000, "role": "user", "text": "first"},
    ]
    result = parse_history_messages(raw)
    assert result[0]["text"] == "first"
    assert result[1]["text"] == "second"


# ---------------------------------------------------------------------------
# can_resume_locally
# ---------------------------------------------------------------------------


def test_can_resume_nonexistent_path():
    s = Session(relay_id="test", path="/nonexistent/xyz/abc", host="remote")
    ok, reason = can_resume_locally(s)
    assert not ok
    assert "not found" in reason.lower()


def test_can_resume_no_path():
    s = Session(relay_id="test", path=None, host="remote")
    ok, reason = can_resume_locally(s)
    assert ok  # no path to check, passes


# ---------------------------------------------------------------------------
# normalize_path_for_local
# ---------------------------------------------------------------------------


def test_normalize_path_passthrough():
    # Standard local path should pass through
    import sys

    if sys.platform == "darwin":
        assert normalize_path_for_local("/Users/someone/Projects") == "/Users/someone/Projects"
    elif sys.platform == "linux":
        assert normalize_path_for_local("/home/someone/Projects") == "/home/someone/Projects"


# ---------------------------------------------------------------------------
# merge_local_into_relay
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_merge_local_into_relay():
    local_hostname = get_local_hostname()
    relay_sessions = [
        Session(relay_id="abc123", host=local_hostname, active=True),
        Session(relay_id="def456", host="remote-host", active=True),
    ]
    local_children = [
        {"happySessionId": "abc123", "pid": 99999, "startedBy": "daemon"},
    ]
    await merge_local_into_relay(relay_sessions, local_children)

    # Local session should be enriched
    assert relay_sessions[0].local_pid == 99999
    assert relay_sessions[0].started_by == "daemon"
    # Remote session should not be enriched
    assert relay_sessions[1].local_pid is None


# ---------------------------------------------------------------------------
# get_local_hostname
# ---------------------------------------------------------------------------


def test_get_local_hostname_no_fqdn():
    hostname = get_local_hostname()
    assert "." not in hostname  # Should strip FQDN
    assert len(hostname) > 0


# ---------------------------------------------------------------------------
# Session new fields
# ---------------------------------------------------------------------------


def test_session_new_fields_defaults():
    s = Session(relay_id="abc123")
    assert s.active_at == 0
    assert s.permission_mode == ""
    assert s.model_id == ""


def test_session_new_fields_populated():
    s = Session(
        relay_id="abc123",
        active_at=1700000000000,
        permission_mode="bypassPermissions",
        model_id="claude-opus-4-6",
    )
    assert s.active_at == 1700000000000
    assert s.permission_mode == "bypassPermissions"
    assert s.model_id == "claude-opus-4-6"


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


def test_permission_modes_non_empty():
    assert len(PERMISSION_MODES) >= 3
    assert "default" in PERMISSION_MODES
    assert "bypassPermissions" in PERMISSION_MODES


def test_common_models_non_empty():
    assert len(COMMON_MODELS) >= 2


def test_agent_flavors_includes_claude():
    assert "claude" in AGENT_FLAVORS
    assert "codex" in AGENT_FLAVORS


# ---------------------------------------------------------------------------
# API wrappers (mock _run_happier_cmd)
# ---------------------------------------------------------------------------

_CMD_PATH = "happier_tui.client._run_happier_cmd"


@pytest.mark.asyncio
async def test_set_session_title_success():
    with patch(_CMD_PATH, new_callable=AsyncMock) as mock:
        mock.return_value = {"ok": True, "data": {"sessionId": "s1", "title": "New"}}
        result = await set_session_title("s1", "New")
        assert result is True
        mock.assert_called_once_with("session", "set-title", "s1", "New")


@pytest.mark.asyncio
async def test_set_session_title_failure():
    with patch(_CMD_PATH, new_callable=AsyncMock) as mock:
        mock.return_value = None
        result = await set_session_title("s1", "New")
        assert result is False


@pytest.mark.asyncio
async def test_set_session_permission_mode():
    with patch(_CMD_PATH, new_callable=AsyncMock) as mock:
        mock.return_value = {"ok": True, "data": {"permissionMode": "plan"}}
        result = await set_session_permission_mode("s1", "plan")
        assert result is True
        mock.assert_called_once_with("session", "set-permission-mode", "s1", "plan")


@pytest.mark.asyncio
async def test_set_session_model():
    with patch(_CMD_PATH, new_callable=AsyncMock) as mock:
        mock.return_value = {"ok": True, "data": {"modelId": "claude-sonnet-4-6"}}
        result = await set_session_model("s1", "claude-sonnet-4-6")
        assert result is True
        mock.assert_called_once_with("session", "set-model", "s1", "claude-sonnet-4-6")


@pytest.mark.asyncio
async def test_archive_session():
    with patch(_CMD_PATH, new_callable=AsyncMock) as mock:
        mock.return_value = {"ok": True}
        result = await archive_session("s1")
        assert result is True
        mock.assert_called_once_with("session", "archive", "s1")


@pytest.mark.asyncio
async def test_unarchive_session():
    with patch(_CMD_PATH, new_callable=AsyncMock) as mock:
        mock.return_value = {"ok": True}
        result = await unarchive_session("s1")
        assert result is True
        mock.assert_called_once_with("session", "unarchive", "s1")


@pytest.mark.asyncio
async def test_send_notification():
    with patch(_CMD_PATH, new_callable=AsyncMock) as mock:
        mock.return_value = {"ok": True}
        result = await send_notification("Hello", "Test")
        assert result is True
        mock.assert_called_once_with("notify", "-p", "Hello", "-t", "Test")


@pytest.mark.asyncio
async def test_send_notification_default_title():
    with patch(_CMD_PATH, new_callable=AsyncMock) as mock:
        mock.return_value = {"ok": True}
        result = await send_notification("Hello")
        assert result is True
        mock.assert_called_once_with("notify", "-p", "Hello", "-t", "Happier")


# ---------------------------------------------------------------------------
# _infer_flavor_from_pid
# ---------------------------------------------------------------------------


def test_infer_flavor_codex():
    with patch("happier_tui.client.subprocess.run") as mock_run:
        mock_run.return_value = type("R", (), {
            "returncode": 0,
            "stdout": "/usr/bin/node happier codex --happy-starting-mode remote --started-by daemon",
        })()
        assert _infer_flavor_from_pid(12345) == "codex"


def test_infer_flavor_gemini():
    with patch("happier_tui.client.subprocess.run") as mock_run:
        mock_run.return_value = type("R", (), {
            "returncode": 0,
            "stdout": "/usr/bin/node happier gemini --happy-starting-mode remote",
        })()
        assert _infer_flavor_from_pid(12345) == "gemini"


def test_infer_flavor_claude_default():
    with patch("happier_tui.client.subprocess.run") as mock_run:
        mock_run.return_value = type("R", (), {
            "returncode": 0,
            "stdout": "/usr/bin/node happier claude --happy-starting-mode remote",
        })()
        assert _infer_flavor_from_pid(12345) == "claude"


def test_infer_flavor_process_gone():
    with patch("happier_tui.client.subprocess.run") as mock_run:
        mock_run.return_value = type("R", (), {"returncode": 1, "stdout": ""})()
        assert _infer_flavor_from_pid(99999) == ""


def test_infer_flavor_timeout():
    import subprocess as sp
    with patch("happier_tui.client.subprocess.run", side_effect=sp.TimeoutExpired("ps", 2)):
        assert _infer_flavor_from_pid(12345) == ""


# ---------------------------------------------------------------------------
# merge_local_into_relay flavor enrichment
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_merge_enriches_flavor_for_local():
    """Local sessions get flavor from _infer_flavor_from_pid."""
    import platform
    local_host = platform.node().split(".")[0].lower()

    relay = [Session(relay_id="s1", host=local_host)]
    children = [{"happySessionId": "s1", "pid": 42}]

    with patch("happier_tui.client.os.kill"):
        with patch("happier_tui.client._infer_flavor_from_pid", return_value="codex"):
            await merge_local_into_relay(relay, children)

    assert relay[0].flavor == "codex"


@pytest.mark.asyncio
async def test_merge_skips_flavor_for_remote():
    """Remote sessions keep default flavor (can't infer from PID)."""
    relay = [Session(relay_id="s1", host="remote-host-xyz")]
    children = []

    await merge_local_into_relay(relay, children)

    assert relay[0].flavor == "claude"  # default, not enriched
