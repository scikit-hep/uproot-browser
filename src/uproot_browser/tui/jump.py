from __future__ import annotations

import dataclasses
from typing import ClassVar

import rich.text
import textual.app
import textual.binding
import textual.containers
import textual.fuzzy
import textual.screen
import textual.widgets
from textual.widgets.option_list import Option


@dataclasses.dataclass
class Candidate:
    """A jump target: a node's full path plus how to display it."""

    path: str
    name: str  # final path segment, what the fuzzy query matches against
    icon: str
    is_dir: bool


class JumpScreen(textual.screen.ModalScreen[str | None]):
    """fzf-style finder: fuzzy-match a node's name, return its path."""

    BINDINGS: ClassVar[list[textual.binding.BindingType]] = [
        textual.binding.Binding("down", "cursor_down", "Down", show=False),
        textual.binding.Binding("up", "cursor_up", "Up", show=False),
        textual.binding.Binding("escape", "cancel", "Cancel", show=False),
    ]

    def __init__(self, candidates: list[Candidate]) -> None:
        self.candidates = candidates
        super().__init__()

    def compose(self) -> textual.app.ComposeResult:
        with textual.containers.Container(id="jump-dialog"):
            yield textual.widgets.Input(placeholder="Jump to branch…", id="jump-input")
            yield textual.widgets.OptionList(id="jump-results")

    def on_mount(self) -> None:
        self._populate("")
        self.query_one("#jump-input", textual.widgets.Input).focus()

    def _populate(self, query: str) -> None:
        results = self.query_one("#jump-results", textual.widgets.OptionList)
        results.clear_options()

        if query:
            matcher = textual.fuzzy.Matcher(query)
            scored = [(matcher.match(c.name), c) for c in self.candidates]
            candidates = [
                c
                for _, c in sorted(
                    ((s, c) for s, c in scored if s > 0),
                    key=lambda sc: sc[0],
                    reverse=True,
                )
            ]
        else:
            candidates = self.candidates

        results.add_options([Option(self._label(c), id=c.path) for c in candidates])
        if candidates:
            results.highlighted = 0

    @staticmethod
    def _label(candidate: Candidate) -> rich.text.Text:
        display = candidate.path.lstrip("/")
        prefix = display[: len(display) - len(candidate.name)]
        text = rich.text.Text(candidate.icon)
        text.append(prefix, style="dim")
        text.append(candidate.name, style="bold")
        return text

    def on_input_changed(self, event: textual.widgets.Input.Changed) -> None:
        self._populate(event.value)

    def on_input_submitted(self) -> None:
        results = self.query_one("#jump-results", textual.widgets.OptionList)
        if results.highlighted is None:
            return
        option = results.get_option_at_index(results.highlighted)
        self.dismiss(option.id)

    def on_option_list_option_selected(
        self, event: textual.widgets.OptionList.OptionSelected
    ) -> None:
        self.dismiss(event.option.id)

    def action_cursor_down(self) -> None:
        self.query_one("#jump-results", textual.widgets.OptionList).action_cursor_down()

    def action_cursor_up(self) -> None:
        self.query_one("#jump-results", textual.widgets.OptionList).action_cursor_up()

    def action_cancel(self) -> None:
        self.dismiss(None)
