"""Tests for happier_tui.client."""

from __future__ import annotations

import json
import time
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio

from happier_tui.client import (
    Session,
    normalize_path_for_local,
    _summarize_tool_use,
    can_resume_locally,
    get_local_hostname,
    merge_local_into_relay,
    parse_history_messages,
    relative_time,
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
