"""Happier TUI — session manager for Happier CLI."""

from __future__ import annotations

import os

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.reactive import reactive
from textual.widgets import DataTable, Footer, Header, Static

from happier_tui.client import (
    Session,
    can_resume_locally,
    get_local_hostname,
    is_daemon_running,
    list_local_sessions,
    merge_local_into_relay,
    read_daemon_state,
    relative_time,
    relay_list_sessions,
    stop_session,
    _normalize_path_for_local,
)


class StatusBar(Static):
    """Shows relay + daemon status."""

    daemon_running: reactive[bool] = reactive(False)
    relay_ok: reactive[bool] = reactive(False)
    session_count: reactive[int] = reactive(0)
    host_counts: reactive[dict] = reactive({})

    def render(self) -> str:
        parts = []
        if self.relay_ok:
            parts.append("[bold green]● Relay connected[/]")
        else:
            parts.append("[bold red]● Relay offline[/]")
        if self.daemon_running:
            parts.append("[green]● Daemon[/]")
        else:
            parts.append("[dim]● No daemon[/]")
        parts.append(f"Sessions: [bold]{self.session_count}[/]")
        if self.host_counts:
            host_parts = [f"{h}: {c}" for h, c in sorted(self.host_counts.items())]
            parts.append(f"[dim]({', '.join(host_parts)})[/]")
        return "  ".join(parts)


class SessionDetail(Static):
    """Shows details of the selected session."""

    session: reactive[Session | None] = reactive(None)

    def render(self) -> str:
        s = self.session
        if not s:
            return "[dim]Select a session to see details[/]"

        local_hostname = get_local_hostname()
        is_local = s.host and s.host.lower() == local_hostname

        if s.active:
            status = "[bold green]active[/]"
        else:
            status = "[dim]inactive[/]"
        if is_local and s.local_pid:
            if s.local_alive:
                status += f" [green](PID {s.local_pid})[/]"
            else:
                status += f" [red](PID {s.local_pid} dead)[/]"

        lines = [
            "[bold]Session Details[/]",
            "",
            f"  Relay ID:    [cyan]{s.relay_id}[/]",
            f"  Host:        [bold]{'[green]' if is_local else '[cyan]'}{s.host or '?'}[/]",
            f"  Directory:   {s.path or 'unknown'}",
            f"  Status:      {status}",
            f"  Updated:     {relative_time(s.updated_at)}",
            f"  Created:     {relative_time(s.created_at)}",
        ]
        if s.title:
            lines.append(f"  Title:       [bold]{s.title}[/]")
        if s.pending_count:
            lines.append(f"  Pending:     [yellow]{s.pending_count}[/]")
        lines.append("")
        if is_local:
            lines.append(f"  [dim]Resume:[/] happier --resume {s.relay_id} --yolo")
        else:
            lines.append(f"  [dim]Enter to open chat  |  R to try local resume[/]")

        return "\n".join(lines)


class HappierTUI(App):
    """Happier session manager TUI."""

    TITLE = "Happier Sessions"
    CSS = """
    Screen {
        layout: vertical;
    }
    #status-bar {
        height: 3;
        padding: 1;
        background: $surface;
        border-bottom: solid $primary;
    }
    #session-table {
        height: 1fr;
        border: round $primary;
    }
    #detail-panel {
        height: auto;
        max-height: 16;
        padding: 1;
        border-top: solid $primary;
        background: $surface;
    }
    DataTable {
        height: 1fr;
    }
    """

    BINDINGS = [
        Binding("r", "refresh", "Refresh"),
        Binding("enter", "select_session", "Open/Resume"),
        Binding("R", "resume_local", "Local Resume"),
        Binding("s", "stop_selected", "Stop"),
        Binding("n", "new_session", "New session"),
        Binding("l", "view_logs", "Logs"),
        Binding("q", "quit", "Quit"),
    ]

    sessions: list[Session] = []
    _sessions_by_id: dict[str, Session] = {}

    def compose(self) -> ComposeResult:
        yield Header()
        yield StatusBar(id="status-bar")
        with Vertical():
            yield DataTable(id="session-table")
            yield SessionDetail(id="detail-panel")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.cursor_type = "row"
        table.add_columns("", "Host", "Updated", "Directory", "Title")
        self.refresh_sessions()
        self.set_interval(5.0, self.refresh_sessions)

    @work(exclusive=True)
    async def refresh_sessions(self) -> None:
        status_bar = self.query_one(StatusBar)

        # Primary: relay sessions
        sessions = await relay_list_sessions()
        status_bar.relay_ok = len(sessions) > 0

        # Secondary: merge local daemon data
        state = read_daemon_state()
        status_bar.daemon_running = state is not None and is_daemon_running()
        if status_bar.daemon_running:
            local_children = await list_local_sessions()
            await merge_local_into_relay(sessions, local_children)

        # Sort: active first, then by updated_at descending
        sessions.sort(key=lambda s: (not s.active, -s.updated_at))

        status_bar.session_count = len(sessions)
        host_counts: dict[str, int] = {}
        for s in sessions:
            h = s.host or "?"
            host_counts[h] = host_counts.get(h, 0) + 1
        status_bar.host_counts = host_counts

        self.sessions = sessions
        self._sessions_by_id = {s.relay_id: s for s in sessions}

        table = self.query_one(DataTable)
        table.clear()

        local_hostname = get_local_hostname()
        home = os.path.expanduser("~")

        for s in sessions:
            # Status icon
            if s.active:
                status_icon = "[bold green]●[/]"
            elif s.local_alive:
                status_icon = "[green]○[/]"
            else:
                status_icon = "[dim]○[/]"

            # Host with color
            host = s.host or "?"
            is_local = host.lower() == local_hostname
            if is_local:
                host_display = f"[green]{host}[/]"
            else:
                host_display = f"[cyan]{host}[/]"

            # Path: shorten home dir
            path = s.path or "?"
            if path.startswith(home):
                path = "~" + path[len(home):]
            # Also shorten common prefixes
            path = path.replace("/Users/luischavesrodriguez/", "~/")
            path = path.replace("/home/luis/", "~/")

            title = (s.title or "")[:50]
            updated = relative_time(s.updated_at)

            table.add_row(
                status_icon,
                host_display,
                updated,
                path,
                title,
                key=s.relay_id,
            )

    def _get_selected_session(self) -> Session | None:
        table = self.query_one(DataTable)
        if table.cursor_row is None or not self._sessions_by_id:
            return None
        try:
            row_key, _ = table.coordinate_to_cell_key((table.cursor_row, 0))
            return self._sessions_by_id.get(row_key.value)
        except Exception:
            return None

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        detail = self.query_one(SessionDetail)
        detail.session = None
        detail.session = self._get_selected_session()

    def action_refresh(self) -> None:
        self.refresh_sessions()
        self.notify("Refreshing…")

    def action_select_session(self) -> None:
        """Enter on a session: local resume if local, chat screen if remote."""
        session = self._get_selected_session()
        if not session:
            self.notify("No session selected", severity="warning")
            return

        local_hostname = get_local_hostname()
        is_local = session.host and session.host.lower() == local_hostname

        if is_local:
            # Local session: resume directly
            cwd = session.path or os.path.expanduser("~")
            self.exit(result=("resume-yolo", session.relay_id, cwd, session.flavor))
        else:
            # Remote session: open chat screen
            from happier_tui.chat_screen import ChatScreen
            self.push_screen(ChatScreen(session))

    def action_resume_local(self) -> None:
        """R key: try to resume any session locally."""
        session = self._get_selected_session()
        if not session:
            self.notify("No session selected", severity="warning")
            return

        ok, reason = can_resume_locally(session)
        if not ok:
            self.notify(f"Cannot resume locally: {reason}", severity="error")
            return

        cwd = session.path or os.path.expanduser("~")
        # Normalize path for this machine
        cwd = _normalize_path_for_local(cwd)
        self.exit(result=("resume-yolo", session.relay_id, cwd, session.flavor))

    @work(exclusive=True)
    async def action_stop_selected(self) -> None:
        session = self._get_selected_session()
        if not session:
            self.notify("No session selected", severity="warning")
            return
        success = await stop_session(session.relay_id)
        if success:
            self.notify(f"Stopped {session.relay_id[:16]}…")
        else:
            self.notify("Failed to stop session", severity="error")
        self.refresh_sessions()

    def action_new_session(self) -> None:
        self.exit(result=("new", os.getcwd()))

    def action_view_logs(self) -> None:
        session = self._get_selected_session()
        if not session:
            self.notify("No session selected", severity="warning")
            return
        if not session.local_pid:
            self.notify("No local PID — logs only available for local sessions", severity="warning")
            return
        from pathlib import Path
        logs_dir = Path.home() / ".happier" / "logs"
        matches = sorted(logs_dir.glob(f"*-pid-{session.local_pid}.log"), reverse=True)
        if matches:
            self.exit(result=("logs", str(matches[0])))
        else:
            self.notify("No log file found", severity="warning")

    def action_quit(self) -> None:
        self.exit()


def main() -> None:
    app = HappierTUI()
    result = app.run()

    if result is None:
        return

    if result[0] in ("resume-yolo", "resume-default"):
        action, resume_id, cwd, flavor = result
        if os.path.isdir(cwd):
            os.chdir(cwd)

        cmd = ["happier"]
        if flavor and flavor != "claude":
            cmd.append(flavor)
        cmd.extend(["--resume", resume_id])
        if action == "resume-yolo":
            cmd.append("--yolo")

        os.execvp("happier", cmd)
    elif result[0] == "new":
        os.execvp("happier", ["happier", "--yolo"])
    elif result[0] == "logs":
        os.execvp("less", ["less", "+G", result[1]])


if __name__ == "__main__":
    main()
