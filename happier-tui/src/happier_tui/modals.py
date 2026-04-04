"""Modal screens for session management actions."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, Label, Select, Static, Switch

from happier_tui.client import AGENT_FLAVORS, COMMON_MODELS, PERMISSION_MODES


# ---------------------------------------------------------------------------
# Shared CSS for all modals
# ---------------------------------------------------------------------------

MODAL_CSS = """
ModalScreen {
    align: center middle;
}
#modal-dialog {
    width: 54;
    padding: 1 2;
    border: round $primary;
    background: $surface;
}
#modal-title {
    text-style: bold;
    margin-bottom: 1;
}
#modal-hint {
    color: $text-muted;
    margin-top: 1;
}
"""


class TitleModal(ModalScreen[str | None]):
    """Set session title."""

    CSS = MODAL_CSS
    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    def __init__(self, current_title: str = "", **kwargs) -> None:
        super().__init__(**kwargs)
        self._current = current_title

    def compose(self) -> ComposeResult:
        with Vertical(id="modal-dialog"):
            yield Label("Set Title", id="modal-title")
            yield Input(
                value=self._current,
                placeholder="Session title...",
                id="title-input",
            )
            yield Static("[dim]Enter to confirm, Escape to cancel[/]", id="modal-hint")

    def on_mount(self) -> None:
        self.query_one(Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        value = event.value.strip()
        self.dismiss(value if value else None)

    def action_cancel(self) -> None:
        self.dismiss(None)


class PermissionModal(ModalScreen[str | None]):
    """Set session permission mode."""

    CSS = MODAL_CSS
    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    def __init__(self, current_mode: str = "", **kwargs) -> None:
        super().__init__(**kwargs)
        self._current = current_mode

    def compose(self) -> ComposeResult:
        options = [(mode, mode) for mode in PERMISSION_MODES]
        with Vertical(id="modal-dialog"):
            yield Label("Permission Mode", id="modal-title")
            yield Select(
                options,
                value=self._current if self._current in PERMISSION_MODES else Select.BLANK,
                id="perm-select",
            )
            yield Static("[dim]Select mode, Escape to cancel[/]", id="modal-hint")

    def on_mount(self) -> None:
        self.query_one(Select).focus()

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.value != Select.BLANK:
            self.dismiss(str(event.value))

    def action_cancel(self) -> None:
        self.dismiss(None)


class ModelModal(ModalScreen[str | None]):
    """Set session model."""

    CSS = MODAL_CSS
    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    def __init__(self, current_model: str = "", **kwargs) -> None:
        super().__init__(**kwargs)
        self._current = current_model

    def compose(self) -> ComposeResult:
        options = [(m, m) for m in COMMON_MODELS]
        with Vertical(id="modal-dialog"):
            yield Label("Model", id="modal-title")
            yield Select(
                options,
                value=self._current if self._current in COMMON_MODELS else Select.BLANK,
                id="model-select",
            )
            yield Static("[dim]Select model, Escape to cancel[/]", id="modal-hint")

    def on_mount(self) -> None:
        self.query_one(Select).focus()

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.value != Select.BLANK:
            self.dismiss(str(event.value))

    def action_cancel(self) -> None:
        self.dismiss(None)


class NotifyModal(ModalScreen[str | None]):
    """Send a push notification."""

    CSS = MODAL_CSS
    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    def compose(self) -> ComposeResult:
        with Vertical(id="modal-dialog"):
            yield Label("Push Notification", id="modal-title")
            yield Input(
                placeholder="Message to send...",
                id="notify-input",
            )
            yield Static("[dim]Enter to send, Escape to cancel[/]", id="modal-hint")

    def on_mount(self) -> None:
        self.query_one(Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        value = event.value.strip()
        self.dismiss(value if value else None)

    def action_cancel(self) -> None:
        self.dismiss(None)


class NewSessionModal(ModalScreen[dict | None]):
    """Configure and start a new session."""

    CSS = MODAL_CSS + """
    #new-session-row {
        height: 3;
        margin-top: 1;
    }
    .field-label {
        margin-top: 1;
        color: $text-muted;
    }
    """
    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
        Binding("enter", "confirm", "Start", show=False),
    ]

    def compose(self) -> ComposeResult:
        flavor_options = [(f, f) for f in AGENT_FLAVORS]
        perm_options = [(m, m) for m in PERMISSION_MODES]
        with Vertical(id="modal-dialog"):
            yield Label("New Session", id="modal-title")
            yield Static("[dim]Agent[/]", classes="field-label")
            yield Select(flavor_options, value="claude", id="flavor-select")
            yield Static("[dim]Permission mode[/]", classes="field-label")
            yield Select(perm_options, value="bypassPermissions", id="perm-select")
            yield Static("[dim]Chrome browser access[/]", classes="field-label")
            yield Switch(value=False, id="chrome-switch")
            yield Static("[dim]Enter to start, Escape to cancel[/]", id="modal-hint")

    def on_mount(self) -> None:
        self.query_one("#flavor-select", Select).focus()

    def action_confirm(self) -> None:
        flavor = self.query_one("#flavor-select", Select).value
        perm = self.query_one("#perm-select", Select).value
        chrome = self.query_one("#chrome-switch", Switch).value
        if flavor == Select.BLANK:
            flavor = "claude"
        if perm == Select.BLANK:
            perm = "default"
        self.dismiss({
            "flavor": str(flavor),
            "permission_mode": str(perm),
            "chrome": chrome,
        })

    def action_cancel(self) -> None:
        self.dismiss(None)
