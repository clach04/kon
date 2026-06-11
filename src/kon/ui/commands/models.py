"""/model command - listing and switching models."""

from __future__ import annotations

from ...llm import get_all_models
from ..chat import ChatLog
from ..floating_list import ListItem
from ..selection_mode import SelectionMode
from ..widgets import InfoBar
from .base import CommandSupport


class ModelCommands(CommandSupport):
    def _handle_model_command(self, args: str) -> None:
        models = get_all_models()
        if not models:
            self.notify("No models configured", title="Models", timeout=3, severity="warning")
            return

        models.sort(key=lambda m: (m.provider, m.id))

        items: list[ListItem] = []
        for m in models:
            parts = [m.provider]
            if not m.supports_images:
                parts.append("[no-vision]")
            caption = " ".join(parts)
            label = (
                f"{m.id} ✓"
                if m.id == self._runtime.model and m.provider == self._runtime.model_provider
                else m.id
            )
            items.append(ListItem(value=m, label=label, description=caption))

        self._show_selection_picker(items, SelectionMode.MODEL)

    def _select_model(self, model) -> None:
        chat = self.query_one("#chat-log", ChatLog)
        info_bar = self.query_one("#info-bar", InfoBar)

        try:
            self._runtime.switch_model(model)
        except ValueError as e:
            chat.add_info_message(str(e), error=True)
            return
        self._sync_runtime_state()

        info_bar.set_model(model.id, model.provider)

        chat.add_info_message(f"Model changed to {model.id} ({model.provider})")
