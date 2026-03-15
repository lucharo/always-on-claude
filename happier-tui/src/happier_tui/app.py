"""Happier TUI — session manager for Happier CLI."""

from __future__ import annotations

import os

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import DataTable, Footer, Input, Static

import json
from pathlib import Path

from happier_tui.client import (
    Session,
    can_resume_locally,
    is_local_host,
    is_daemon_running,
    list_local_sessions,
    merge_local_into_relay,
    normalize_hostname,
    read_daemon_state,
    relative_time,
    relay_list_sessions,
    stop_session,
    normalize_path_for_local,
)


def _find_synced_relay_ids() -> set[str]:
    """Scan local JSONL files for sync_metadata to find relay origin IDs.

    Returns set of relay session IDs that have been synced locally.
    """
    synced = set()
    claude_projects = Path.home() / ".claude" / "projects"
    if not claude_projects.exists():
        return synced
    for project_dir in claude_projects.iterdir():
        if not project_dir.is_dir():
            continue
        for jsonl in project_dir.glob("*.jsonl"):
            try:
                with open(jsonl) as f:
                    first_line = f.readline()
                    if not first_line:
                        continue
                    data = json.loads(first_line)
                    if data.get("type") == "sync_metadata":
                        relay_id = data.get("relay_session_id")
                        if relay_id:
                            synced.add(relay_id)
            except (json.JSONDecodeError, OSError):
                continue
    return synced


def _infer_source(session: Session) -> str:
    """Infer whether session was started from phone, terminal, or daemon."""
    if session.started_by:
        sb = session.started_by.lower()
        if "terminal" in sb:
            return "terminal"
        if "daemon" in sb:
            return "daemon"
    # Heuristic: /home/luis or ~ with no specific project path → likely phone
    if session.path and session.path in ("/home/luis", os.path.expanduser("~")):
        return "phone"
    return "terminal"


def _shorten_path(path: str) -> str:
    """Shorten paths for display."""
    if not path or path == "?":
        return "?"
    home = os.path.expanduser("~")
    if path.startswith(home):
        path = "~" + path[len(home):]
    path = path.replace("/Users/luischavesrodriguez/", "~/")
    path = path.replace("/home/luis/", "~/")
    path = path.replace("~/Projects/", "~/P/")
    return path


def _session_status(s: Session) -> tuple[str, str]:
    """Return (icon, label) for session status.

    Three states:
    - connected: relay says active (socket.io connected)
    - running: local daemon says PID is alive (not connected to relay)
    - inactive: neither
    """
    if s.active:
        return "[bold green]●[/]", "[green]connected[/]"
    if s.local_alive:
        return "[yellow]●[/]", "[yellow]running[/]"
    return "[dim]○[/]", "[dim]inactive[/]"


class StatusBar(Static):
    """Compact single-row status bar."""

    daemon_running: reactive[bool] = reactive(False)
    relay_ok: reactive[bool] = reactive(False)
    total_count: reactive[int] = reactive(0)
    visible_count: reactive[int] = reactive(0)
    active_count: reactive[int] = reactive(0)
    running_count: reactive[int] = reactive(0)
    host_counts: reactive[dict] = reactive({})
    filter_label: reactive[str] = reactive("")

    def render(self) -> str:
        # Connection indicators — use symbols + text, not just color
        relay = "[bold green]✓ relay[/]" if self.relay_ok else "[bold red]✗ relay[/]"
        daemon = "  [bold green]✓ daemon[/]" if self.daemon_running else "  [dim]✗ daemon[/]"

        # Counts
        counts = f"{self.visible_count} sessions"
        if self.active_count:
            counts += f"  [green]{self.active_count} connected[/]"
        if self.running_count:
            counts += f"  [yellow]{self.running_count} running[/]"

        # Host breakdown
        hosts = ""
        if self.host_counts:
            host_parts = [f"{h}:{c}" for h, c in sorted(self.host_counts.items())]
            hosts = f"  [dim]{' '.join(host_parts)}[/]"

        # Filter pill
        filt = ""
        if self.filter_label:
            filt = f"  [black on yellow] {self.filter_label} [/]"

        return f"{relay}{daemon}  │  {counts}{hosts}{filt}"


class SessionDetail(Static):
    """Toggleable right sidebar with session details."""

    session: reactive[Session | None] = reactive(None)

    def render(self) -> str:
        s = self.session
        if not s:
            return "[dim]No session selected[/]"

        is_local = is_local_host(s.host)

        _, status_label = _session_status(s)
        source = _infer_source(s)

        title = s.title or "untitled"
        path = s.path or "?"

        lines = [
            f"[bold]{title}[/]",
            "",
            f"[dim]ID[/]      [cyan]{s.relay_id}[/]",
            f"[dim]Status[/]  {status_label}",
            f"[dim]Host[/]    {'[bold]' if is_local else '[cyan]'}{normalize_hostname(s.host or '?')}[/]",
            f"[dim]Agent[/]   {s.flavor}",
            f"[dim]Source[/]  {source}",
            f"[dim]Dir[/]     {path}",
            f"[dim]Updated[/] {relative_time(s.updated_at)}",
            f"[dim]Created[/] {relative_time(s.created_at)}",
        ]
        if s.synced_locally:
            lines.append(f"[dim]Synced[/]  [magenta]⇅ local copy exists[/]")
        if s.pending_count:
            lines.append(f"[dim]Pending[/] [yellow bold]{s.pending_count} messages[/]")
        if is_local and s.local_pid:
            pid_status = "[green]alive[/]" if s.local_alive else "[red]dead[/]"
            lines.append(f"[dim]PID[/]     {s.local_pid} {pid_status}")
        lines.append("")

        # Resume availability
        ok, reason = can_resume_locally(s)
        if is_local:
            lines.append("[dim]Enter: resume  R: resume (yolo)[/]")
        elif ok:
            lines.append("[dim]Enter: chat view[/]")
            lines.append("[dim]R: local resume (needs file sync)[/]")
        else:
            lines.append(f"[dim]Enter: chat view[/]")
            lines.append(f"[red]R: blocked ({reason})[/]")

        return "\n".join(lines)


class HappierTUI(App):
    """Happier session manager TUI."""

    TITLE = "Happier Sessions"
    CSS = """
    Screen {
        layout: vertical;
    }
    #status-bar {
        height: 1;
        padding: 0 1;
        background: $surface;
    }
    #main-area {
        height: 1fr;
    }
    #session-table {
        width: 1fr;
        border: round $primary;
    }
    #session-table.filtered {
        border: round yellow;
    }
    #detail-panel {
        width: 40;
        padding: 1;
        border-left: solid $primary-darken-2;
        background: $surface;
    }
    #detail-panel.hidden {
        display: none;
    }
    DataTable {
        height: 1fr;
    }
    #search-bar {
        height: 1;
        padding: 0 1;
        display: none;
        border: none;
        background: $surface;
    }
    #search-bar.visible {
        display: block;
    }
    #empty-message {
        width: 1fr;
        height: 1fr;
        content-align: center middle;
        text-align: center;
        display: none;
    }
    #empty-message.visible {
        display: block;
    }
    """

    BINDINGS = [
        Binding("r", "refresh", "Refresh"),
        Binding("enter", "select_session", "Open", priority=True),
        Binding("R", "resume_local", "Resume local"),
        Binding("a", "cycle_filter", "Filter"),
        Binding("slash", "search", "Search"),
        Binding("i", "toggle_detail", "Detail"),
        Binding("s", "stop_selected", "Stop"),
        Binding("n", "new_session", "New"),
        Binding("t", "toggle_theme", "Theme"),
        Binding("q", "quit", "Quit"),
        Binding("ctrl+c", "quit", show=False),
        Binding("ctrl+d", "quit", show=False),
    ]

    # Filter modes: "recent" (default) → "active" → "all"
    FILTER_MODES = ("recent", "active", "all")

    sessions: list[Session] = []
    _sessions_by_id: dict[str, Session] = {}
    _filter_mode: str = "recent"  # default: last 24h + active/running
    _search_query: str = ""

    def compose(self) -> ComposeResult:
        yield StatusBar(id="status-bar")
        yield Input(placeholder="/search…", id="search-bar")
        with Horizontal(id="main-area"):
            yield DataTable(id="session-table")
            yield Static(id="empty-message")
            yield SessionDetail(id="detail-panel")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.cursor_type = "row"
        table.zebra_stripes = True
        table.add_columns("", "Host", "Agent", "Title", "Directory", "Updated")
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

        # Mark sessions that have been synced locally
        synced_ids = _find_synced_relay_ids()
        for s in sessions:
            if s.relay_id in synced_ids:
                s.synced_locally = True

        # Sort: connected first, then running, then by updated_at descending
        sessions.sort(key=lambda s: (
            not s.active,       # connected first
            not s.local_alive,  # running second
            -s.updated_at,      # then most recent
        ))

        self.sessions = sessions
        self._sessions_by_id = {s.relay_id: s for s in sessions}

        # Count states
        active_count = sum(1 for s in sessions if s.active)
        running_count = sum(1 for s in sessions if s.local_alive and not s.active)
        status_bar.active_count = active_count
        status_bar.running_count = running_count
        status_bar.total_count = len(sessions)

        # Apply filters
        import time
        visible = sessions
        filter_parts = []
        cutoff_24h = int((time.time() - 86400) * 1000)

        if self._filter_mode == "recent":
            visible = [
                s for s in visible
                if s.active or s.local_alive or s.updated_at > cutoff_24h
            ]
            filter_parts.append("last 24h")
        elif self._filter_mode == "active":
            visible = [s for s in visible if s.active or s.local_alive]
            filter_parts.append("active/running")
        # "all" → no filter

        if self._search_query:
            q = self._search_query.lower()
            visible = [
                s for s in visible
                if q in (s.title or "").lower() or q in (s.path or "").lower()
            ]
            filter_parts.append(f'"{self._search_query}"')

        status_bar.filter_label = " + ".join(filter_parts) if self._filter_mode != "all" or self._search_query else ""
        status_bar.visible_count = len(visible)

        host_counts: dict[str, int] = {}
        for s in visible:
            h = s.host or "?"
            host_counts[h] = host_counts.get(h, 0) + 1
        status_bar.host_counts = host_counts

        # Update table border for filter state
        table = self.query_one(DataTable)
        if filter_parts:
            table.add_class("filtered")
        else:
            table.remove_class("filtered")

        # Show/hide empty message
        empty_msg = self.query_one("#empty-message", Static)

        if not visible:
            table.display = False
            empty_msg.add_class("visible")
            if self._filter_mode == "active":
                n_total = len(sessions)
                empty_msg.update(
                    f"[dim]No active or running sessions right now[/]\n"
                    f"[dim]{n_total} sessions hidden[/]\n\n"
                    f"[dim]Press [bold]a[/bold] to show all[/]"
                )
            elif self._filter_mode == "recent":
                n_total = len(sessions)
                empty_msg.update(
                    f"[dim]No sessions in the last 24 hours[/]\n"
                    f"[dim]{n_total} older sessions hidden[/]\n\n"
                    f"[dim]Press [bold]a[/bold] to show more[/]"
                )
            elif self._search_query:
                empty_msg.update(
                    f'[dim]No sessions matching "{self._search_query}"[/]\n\n'
                    f"[dim]Press [bold]/[/bold] to clear search[/]"
                )
            else:
                empty_msg.update(
                    "[dim]No sessions found[/]\n\n"
                    "[dim]Press [bold]n[/bold] to start one[/]"
                )
        else:
            table.display = True
            empty_msg.remove_class("visible")
            table.clear()

            for s in visible:
                icon, _ = _session_status(s)

                # Host: normalize FQDN, bold for local, dim for remote
                host = normalize_hostname(s.host or "?")
                is_local = is_local_host(s.host)
                host_display = f"[bold]{host}[/]" if is_local else f"[dim]{host}[/]"

                # Title: bold if active/running, dim italic if inactive
                title = s.title or "untitled"
                title = title[:45]
                synced_badge = " [magenta]⇅[/]" if s.synced_locally else ""
                if s.active or s.local_alive:
                    title_display = f"[bold]{title}[/]{synced_badge}"
                else:
                    title_display = f"[dim italic]{title}[/]{synced_badge}"

                agent = f"[dim]{s.flavor}[/]"
                path = _shorten_path(s.path or "?")
                updated = relative_time(s.updated_at)

                table.add_row(
                    icon,
                    host_display,
                    agent,
                    title_display,
                    path,
                    updated,
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

    def action_cycle_filter(self) -> None:
        """Cycle filter: recent → active → all → recent."""
        modes = self.FILTER_MODES
        idx = modes.index(self._filter_mode)
        self._filter_mode = modes[(idx + 1) % len(modes)]
        labels = {"recent": "Recent (24h)", "active": "Active/running only", "all": "All sessions"}
        self.notify(labels[self._filter_mode])
        self.refresh_sessions()

    def action_search(self) -> None:
        """Toggle search bar."""
        search = self.query_one("#search-bar", Input)
        if search.has_class("visible"):
            search.remove_class("visible")
            self._search_query = ""
            self.refresh_sessions()
            self.query_one(DataTable).focus()
        else:
            search.add_class("visible")
            search.clear()
            search.focus()

    def action_toggle_detail(self) -> None:
        """Toggle the detail sidebar."""
        panel = self.query_one("#detail-panel")
        if panel.has_class("hidden"):
            panel.remove_class("hidden")
        else:
            panel.add_class("hidden")

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "search-bar":
            self._search_query = event.value
            self.refresh_sessions()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "search-bar":
            event.input.remove_class("visible")
            self.query_one(DataTable).focus()

    def action_select_session(self) -> None:
        """Enter: local resume if local, chat screen if remote."""
        session = self._get_selected_session()
        if not session:
            self.notify("No session selected", severity="warning")
            return

        if is_local_host(session.host):
            cwd = session.path or os.path.expanduser("~")
            self.exit(result=("resume-yolo", session.relay_id, cwd, session.flavor))
        else:
            from happier_tui.chat_screen import ChatScreen
            self.push_screen(ChatScreen(session))

    def action_resume_local(self) -> None:
        """R: resume any session locally (syncs conversation first if remote)."""
        session = self._get_selected_session()
        if not session:
            self.notify("No session selected", severity="warning")
            return

        ok, reason = can_resume_locally(session)
        if not ok:
            self.notify(f"Cannot resume locally: {reason}", severity="error")
            return

        if is_local_host(session.host):
            cwd = session.path or os.path.expanduser("~")
            cwd = normalize_path_for_local(cwd)
            self.exit(result=("resume-yolo", session.relay_id, cwd, session.flavor))
        else:
            # Remote session: sync conversation from relay first
            self._sync_and_resume(session)

    @work(exclusive=True)
    async def _sync_and_resume(self, session: Session) -> None:
        """Sync conversation from relay and then resume locally."""
        from happier_tui.sync import sync_session_locally

        self.notify("Syncing conversation from relay…")
        try:
            jsonl_path, count = await sync_session_locally(session)
            self.notify(f"Synced {count} messages → {jsonl_path.name}")
        except Exception as e:
            self.notify(f"Sync failed: {e}", severity="error")
            return

        cwd = normalize_path_for_local(session.path or os.path.expanduser("~"))
        # Resume directly via claude (not happier) since we generated a
        # new session UUID that happier's relay doesn't know about
        resume_id = jsonl_path.stem
        self.exit(result=("resume-synced", resume_id, cwd, session.flavor))

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

    def action_toggle_theme(self) -> None:
        """Toggle between dark and light mode."""
        self.theme = "textual-light" if self.theme == "textual-dark" else "textual-dark"

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
    elif result[0] == "resume-synced":
        # Synced from relay — resume directly via the agent binary
        # (not happier, since the relay doesn't know this session UUID)
        _, resume_id, cwd, flavor = result
        if os.path.isdir(cwd):
            os.chdir(cwd)

        agent = flavor or "claude"
        cmd = [agent, "--resume", resume_id]
        os.execvp(agent, cmd)
    elif result[0] == "new":
        os.execvp("happier", ["happier", "--yolo"])
    elif result[0] == "logs":
        os.execvp("less", ["less", "+G", result[1]])


if __name__ == "__main__":
    main()
