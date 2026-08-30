"""
Interactive AI-powered Git commit command handler for gitctl.
"""

from __future__ import annotations

import argparse
import os
import readline
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List, Optional, Tuple

from gitctl.core.ai_provider import generate_commit_message, get_available_providers
from gitctl.core.console import (
    create_panel,
    create_table,
    get_console,
    print_error,
    print_success,
    print_warning,
    status_spinner,
)

try:
    from rich.panel import Panel
    from rich.prompt import Confirm, Prompt
    from rich.syntax import Syntax
    from rich.text import Text
    HAS_RICH = True
except ImportError:
    HAS_RICH = False


def _run_git(args: List[str], cwd: Optional[Path] = None, check: bool = True) -> subprocess.CompletedProcess:
    """Execute a git command and return CompletedProcess."""
    return subprocess.run(
        ["git"] + args,
        cwd=cwd or Path.cwd(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=check,
    )


def is_git_repository(cwd: Optional[Path] = None) -> bool:
    """Check if directory is inside a Git repository."""
    try:
        res = _run_git(["rev-parse", "--is-inside-work-tree"], cwd=cwd, check=False)
        return res.returncode == 0 and res.stdout.strip() == "true"
    except Exception:
        return False


def get_staged_summary(cwd: Optional[Path] = None) -> Tuple[List[str], str, str]:
    """
    Get list of staged files, stat summary, and full cached diff.
    Returns (staged_files, stat_text, diff_text).
    """
    res_names = _run_git(["diff", "--cached", "--name-status"], cwd=cwd, check=False)
    staged_files = [line.strip() for line in res_names.stdout.splitlines() if line.strip()]

    res_stat = _run_git(["diff", "--cached", "--stat"], cwd=cwd, check=False)
    stat_text = res_stat.stdout.strip()

    res_diff = _run_git(["diff", "--cached"], cwd=cwd, check=False)
    diff_text = res_diff.stdout.strip()

    return staged_files, stat_text, diff_text


def get_unstaged_count(cwd: Optional[Path] = None) -> int:
    """Count number of unstaged tracked modifications."""
    res = _run_git(["diff", "--name-only"], cwd=cwd, check=False)
    return len([line for line in res.stdout.splitlines() if line.strip()])


def prompt_inline_edit(initial_text: str) -> str:
    """Prompt user to edit message with readline prefill in terminal."""
    def prefill_hook():
        readline.insert_text(initial_text)
        readline.redisplay()

    readline.set_pre_input_hook(prefill_hook)
    try:
        new_text = input("Edit commit message: ").strip()
    finally:
        readline.set_pre_input_hook()

    return new_text or initial_text


def prompt_editor_edit(initial_text: str) -> str:
    """Open user's configured editor ($EDITOR or git editor) to edit message."""
    editor = os.environ.get("GIT_EDITOR") or os.environ.get("EDITOR") or "nano"
    with tempfile.NamedTemporaryFile(suffix=".txt", mode="w+", delete=False) as tf:
        tf.write(initial_text)
        tf_path = tf.name

    try:
        subprocess.run([editor, tf_path], check=False)
        with open(tf_path, "r", encoding="utf-8") as f:
            content = f.read().strip()
        lines = [line.strip() for line in content.splitlines() if line.strip() and not line.startswith("#")]
        return lines[0] if lines else initial_text
    finally:
        if os.path.exists(tf_path):
            os.remove(tf_path)


def handle_commit_command(args: argparse.Namespace) -> int:
    """Execute the interactive AI commit workflow."""
    console = get_console(no_color=getattr(args, "no_color", False))
    cwd = Path.cwd()

    # 1. Verify Git repository
    if not is_git_repository(cwd):
        print_error("Current directory is not a Git repository.", custom_console=console)
        return 1

    # 2. Check if --all was requested to stage tracked changes automatically
    if getattr(args, "all", False):
        _run_git(["add", "-u"], cwd=cwd, check=False)

    # 3. Check staged changes
    staged_files, stat_text, diff_text = get_staged_summary(cwd)

    if not staged_files:
        unstaged = get_unstaged_count(cwd)
        if unstaged > 0:
            console.print("[bold yellow]No changes staged for commit, but unstaged modifications exist.[/bold yellow]")
            if not getattr(args, "yes", False):
                try:
                    choice = input("Stage all tracked modifications (`git add -u`)? [Y/n]: ").strip().lower()
                except (KeyboardInterrupt, EOFError):
                    console.print("\n[yellow]Aborted.[/yellow]")
                    return 1
                if choice in ("", "y", "yes"):
                    _run_git(["add", "-u"], cwd=cwd, check=False)
                    staged_files, stat_text, diff_text = get_staged_summary(cwd)
                else:
                    print_warning("No staged changes to commit. Use 'git add <files>' first.", custom_console=console)
                    return 0
            else:
                _run_git(["add", "-u"], cwd=cwd, check=False)
                staged_files, stat_text, diff_text = get_staged_summary(cwd)

        if not staged_files:
            print_warning("No staged changes found to commit. Use 'git add <files>' first.", custom_console=console)
            return 0

    # Display staged files summary
    file_list_text = "\n".join([f"  • [cyan]{f}[/cyan]" for f in staged_files[:10]])
    if len(staged_files) > 10:
        file_list_text += f"\n  ... and {len(staged_files) - 10} more files"

    console.print(create_panel(
        file_list_text,
        title=f"[bold]Staged Changes ({len(staged_files)} file{'s' if len(staged_files) != 1 else ''})[/bold]",
        border_style="cyan",
    ))

    provider_name = getattr(args, "provider", "auto")
    current_hint = getattr(args, "hint", None)
    commit_msg = ""
    provider_used = ""

    # Generation loop
    while True:
        try:
            with status_spinner(f"Generating commit message using AI ({provider_name})...", custom_console=console):
                commit_msg, provider_used = generate_commit_message(
                    diff_text=diff_text,
                    stat_text=stat_text,
                    hint=current_hint,
                    provider_name=provider_name,
                )
        except Exception as e:
            print_error(f"Failed to generate commit message: {e}", custom_console=console)
            return 1

        # Display suggested message
        console.print(create_panel(
            f"[bold green]{commit_msg}[/bold green]",
            title=f"[bold]Suggested Commit Message (via {provider_used})[/bold]",
            border_style="green",
        ))

        # Dry-run mode
        if getattr(args, "dry_run", False):
            console.print("[dim italic]Dry-run mode enabled: commit not executed.[/dim italic]")
            return 0

        # Auto-accept mode
        if getattr(args, "yes", False):
            break

        # Direct edit flag mode
        if getattr(args, "edit", False):
            commit_msg = prompt_inline_edit(commit_msg)
            break

        # Interactive selection menu
        console.print("[bold]Options:[/bold] [bold green]\\[a][/bold green] Accept & Commit  [bold cyan]\\[e][/bold cyan] Edit  [bold yellow]\\[r][/bold yellow] Regenerate  [bold blue]\\[h][/bold blue] Add Hint  [bold red]\\[c][/bold red] Cancel")
        try:
            choice = input("Select option [a/e/r/h/c] (default: a): ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[yellow]Commit aborted by user.[/yellow]")
            return 1

        if choice in ("", "a", "accept", "y", "yes"):
            break
        elif choice in ("e", "edit"):
            console.print("[dim]Edit inline (press Enter when done):[/dim]")
            commit_msg = prompt_inline_edit(commit_msg)
            # Confirm edited message
            console.print(f"[bold green]Updated Message:[/bold green] {commit_msg}")
            try:
                sub_choice = input("Commit with this message? [Y/n]: ").strip().lower()
            except (KeyboardInterrupt, EOFError):
                console.print("\n[yellow]Commit aborted.[/yellow]")
                return 1
            if sub_choice in ("", "y", "yes"):
                break
        elif choice in ("r", "retry", "regenerate"):
            console.print("[dim]Regenerating message...[/dim]")
            continue
        elif choice in ("h", "hint"):
            try:
                hint_input = input("Enter guidance/hint for AI: ").strip()
            except (KeyboardInterrupt, EOFError):
                console.print("\n[yellow]Commit aborted.[/yellow]")
                return 1
            if hint_input:
                current_hint = hint_input
            continue
        elif choice in ("c", "q", "cancel", "quit", "abort"):
            console.print("[yellow]Commit cancelled.[/yellow]")
            return 0
        else:
            console.print(f"[red]Unknown option '{choice}'.[/red]")
            continue

    # Execute git commit
    commit_cmd = ["commit", "-m", commit_msg]
    if getattr(args, "amend", False):
        commit_cmd.append("--amend")
    if getattr(args, "no_verify", False):
        commit_cmd.append("--no-verify")

    # Pass through any extra git commit flags
    extra_git_args = getattr(args, "git_args", [])
    if extra_git_args:
        commit_cmd.extend(extra_git_args)

    res = _run_git(commit_cmd, cwd=cwd, check=False)
    if res.returncode != 0:
        print_error(f"Git commit failed:\n{res.stderr.strip()}", custom_console=console)
        return res.returncode

    print_success(f"Committed successfully: [bold]{commit_msg}[/bold]", custom_console=console)
    if res.stdout.strip():
        console.print(f"[dim]{res.stdout.strip()}[/dim]")

    return 0
