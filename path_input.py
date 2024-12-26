# https://github.com/tconbeer/textual-textarea/blob/main/src/textual_textarea/path_input.py (modified)

from __future__ import annotations
import os
import unicodedata

from rich.highlighter import Highlighter
from textual.binding import Binding
from textual.suggester import Suggester
from textual.validation import ValidationResult, Validator
from textual.widgets import Input
from difflib import SequenceMatcher
from pathlib import Path
from typing import final, override

import stat


def fuzzy_search(s: str, choices: list[str], limit: int | None = None) -> list[str]:
    matches: list[tuple[str, float]] = []

    for choice in choices:
        choice_lower = unicodedata.normalize("NFKC", choice).lower()

        if s in choice_lower:
            position = choice_lower.index(s)
            position_factor = 1 - (position / len(choice_lower) * 0.1)

            score = 1.0 + position_factor

            matches.append((choice, score))
        else:
            ratio = SequenceMatcher(None, s, choice_lower).ratio()
            matches.append((choice, ratio * 0.9))
    matches.sort(key=lambda x: x[1], reverse=True)
    matches_str = list(map(lambda x: x[0], matches))

    return matches_str[:limit] if limit else matches_str


def split_path_valid_invalid(path_str: str) -> tuple[Path, str]:
    path = Path(path_str)

    if not path_str:
        return Path("."), ""

    if path.exists():
        return path, ""

    current = path
    while current != current.parent and not current.exists():
        current = current.parent

    valid_str = str(current)
    if valid_str == ".":
        valid_str = ""

    if path_str.startswith("/") and not valid_str.startswith("/"):
        valid_str = "/" + valid_str

    invalid_part = path_str[len(valid_str) :].lstrip("/")

    return current, invalid_part


def render_path(path: Path) -> str:
    ext = os.path.sep if path.exists() and path.is_dir() else ""
    return f"{str(path.expanduser().resolve())}{ext}"


class PathSuggester(Suggester):
    def __init__(self) -> None:
        super().__init__(use_cache=False, case_sensitive=True)

    @override
    async def get_suggestion(self, value: str) -> str | None:
        if not value:
            return None

        valid, invalid = split_path_valid_invalid(value)
        if not invalid:
            return render_path(valid)

        entries = list(map(lambda x: x.name, valid.glob("*")))

        candidate = fuzzy_search(invalid, entries)
        if not candidate:
            return None

        return render_path(valid / candidate[0])


@final
class PathValidator(Validator):
    def __init__(
        self,
        dir_okay: bool,
        file_okay: bool,
        must_exist: bool,
        failure_description: str = "Not a valid path.",
    ) -> None:
        self.dir_okay = dir_okay
        self.file_okay = file_okay
        self.must_exist = must_exist
        super().__init__(failure_description)

    @override
    def validate(self, value: str) -> ValidationResult:
        if self.dir_okay and self.file_okay and not self.must_exist:
            return self.success()
        try:
            p = Path(value).expanduser().resolve()
        except Exception:
            return self.failure("Not a valid path.")

        try:
            st = p.stat()
        except FileNotFoundError:
            if self.must_exist:
                return self.failure("File or directory does not exist.")
            return self.success()

        if not self.dir_okay and stat.S_ISDIR(st.st_mode):
            return self.failure("Path cannot be a directory.")
        elif not self.file_okay and stat.S_ISREG(st.st_mode):
            return self.failure("Path cannot be a regular file.")

        return self.success()


@final
class PathInput(Input):
    BINDINGS = [
        Binding("tab", "complete", "Accept Completion", show=False),
    ]

    def __init__(
        self,
        value: str | None = None,
        placeholder: str = "",
        highlighter: Highlighter | None = None,
        password: bool = False,
        *,
        name: str | None = None,
        id: str | None = None,  # noqa: A002
        classes: str | None = None,
        disabled: bool = False,
        dir_okay: bool = True,
        file_okay: bool = True,
        must_exist: bool = False,
        tab_advances_focus: bool = False,
    ) -> None:
        self.tab_advances_focus = tab_advances_focus
        super().__init__(
            value,
            placeholder,
            highlighter,
            password,
            suggester=PathSuggester(),
            validators=PathValidator(dir_okay, file_okay, must_exist),
            name=name,
            id=id,
            classes=classes,
            disabled=disabled,
            select_on_focus=False,
        )

    def action_complete(self) -> None:
        if self._suggestion and self._suggestion != self.value:
            self.action_cursor_right()
        elif self.tab_advances_focus:
            self.app.action_focus_next()

    @override
    def _toggle_cursor(self) -> None:
        """Toggle visibility of cursor."""
        if self.app.is_headless:
            self._cursor_visible = True
        else:
            self._cursor_visible = not self._cursor_visible
