"""Chat screen for interacting with remote sessions via the relay."""

from __future__ import annotations

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Footer, Header, Input, RichLog, Static

from happier_tui.client import (
    Session,
    get_session_history,
    get_session_runs,
    parse_history_messages,
    relative_time,
    stream_cancel,
    stream_read,
    stream_start,
)


class ChatStatus(Static):
    """Status bar showing session info."""

    def __init__(self, session: Session) -> None:
        super().__init__()
        self._session = session

    def render(self) -> str:
        s = self._session
        status = "[bold green]active[/]" if s.active else "[dim]inactive[/]"
        host = f"[cyan]{s.host}[/]" if s.host else "?"
        title = f"  [bold]{s.title}[/]" if s.title else ""
        return f"{host}  {status}  {relative_time(s.updated_at)}{title}"


class ChatScreen(Screen):
    """Chat view for a remote session."""

    BINDINGS = [
        Binding("escape", "go_back", "Back"),
    ]

    CSS = """
    ChatScreen {
        layout: vertical;
    }
    #chat-status {
        height: 3;
        padding: 1;
        background: $surface;
        border-bottom: solid $primary;
    }
    #chat-log {
        height: 1fr;
        border: round $primary;
        padding: 0 1;
    }
    #chat-input {
        dock: bottom;
    }
    """

    def __init__(self, session: Session) -> None:
        super().__init__()
        self._session = session
        self._streaming = False
        self._stream_id: str | None = None
        self._run_id: str | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        yield ChatStatus(self._session, id="chat-status")
        yield RichLog(id="chat-log", highlight=True, markup=True, wrap=True)
        yield Input(
            placeholder="Type a message (Enter to send, Escape to go back)…",
            id="chat-input",
        )
        yield Footer()

    def on_mount(self) -> None:
        self.load_history()
        if not self._session.active:
            log = self.query_one(RichLog)
            log.write("[dim italic]Session is inactive — history is read-only[/]")
            self.query_one(Input).disabled = True

    @work(exclusive=True, group="history")
    async def load_history(self) -> None:
        """Load conversation history from relay."""
        log = self.query_one(RichLog)
        log.write("[dim]Loading history…[/]")

        raw = await get_session_history(self._session.relay_id, limit=50, fmt="raw")
        messages = parse_history_messages(raw)

        log.clear()
        if not messages:
            log.write("[dim]No messages yet[/]")
            return

        for msg in messages:
            self._render_message(log, msg)

    def _render_message(self, log: RichLog, msg: dict) -> None:
        """Render a single message to the RichLog."""
        role = msg["role"]
        text = msg["text"]
        kind = msg.get("kind", "text")

        if role == "user":
            log.write(f"[bold cyan]You:[/] {text}")
        elif role == "assistant":
            if kind == "tool_use":
                log.write(f"  [dim]{text}[/]")
            else:
                log.write(f"[bold green]Claude:[/] {text}")
        log.write("")  # blank line between messages

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Send a message when Enter is pressed."""
        message = event.value.strip()
        if not message or self._streaming:
            return

        event.input.clear()
        log = self.query_one(RichLog)
        log.write(f"[bold cyan]You:[/] {message}")
        log.write("")

        self._send_message(message)

    @work(exclusive=True, group="stream")
    async def _send_message(self, message: str) -> None:
        """Send message via relay stream API."""
        log = self.query_one(RichLog)
        inp = self.query_one(Input)
        self._streaming = True
        inp.disabled = True

        # Get or create a run
        runs = await get_session_runs(self._session.relay_id)
        if runs:
            run_id = runs[0].get("id", "")
        else:
            log.write("[yellow]No active run found — cannot send message[/]")
            self._streaming = False
            inp.disabled = False
            return

        # Start stream
        stream_data = await stream_start(self._session.relay_id, run_id, message)
        if not stream_data:
            log.write("[red]Failed to start stream[/]")
            self._streaming = False
            inp.disabled = False
            return

        stream_id = stream_data.get("streamId", "")
        self._stream_id = stream_id
        self._run_id = run_id

        # Poll for events
        cursor = 0
        while self._streaming:
            data = await stream_read(
                self._session.relay_id, run_id, stream_id, cursor=cursor
            )
            if not data:
                break

            events = data.get("events", [])
            for event in events:
                self._handle_stream_event(log, event)

            new_cursor = data.get("cursor", cursor)
            done = data.get("done", False)

            if done:
                break
            if new_cursor == cursor and not events:
                # No new data, wait before polling again
                import asyncio
                await asyncio.sleep(0.5)
            cursor = new_cursor

        self._streaming = False
        self._stream_id = None
        self._run_id = None
        inp.disabled = not self._session.active

    def _handle_stream_event(self, log: RichLog, event: dict) -> None:
        """Process a single stream event."""
        event_type = event.get("type", "")

        if event_type == "text":
            text = event.get("text", "")
            if text.strip():
                log.write(f"[bold green]Claude:[/] {text}")
        elif event_type == "tool_use":
            name = event.get("name", "?")
            log.write(f"  [dim]Using {name}…[/]")
        elif event_type == "tool_result":
            pass  # skip tool results in display
        elif event_type == "error":
            error = event.get("error", "Unknown error")
            log.write(f"[red]Error: {error}[/]")
        elif event_type == "done":
            log.write("[dim]─── Response complete ───[/]")
            log.write("")

    def action_go_back(self) -> None:
        """Return to session list, cancelling any active stream."""
        if self._streaming and self._stream_id and self._run_id:
            self._cancel_stream()
        self.app.pop_screen()

    @work(group="cancel")
    async def _cancel_stream(self) -> None:
        if self._stream_id and self._run_id:
            await stream_cancel(
                self._session.relay_id, self._run_id, self._stream_id
            )
        self._streaming = False
