"""
Unified console, formatting, and UI components for gitctl.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Generator, Optional

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


# Shared global console instance
console = Console()


def get_console(no_color: bool = False) -> Console:
    """Return a configured Console instance."""
    if no_color:
        return Console(no_color=True)
    return console


@contextmanager
def status_spinner(
    message: str,
    custom_console: Optional[Console] = None,
    spinner: str = "dots",
) -> Generator[None, None, None]:
    """Display an animated Rich spinner with message while executing code block."""
    c = custom_console or console
    if HAS_RICH and not c.no_color:
        with c.status(f"[bold cyan]{message}[/bold cyan]", spinner=spinner):
            yield
    else:
        yield


def print_error(message: str, custom_console: Optional[Console] = None) -> None:
    """Print a standardized error message."""
    c = custom_console or console
    if HAS_RICH:
        c.print(f"[bold red]Error:[/bold red] {message}")
    else:
        print(f"Error: {message}")


def print_warning(message: str, custom_console: Optional[Console] = None) -> None:
    """Print a standardized warning message."""
    c = custom_console or console
    if HAS_RICH:
        c.print(f"[bold yellow]Warning:[/bold yellow] {message}")
    else:
        print(f"Warning: {message}")


def print_success(message: str, custom_console: Optional[Console] = None) -> None:
    """Print a standardized success message."""
    c = custom_console or console
    if HAS_RICH:
        c.print(f"[bold green]Success:[/bold green] {message}")
    else:
        print(f"Success: {message}")


def create_table(
    title: Optional[str] = None,
    header_style: str = "bold cyan",
    border_style: str = "bright_blue",
    expand: bool = True,
) -> Table:
    """Create a standardized Rich table."""
    return Table(
        title=title,
        box=box.ROUNDED,
        header_style=header_style,
        border_style=border_style,
        show_lines=False,
        expand=expand,
    )


def create_panel(
    content,
    title: Optional[str] = None,
    border_style: str = "bright_blue",
    padding: tuple = (0, 1),
) -> Panel:
    """Create a standardized Rich panel."""
    return Panel(
        content,
        title=title,
        border_style=border_style,
        box=box.ROUNDED,
        padding=padding,
    )
