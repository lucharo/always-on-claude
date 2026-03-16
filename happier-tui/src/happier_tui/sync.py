"""Conversation sync: reconstruct local JSONL from relay history.

This enables cross-device session resume by pulling conversation history
from the Happier relay and writing it in the format Claude Code expects.

Flow:
  1. Pull full history from relay (raw format)
  2. Transform relay messages → Claude Code JSONL lines
  3. Write to ~/.claude/projects/<encoded-path>/<session-uuid>.jsonl
  4. Now `happier --resume <id>` can find it locally
"""

from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from happier_tui.client import (
    Session,
    get_session_history,
    normalize_path_for_local,
)


def _encode_project_dir(path: str) -> str:
    """Encode a filesystem path as a Claude project directory name.

    Claude encodes /home/luis → -home-luis (replaces / with -)
    """
    return path.replace("/", "-")


def _make_uuid() -> str:
    return str(uuid.uuid4())


def _epoch_ms_to_iso(epoch_ms: int) -> str:
    """Convert epoch milliseconds to ISO 8601 string."""
    dt = datetime.fromtimestamp(epoch_ms / 1000, tz=timezone.utc)
    return dt.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def relay_to_jsonl_lines(
    raw_messages: list[dict],
    session_id: str,
    cwd: str,
    version: str = "2.1.76",
) -> list[dict]:
    """Transform relay raw history messages into Claude Code JSONL lines.

    Only produces `user` and `assistant` lines — the minimum needed for
    `--resume` to work. Skips progress, system, hooks, and other metadata.

    Args:
        raw_messages: Messages from `get_session_history(fmt="raw")`,
                      returned newest-first from the API.
        session_id: The Claude session UUID (or relay session ID as fallback).
        cwd: Working directory path.
        version: Claude Code version string.

    Returns:
        List of JSONL-ready dicts, in chronological order.
    """
    # Reverse to chronological order (API returns newest-first)
    messages = list(reversed(raw_messages))

    lines: list[dict] = []
    parent_uuid: str | None = None

    for msg in messages:
        role = msg.get("role", "")
        ts = msg.get("createdAt", 0)
        timestamp = _epoch_ms_to_iso(ts)

        envelope = {
            "parentUuid": parent_uuid,
            "isSidechain": False,
            "userType": "external",
            "cwd": cwd,
            "sessionId": session_id,
            "version": version,
        }

        if role == "user":
            text = msg.get("text", "")
            if not text or not text.strip():
                continue

            line_uuid = _make_uuid()
            line = {
                "type": "user",
                **envelope,
                "uuid": line_uuid,
                "timestamp": timestamp,
                "message": {
                    "role": "user",
                    "content": [{"type": "text", "text": text}],
                },
            }
            lines.append(line)
            parent_uuid = line_uuid

        elif role == "agent":
            raw = msg.get("raw", {}).get("content", {}).get("data", {})
            if not isinstance(raw, dict):
                continue

            msg_type = raw.get("type", "")

            if msg_type == "assistant":
                api_message = raw.get("message", {})
                content_blocks = api_message.get("content", [])
                if not isinstance(content_blocks, list):
                    continue

                # Get the API message metadata
                model = api_message.get("model", "claude-opus-4-6")
                msg_id = api_message.get("id", f"msg_{_make_uuid()[:20]}")
                stop_reason = api_message.get("stop_reason")
                usage = api_message.get("usage", {})

                # Filter to emittable blocks (skip thinking)
                emittable = [
                    b for b in content_blocks
                    if isinstance(b, dict) and b.get("type") != "thinking"
                ]

                for i, block in enumerate(emittable):
                    block_type = block.get("type", "")
                    is_last = (i == len(emittable) - 1)
                    line_uuid = _make_uuid()

                    line = {
                        "type": "assistant",
                        **envelope,
                        "parentUuid": parent_uuid,
                        "uuid": line_uuid,
                        "timestamp": timestamp,
                        "message": {
                            "model": model,
                            "id": msg_id,
                            "type": "message",
                            "role": "assistant",
                            "content": [block],
                            "stop_reason": stop_reason if is_last else None,
                            "stop_sequence": None,
                            **({"usage": usage} if is_last else {}),
                        },
                    }
                    lines.append(line)
                    parent_uuid = line_uuid

                    # If this was a tool_use, we need a tool_result
                    # We don't have the actual result from relay, so emit
                    # a minimal placeholder
                    if block_type == "tool_use":
                        tool_id = block.get("id", f"toolu_{_make_uuid()[:20]}")
                        result_uuid = _make_uuid()
                        result_line = {
                            "type": "user",
                            **envelope,
                            "parentUuid": parent_uuid,
                            "uuid": result_uuid,
                            "timestamp": timestamp,
                            "message": {
                                "role": "user",
                                "content": [{
                                    "tool_use_id": tool_id,
                                    "type": "tool_result",
                                    "content": "(synced from relay — original output not available)",
                                }],
                            },
                        }
                        lines.append(result_line)
                        parent_uuid = result_uuid

    return lines


def jsonl_path_for_session(
    session: Session,
    session_uuid: str | None = None,
) -> Path:
    """Determine the local JSONL file path for a session.

    Claude Code stores conversations at:
      ~/.claude/projects/<encoded-path>/<session-uuid>.jsonl

    Where <encoded-path> is the working directory with / replaced by -
    """
    claude_dir = Path.home() / ".claude" / "projects"

    # Determine the working directory path (normalized for this machine)
    cwd = session.path or "/"
    local_cwd = normalize_path_for_local(cwd)

    # Encode the path as a project directory name
    project_dir_name = _encode_project_dir(local_cwd)
    project_dir = claude_dir / project_dir_name
    project_dir.mkdir(parents=True, exist_ok=True)

    # Use session UUID or relay ID as filename
    file_id = session_uuid or session.relay_id
    return project_dir / f"{file_id}.jsonl"


async def sync_session_locally(
    session: Session,
    limit: int = 500,
) -> tuple[Path, int]:
    """Pull relay history and write it as a local JSONL file.

    Returns (path_to_jsonl, message_count).
    """
    # Pull full history from relay
    raw = await get_session_history(
        session.relay_id,
        limit=limit,
        fmt="raw",
    )

    if not raw:
        raise RuntimeError("No history returned from relay")

    # Determine local working directory
    cwd = normalize_path_for_local(session.path or "/")

    # Deterministic UUID from relay ID — same relay session always maps to
    # the same local file. This makes sync idempotent (transfer, not clone).
    session_uuid = str(uuid.uuid5(uuid.NAMESPACE_URL, f"happier:{session.relay_id}"))

    # Transform relay messages to JSONL lines
    lines = relay_to_jsonl_lines(
        raw_messages=raw,
        session_id=session_uuid,
        cwd=cwd,
    )

    if not lines:
        raise RuntimeError("No user/assistant messages found in history")

    # Write JSONL file
    jsonl_path = jsonl_path_for_session(session, session_uuid)
    with open(jsonl_path, "w") as f:
        # First line: sync metadata (so the TUI can link back to relay origin)
        meta = {
            "type": "sync_metadata",
            "relay_session_id": session.relay_id,
            "relay_host": session.host,
            "synced_at": _epoch_ms_to_iso(int(time.time() * 1000)),
            "original_title": session.title,
        }
        f.write(json.dumps(meta, separators=(",", ":")) + "\n")
        for line in lines:
            f.write(json.dumps(line, separators=(",", ":")) + "\n")

    return jsonl_path, len(lines)
