"""Tests for happier_tui.sync."""

from __future__ import annotations

import json

from happier_tui.sync import (
    _encode_project_dir,
    _epoch_ms_to_iso,
    relay_to_jsonl_lines,
)


def test_encode_project_dir():
    assert _encode_project_dir("/home/luis") == "-home-luis"
    assert _encode_project_dir("/Users/foo/Projects/bar") == "-Users-foo-Projects-bar"


def test_epoch_ms_to_iso():
    # 2026-03-14T00:00:00.000Z
    result = _epoch_ms_to_iso(1773504000000)
    assert result.endswith("Z")
    assert "2026" in result


def test_relay_to_jsonl_empty():
    lines = relay_to_jsonl_lines([], session_id="test", cwd="/tmp")
    assert lines == []


def test_relay_to_jsonl_user_message():
    raw = [
        {
            "id": "1",
            "createdAt": 1773504000000,
            "role": "user",
            "text": "hello world",
        }
    ]
    lines = relay_to_jsonl_lines(raw, session_id="test-session", cwd="/tmp")
    assert len(lines) == 1
    line = lines[0]
    assert line["type"] == "user"
    assert line["sessionId"] == "test-session"
    assert line["cwd"] == "/tmp"
    assert line["message"]["role"] == "user"
    assert line["message"]["content"][0]["text"] == "hello world"
    assert line["parentUuid"] is None  # first message


def test_relay_to_jsonl_assistant_text():
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
                            "model": "claude-opus-4-6",
                            "id": "msg_abc",
                            "content": [
                                {"type": "text", "text": "Here is my response"}
                            ],
                            "stop_reason": "end_turn",
                            "usage": {"input_tokens": 10, "output_tokens": 5},
                        },
                    }
                }
            },
        }
    ]
    lines = relay_to_jsonl_lines(raw, session_id="s1", cwd="/tmp")
    assert len(lines) == 1
    line = lines[0]
    assert line["type"] == "assistant"
    assert line["message"]["content"][0]["text"] == "Here is my response"
    assert line["message"]["stop_reason"] == "end_turn"
    assert line["message"]["model"] == "claude-opus-4-6"


def test_relay_to_jsonl_tool_use_generates_result():
    """Tool use blocks should generate a corresponding tool_result line."""
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
                            "model": "claude-opus-4-6",
                            "id": "msg_xyz",
                            "content": [
                                {
                                    "type": "tool_use",
                                    "id": "toolu_123",
                                    "name": "Read",
                                    "input": {"file_path": "/tmp/test.py"},
                                }
                            ],
                            "stop_reason": "tool_use",
                            "usage": {},
                        },
                    }
                }
            },
        }
    ]
    lines = relay_to_jsonl_lines(raw, session_id="s1", cwd="/tmp")
    # Should produce: assistant (tool_use) + user (tool_result)
    assert len(lines) == 2
    assert lines[0]["type"] == "assistant"
    assert lines[0]["message"]["content"][0]["type"] == "tool_use"
    assert lines[1]["type"] == "user"
    assert lines[1]["message"]["content"][0]["type"] == "tool_result"
    assert lines[1]["message"]["content"][0]["tool_use_id"] == "toolu_123"


def test_relay_to_jsonl_skips_system():
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
    lines = relay_to_jsonl_lines(raw, session_id="s1", cwd="/tmp")
    assert len(lines) == 0


def test_relay_to_jsonl_uuid_chain():
    """Messages should be chained by parentUuid."""
    raw = [
        # Newest first (API order)
        {
            "id": "2",
            "createdAt": 2000,
            "role": "agent",
            "raw": {
                "content": {
                    "data": {
                        "type": "assistant",
                        "message": {
                            "model": "claude-opus-4-6",
                            "id": "msg_1",
                            "content": [{"type": "text", "text": "hi"}],
                            "stop_reason": "end_turn",
                            "usage": {},
                        },
                    }
                }
            },
        },
        {
            "id": "1",
            "createdAt": 1000,
            "role": "user",
            "text": "hello",
        },
    ]
    lines = relay_to_jsonl_lines(raw, session_id="s1", cwd="/tmp")
    assert len(lines) == 2
    # First line (user) has no parent
    assert lines[0]["parentUuid"] is None
    # Second line (assistant) chains to first
    assert lines[1]["parentUuid"] == lines[0]["uuid"]


def test_relay_to_jsonl_skips_thinking():
    """Thinking blocks should be skipped."""
    raw = [
        {
            "id": "5",
            "createdAt": 5000,
            "role": "agent",
            "raw": {
                "content": {
                    "data": {
                        "type": "assistant",
                        "message": {
                            "model": "claude-opus-4-6",
                            "id": "msg_2",
                            "content": [
                                {"type": "thinking", "thinking": "hmm", "signature": "sig"},
                                {"type": "text", "text": "result"},
                            ],
                            "stop_reason": "end_turn",
                            "usage": {},
                        },
                    }
                }
            },
        }
    ]
    lines = relay_to_jsonl_lines(raw, session_id="s1", cwd="/tmp")
    # Only the text block, not the thinking block
    assert len(lines) == 1
    assert lines[0]["message"]["content"][0]["type"] == "text"


def test_relay_to_jsonl_skips_empty_user():
    raw = [
        {"id": "1", "createdAt": 1000, "role": "user", "text": ""},
        {"id": "2", "createdAt": 2000, "role": "user", "text": "   "},
    ]
    lines = relay_to_jsonl_lines(raw, session_id="s1", cwd="/tmp")
    assert len(lines) == 0


def test_jsonl_is_valid_json():
    """Each line should be serializable as valid JSON."""
    raw = [
        {"id": "1", "createdAt": 1000, "role": "user", "text": "test"},
    ]
    lines = relay_to_jsonl_lines(raw, session_id="s1", cwd="/tmp")
    for line in lines:
        serialized = json.dumps(line)
        parsed = json.loads(serialized)
        assert parsed["type"] == line["type"]
