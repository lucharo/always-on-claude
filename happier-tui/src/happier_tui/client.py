"""Client for Happier relay API and local daemon."""

from __future__ import annotations

import asyncio
import json
import os
import platform
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class DaemonState:
    pid: int
    http_port: int
    started_at: int
    cli_version: str
    control_token: str | None
    log_path: str | None


@dataclass
class Session:
    """A session from the relay or local daemon."""

    relay_id: str  # happier relay session id (was happier_session_id)
    title: str | None = None
    path: str | None = None
    host: str | None = None
    active: bool = False
    created_at: int = 0  # epoch ms
    updated_at: int = 0  # epoch ms
    archived_at: int | None = None
    pending_count: int = 0
    # Sync state
    synced_locally: bool = False  # has been synced via conversation sync
    local_session_uuid: str | None = None  # local Claude session UUID if synced
    # Local daemon enrichment (only for sessions on this host)
    local_pid: int | None = None
    local_alive: bool = False
    claude_session_id: str | None = None
    started_by: str | None = None
    flavor: str = "claude"


def get_local_hostname() -> str:
    """Get the hostname that happier uses for this machine."""
    # Happier uses a short hostname, not FQDN
    return platform.node().split(".")[0].lower()


def normalize_hostname(host: str) -> str:
    """Normalize a hostname for comparison — strip FQDN, lowercase."""
    return host.split(".")[0].lower() if host else ""


def is_local_host(host: str | None) -> bool:
    """Check if a hostname refers to this machine."""
    if not host:
        return False
    return normalize_hostname(host) == get_local_hostname()


# ---------------------------------------------------------------------------
# Relay API (primary data source)
# ---------------------------------------------------------------------------

async def _run_happier_cmd(*args: str, timeout: float = 15.0) -> dict | None:
    """Run a happier CLI command and parse JSON output."""
    cmd = ["happier", *args, "--json"]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        if proc.returncode != 0:
            return None
        return json.loads(stdout.decode())
    except (asyncio.TimeoutError, json.JSONDecodeError, FileNotFoundError, OSError):
        return None


async def relay_list_sessions(include_archived: bool = False) -> list[Session]:
    """List all sessions from the relay API."""
    result = await _run_happier_cmd("session", "list")
    if not result or not result.get("ok"):
        return []

    raw_sessions = result.get("data", {}).get("sessions", [])
    sessions = []
    for s in raw_sessions:
        if not include_archived and s.get("archivedAt"):
            continue
        sessions.append(Session(
            relay_id=s["id"],
            title=s.get("title"),
            path=s.get("path"),
            host=s.get("host"),
            active=s.get("active", False),
            created_at=s.get("createdAt", 0),
            updated_at=s.get("updatedAt", 0),
            archived_at=s.get("archivedAt"),
            pending_count=s.get("pendingCount", 0),
        ))

    return sessions


async def get_session_history(
    session_id: str,
    limit: int = 50,
    fmt: str = "raw",
) -> list[dict]:
    """Fetch session history from relay. Returns list of message dicts."""
    args = ["session", "history", session_id, "--format", fmt, "--limit", str(limit)]
    result = await _run_happier_cmd(*args, timeout=30.0)
    if not result or not result.get("ok"):
        return []
    return result.get("data", {}).get("messages", [])


async def get_session_runs(session_id: str) -> list[dict]:
    """List runs for a session."""
    result = await _run_happier_cmd("session", "run", "list", session_id)
    if not result or not result.get("ok"):
        return []
    return result.get("data", {}).get("runs", [])


async def stream_start(
    session_id: str, run_id: str, message: str
) -> dict | None:
    """Start a stream (send a message to a session).

    Note: message is passed as a CLI argument. Very long messages (>128KB)
    may hit OS argument length limits on some platforms.
    """
    result = await _run_happier_cmd(
        "session", "run", "stream-start", session_id, run_id, message,
        timeout=30.0,
    )
    if not result or not result.get("ok"):
        return None
    return result.get("data", {})


async def stream_read(
    session_id: str, run_id: str, stream_id: str, cursor: int = 0
) -> dict | None:
    """Read events from a stream."""
    result = await _run_happier_cmd(
        "session", "run", "stream-read", session_id, run_id, stream_id,
        "--cursor", str(cursor),
        timeout=30.0,
    )
    if not result or not result.get("ok"):
        return None
    return result.get("data", {})


async def stream_cancel(
    session_id: str, run_id: str, stream_id: str
) -> bool:
    """Cancel an active stream."""
    result = await _run_happier_cmd(
        "session", "run", "stream-cancel", session_id, run_id, stream_id,
    )
    return bool(result and result.get("ok"))


# ---------------------------------------------------------------------------
# History parsing helpers
# ---------------------------------------------------------------------------

def parse_history_messages(raw_messages: list[dict]) -> list[dict]:
    """Parse raw history messages into displayable format.

    Returns list of dicts with keys: role, text, kind, timestamp
    """
    parsed = []
    for msg in reversed(raw_messages):  # raw comes newest-first
        ts = msg.get("createdAt", 0)
        role = msg.get("role", "")

        if role == "user":
            text = msg.get("text", "")
            if text and text.strip():
                parsed.append({
                    "role": "user",
                    "text": text.strip(),
                    "kind": "text",
                    "timestamp": ts,
                })
        elif role == "agent":
            raw = msg.get("raw", {}).get("content", {}).get("data", {})
            if not isinstance(raw, dict):
                continue
            msg_type = raw.get("type", "")
            if msg_type == "assistant":
                content = raw.get("message", {}).get("content", [])
                if isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict):
                            if block.get("type") == "text" and block.get("text", "").strip():
                                parsed.append({
                                    "role": "assistant",
                                    "text": block["text"].strip(),
                                    "kind": "text",
                                    "timestamp": ts,
                                })
                            elif block.get("type") == "tool_use":
                                name = block.get("name", "unknown")
                                inp = block.get("input", {})
                                summary = _summarize_tool_use(name, inp)
                                parsed.append({
                                    "role": "assistant",
                                    "text": summary,
                                    "kind": "tool_use",
                                    "timestamp": ts,
                                })

    return parsed


def _summarize_tool_use(name: str, inp: dict) -> str:
    """Create a one-line summary of a tool use."""
    if name in ("Read", "read"):
        return f"Read {inp.get('file_path', inp.get('path', '?'))}"
    if name in ("Edit", "edit"):
        return f"Edit {inp.get('file_path', '?')}"
    if name in ("Write", "write"):
        return f"Write {inp.get('file_path', '?')}"
    if name in ("Bash", "bash"):
        cmd = inp.get("command", "?")
        return f"Bash: {cmd[:60]}"
    if name in ("Glob", "glob"):
        return f"Glob: {inp.get('pattern', '?')}"
    if name in ("Grep", "grep"):
        return f"Grep: {inp.get('pattern', '?')}"
    return f"Tool: {name}"


# ---------------------------------------------------------------------------
# Local daemon (secondary enrichment)
# ---------------------------------------------------------------------------

def _find_happier_dir() -> Path:
    return Path.home() / ".happier"


def _find_active_server_dir() -> Path | None:
    happier_dir = _find_happier_dir()
    settings_path = happier_dir / "settings.json"
    if not settings_path.exists():
        return None
    settings = json.loads(settings_path.read_text())
    active_id = settings.get("activeServerId", "cloud")
    server_dir = happier_dir / "servers" / active_id
    return server_dir if server_dir.exists() else None


def read_daemon_state() -> DaemonState | None:
    server_dir = _find_active_server_dir()
    if not server_dir:
        return None
    state_path = server_dir / "daemon.state.json"
    if not state_path.exists():
        return None
    data = json.loads(state_path.read_text())
    return DaemonState(
        pid=data.get("pid", 0),
        http_port=data.get("httpPort", 0),
        started_at=data.get("startedAt", 0),
        cli_version=data.get("startedWithCliVersion", "?"),
        control_token=data.get("controlToken"),
        log_path=data.get("daemonLogPath"),
    )


_httpx_client: "httpx.AsyncClient | None" = None


def _get_httpx_client() -> "httpx.AsyncClient":
    """Reuse a single httpx.AsyncClient to avoid per-call overhead."""
    import httpx

    global _httpx_client
    if _httpx_client is None or _httpx_client.is_closed:
        _httpx_client = httpx.AsyncClient()
    return _httpx_client


async def _daemon_post(path: str, body: dict | None = None, timeout: float = 10.0) -> dict:
    state = read_daemon_state()
    if not state or not state.http_port:
        return {"error": "No daemon running"}

    try:
        os.kill(state.pid, 0)
    except OSError:
        return {"error": "Daemon PID not running"}

    headers = {"Content-Type": "application/json"}
    if state.control_token:
        headers["x-happier-daemon-token"] = state.control_token

    url = f"http://127.0.0.1:{state.http_port}{path}"
    client = _get_httpx_client()
    resp = await client.post(url, json=body or {}, headers=headers, timeout=timeout)
    if resp.status_code != 200:
        return {"error": f"HTTP {resp.status_code}: {resp.text}"}
    return resp.json()


async def list_local_sessions() -> list[dict]:
    """List sessions from the local daemon. Returns raw child dicts."""
    result = await _daemon_post("/list")
    if "error" in result:
        return []
    return result.get("children", [])


async def stop_session(session_id: str) -> bool:
    result = await _daemon_post("/stop-session", {"sessionId": session_id})
    return result.get("success", False)


async def merge_local_into_relay(
    relay_sessions: list[Session],
    local_children: list[dict],
) -> None:
    """Enrich relay sessions with local daemon data (PID, alive status)."""
    # Build mapping of happier session ID -> local child data
    local_by_id = {}
    for child in local_children:
        sid = child.get("happySessionId", "")
        if sid:
            local_by_id[sid] = child

    for session in relay_sessions:
        if not is_local_host(session.host):
            continue
        child = local_by_id.get(session.relay_id)
        if child:
            pid = child.get("pid", 0)
            session.local_pid = pid
            session.started_by = child.get("startedBy", "unknown")
            try:
                os.kill(pid, 0)
                session.local_alive = True
            except ProcessLookupError:
                session.local_alive = False
            except PermissionError:
                session.local_alive = True


def is_daemon_running() -> bool:
    state = read_daemon_state()
    if not state:
        return False
    try:
        os.kill(state.pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def shorten_path(path: str) -> str:
    """Shorten a filesystem path for display.

    Maps any home directory prefix to ~, then shortens ~/Projects/ to ~/P/.
    Uses Path.home() so it works for any user on any machine.
    """
    if not path or path == "?":
        return "?"
    home = str(Path.home())
    if path.startswith(home):
        path = "~" + path[len(home):]
    # Cross-machine: normalize any /Users/<user>/ or /home/<user>/ to ~/
    path = re.sub(r"^/Users/[^/]+/", "~/", path)
    path = re.sub(r"^/home/[^/]+/", "~/", path)
    path = path.replace("~/Projects/", "~/P/")
    return path


def relative_time(epoch_ms: int) -> str:
    """Convert epoch milliseconds to a human-readable relative time."""
    import time

    if not epoch_ms:
        return "?"
    diff = time.time() - (epoch_ms / 1000)
    if diff < 0:
        return "just now"
    if diff < 60:
        return "just now"
    if diff < 3600:
        mins = int(diff / 60)
        return f"{mins}m ago"
    if diff < 86400:
        hours = int(diff / 3600)
        return f"{hours}h ago"
    days = int(diff / 86400)
    if days == 1:
        return "yesterday"
    if days < 30:
        return f"{days}d ago"
    return f"{days // 30}mo ago"


def can_resume_locally(session: Session) -> tuple[bool, str]:
    """Check if a session can be resumed locally.

    Returns (can_resume, reason_if_not).
    """
    import shutil

    # Check agent binary
    agent = session.flavor or "claude"
    if not shutil.which(agent) and not shutil.which("happier"):
        return False, f"'{agent}' not installed locally"

    # Check directory exists
    if session.path:
        # Normalize path for this machine
        local_path = normalize_path_for_local(session.path)
        if not os.path.isdir(local_path):
            return False, f"Directory not found: {local_path}"

    return True, ""


def normalize_path_for_local(p: str) -> str:
    """Normalize a path from the relay to work on this machine."""
    import sys

    if sys.platform == "darwin":
        # On Mac, /home/luis/* should map to /Users/<user>/*
        match = re.match(r"/home/[^/]+/(.+)", p)
        if match:
            return str(Path.home() / match.group(1))
    elif sys.platform == "linux":
        # On Linux, /Users/* should map to ~/
        match = re.match(r"/Users/[^/]+/(.+)", p)
        if match:
            return str(Path.home() / match.group(1))
    return p
