"""
Unified console, formatting, and UI components for gitctl.
"""

from __future__ import annotations

from contextlib import contextmanager
import re
from typing import Any, Generator, List, Optional

try:
    from rich import box
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    from rich.prompt import Confirm, Prompt
    HAS_RICH = True
except ImportError:
    HAS_RICH = False
    box = None  # type: ignore
    Console = None  # type: ignore
    Panel = None  # type: ignore
    Table = None  # type: ignore
    Text = None  # type: ignore
    Confirm = None  # type: ignore
    Prompt = None  # type: ignore


def _strip_tags(text: Any) -> str:
    """Strip basic Rich markup tags like [bold red]...[/bold red]."""
    return re.sub(r'\[/?[a-zA-Z0-9_\s#=,-]+\]', '', str(text))


class DummyTable:
    """Minimal text-based fallback Table when rich is not available."""

    def __init__(self, title: Optional[str] = None, **kwargs) -> None:
        self.title = title
        self.columns: List[str] = []
        self.rows: List[List[str]] = []

    def add_column(self, header: str, **kwargs) -> None:
        self.columns.append(_strip_tags(header))

    def add_row(self, *args, **kwargs) -> None:
        self.rows.append([_strip_tags(str(a)) for a in args])

    def __str__(self) -> str:
        lines: List[str] = []
        if self.title:
            lines.append(f"=== {self.title} ===")
        if not self.columns:
            return "\n".join(lines)

        col_widths = [len(c) for c in self.columns]
        for row in self.rows:
            for i, val in enumerate(row):
                if i < len(col_widths):
                    col_widths[i] = max(col_widths[i], len(val))
                else:
                    col_widths.append(len(val))

        header_line = " | ".join(c.ljust(col_widths[i]) for i, c in enumerate(self.columns))
        sep_line = "-+-".join("-" * col_widths[i] for i in range(len(self.columns)))
        lines.append(header_line)
        lines.append(sep_line)

        for row in self.rows:
            padded_row = [
                str(row[i]).ljust(col_widths[i]) if i < len(row) else "".ljust(col_widths[i])
                for i in range(len(self.columns))
            ]
            lines.append(" | ".join(padded_row))

        return "\n".join(lines)


class DummyConsole:
    """Minimal fallback Console when rich is not available."""

    def __init__(self, no_color: bool = False) -> None:
        self.no_color = no_color

    def print(self, *args, **kwargs) -> None:
        clean_args = []
        for a in args:
            if isinstance(a, str):
                clean_args.append(_strip_tags(a))
            else:
                clean_args.append(str(a))
        print(*clean_args)

    @contextmanager
    def status(self, message: str, spinner: str = "dots") -> Generator[None, None, None]:
        clean_msg = _strip_tags(message)
        print(f"[*] {clean_msg}")
        yield


class DummyPrompt:
    """Minimal text fallback for rich.prompt.Prompt."""

    @staticmethod
    def ask(prompt: str, choices: Optional[List[str]] = None, default: Optional[str] = None, **kwargs) -> str:
        clean_prompt = _strip_tags(prompt)
        if choices:
            clean_prompt += f" ({'/'.join(choices)})"
        if default is not None:
            clean_prompt += f" [{default}]"
        clean_prompt += ": "
        val = input(clean_prompt).strip()
        return val if val else (default or "")


class DummyConfirm:
    """Minimal text fallback for rich.prompt.Confirm."""

    @staticmethod
    def ask(prompt: str, default: bool = True, **kwargs) -> bool:
        clean_prompt = _strip_tags(prompt)
        suffix = " [Y/n]: " if default else " [y/N]: "
        val = input(clean_prompt + suffix).strip().lower()
        if not val:
            return default
        return val in ("y", "yes", "true", "1")


# Provide fallbacks if rich is missing
if not HAS_RICH:
    Prompt = DummyPrompt  # type: ignore
    Confirm = DummyConfirm  # type: ignore

# Shared global console instance
console = Console() if HAS_RICH else DummyConsole()


def get_console(no_color: bool = False) -> Any:
    """Return a configured Console instance."""
    if no_color:
        return Console(no_color=True) if HAS_RICH else DummyConsole(no_color=True)
    return console


@contextmanager
def status_spinner(
    message: str,
    custom_console: Optional[Any] = None,
    spinner: str = "dots",
) -> Generator[None, None, None]:
    """Display an animated Rich spinner with message while executing code block."""
    c = custom_console or console
    if HAS_RICH and not getattr(c, "no_color", False):
        with c.status(f"[bold cyan]{message}[/bold cyan]", spinner=spinner):
            yield
    else:
        with c.status(message, spinner=spinner):
            yield


def print_error(message: str, custom_console: Optional[Any] = None) -> None:
    """Print a standardized error message."""
    c = custom_console or console
    if HAS_RICH:
        c.print(f"[bold red]Error:[/bold red] {message}")
    else:
        c.print(f"Error: {message}")


def print_warning(message: str, custom_console: Optional[Any] = None) -> None:
    """Print a standardized warning message."""
    c = custom_console or console
    if HAS_RICH:
        c.print(f"[bold yellow]Warning:[/bold yellow] {message}")
    else:
        c.print(f"Warning: {message}")


def print_success(message: str, custom_console: Optional[Any] = None) -> None:
    """Print a standardized success message."""
    c = custom_console or console
    if HAS_RICH:
        c.print(f"[bold green]Success:[/bold green] {message}")
    else:
        c.print(f"Success: {message}")


def create_table(
    title: Optional[str] = None,
    header_style: str = "bold cyan",
    border_style: str = "bright_blue",
    expand: bool = True,
) -> Any:
    """Create a standardized Rich table or fallback DummyTable."""
    if HAS_RICH:
        return Table(
            title=title,
            box=box.ROUNDED,
            header_style=header_style,
            border_style=border_style,
            show_lines=False,
            expand=expand,
        )
    return DummyTable(title=title)


def create_panel(
    content: Any,
    title: Optional[str] = None,
    border_style: str = "bright_blue",
    padding: tuple = (0, 1),
) -> Any:
    """Create a standardized Rich panel or formatted text fallback."""
    if HAS_RICH:
        return Panel(
            content,
            title=title,
            border_style=border_style,
            box=box.ROUNDED,
            padding=padding,
        )
    clean_title = f"=== {_strip_tags(title)} ===\n" if title else ""
    return f"{clean_title}{content}"
