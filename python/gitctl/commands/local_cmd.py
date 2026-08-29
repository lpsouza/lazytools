"""
Local workspace Git status and audit command handler.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
from pathlib import Path
from typing import List

from gitctl.core.console import create_panel, create_table, get_console, print_error, status_spinner
from gitctl.core.git_local import GitScanner, RepoAuditResult

try:
    from rich import box
    from rich.table import Table
    from rich.text import Text
    HAS_RICH = True
except ImportError:
    HAS_RICH = False


def _format_short_url(url: str) -> str:
    """Shorten git URL for clean table display."""
    if not url:
        return ""
    clean = url.replace("https://", "").replace("http://", "").replace("ssh://", "")
    if clean.startswith("git@"):
        clean = clean[4:].replace(":", "/", 1)
    if clean.endswith(".git"):
        clean = clean[:-4]
    return clean


def render_local_rich(
    results: List[RepoAuditResult],
    target_path: Path,
    fetched: bool,
    show_all: bool = False,
    no_color: bool = False,
) -> None:
    """Render Rich dashboard and table for local repositories."""
    console = get_console(no_color=no_color)

    # Metrics aggregation
    total_dirs = len(results)
    git_repos = [r for r in results if r.is_git]
    total_repos = len(git_repos)
    clean_count = sum(1 for r in git_repos if r.working_tree.is_clean)
    dirty_count = total_repos - clean_count
    synced_count = sum(1 for r in git_repos if r.remote_sync.sync_state == "synced")
    ahead_count = sum(1 for r in git_repos if r.remote_sync.sync_state == "ahead")
    behind_count = sum(1 for r in git_repos if r.remote_sync.sync_state == "behind")
    diverged_count = sum(1 for r in git_repos if r.remote_sync.sync_state == "diverged")
    no_upstream_count = sum(
        1 for r in git_repos if r.remote_sync.sync_state in ("no_upstream", "no_remote")
    )

    # Header Grid & Summary Panel
    grid = Table.grid(padding=(0, 2))
    grid.add_column(style="bold cyan")
    grid.add_column()
    grid.add_column(style="bold yellow")
    grid.add_column()
    grid.add_column(style="bold green")
    grid.add_column()

    mode_badge = "[bold green]Online (Fetched Remotes)[/bold green]" if fetched else "[dim]Cached Local Refs[/dim]"

    grid.add_row(
        "📁 Workspace:",
        f"{target_path} [dim]({total_repos} repos)[/dim]",
        "🌳 Working Tree:",
        f"[bold green]✔ {clean_count} Clean[/bold green]   [bold yellow]✎ {dirty_count} Dirty[/bold yellow]",
        "🌐 Remote Sync:",
        f"[bold green]✔ {synced_count} Synced[/bold green]  [bold blue]↑ {ahead_count} Ahead[/bold blue]  [bold red]↓ {behind_count} Behind[/bold red]  [bold magenta]⇅ {diverged_count} Diverged[/bold magenta]  [dim yellow]⚠ {no_upstream_count} No Upstream[/dim yellow]",
    )

    panel = create_panel(
        grid,
        title=f"[bold cyan]gitctl • Local Workspace Audit[/bold cyan] [dim]({mode_badge})[/dim]",
        border_style="bright_blue",
    )

    console.print()
    console.print(panel)
    console.print()

    # Table View
    table = create_table(expand=True)
    table.add_column("Repository", style="bold white", no_wrap=True, ratio=20)
    table.add_column("Branch", no_wrap=True, ratio=15)
    table.add_column("Working Tree", no_wrap=True, ratio=25)
    table.add_column("Remote Sync", no_wrap=True, ratio=18)
    table.add_column("Stash", justify="center", no_wrap=True, ratio=6)
    table.add_column("Remote / Upstream", overflow="ellipsis", ratio=26)

    for r in results:
        if not r.is_git:
            if show_all:
                table.add_row(
                    f"[dim]{r.name}[/dim]",
                    "[dim]—[/dim]",
                    "[dim red]✖ Not a git repository[/dim red]",
                    "[dim]—[/dim]",
                    "[dim]0[/dim]",
                    "[dim]—[/dim]",
                )
            continue

        repo_style = "bold white"
        if not r.working_tree.is_clean or r.remote_sync.sync_state in ("behind", "diverged"):
            repo_style = "bold yellow"
        repo_text = f"[{repo_style}]{r.name}[/{repo_style}]"

        if r.is_detached:
            branch_text = f"[yellow]detached:{r.branch}[/yellow]"
        elif r.branch in ("main", "master"):
            branch_text = f"[bold green]{r.branch}[/bold green]"
        else:
            branch_text = f"[cyan]{r.branch}[/cyan]"

        if r.working_tree.is_clean:
            wt_text = "[bold green]✔ Clean[/bold green]"
        else:
            parts = []
            if r.working_tree.staged > 0:
                parts.append(f"[bold green]● {r.working_tree.staged} staged[/bold green]")
            if r.working_tree.unstaged > 0:
                parts.append(f"[bold yellow]+ {r.working_tree.unstaged} mod[/bold yellow]")
            if r.working_tree.untracked > 0:
                parts.append(f"[dim yellow]? {r.working_tree.untracked} untracked[/dim yellow]")
            if r.working_tree.conflicted > 0:
                parts.append(f"[bold red]✖ {r.working_tree.conflicted} conflict[/bold red]")
            wt_text = f"[yellow]✎ Dirty[/yellow] ({', '.join(parts)})"

        sync_state = r.remote_sync.sync_state
        if sync_state == "synced":
            sync_text = "[bold green]✔ Synced[/bold green]"
        elif sync_state == "ahead":
            sync_text = f"[bold blue]↑ {r.remote_sync.ahead} Ahead[/bold blue]"
        elif sync_state == "behind":
            sync_text = f"[bold red]↓ {r.remote_sync.behind} Behind[/bold red]"
        elif sync_state == "diverged":
            sync_text = f"[bold magenta]⇅ Diverged (+{r.remote_sync.ahead}/-{r.remote_sync.behind})[/bold magenta]"
        elif sync_state == "no_upstream":
            sync_text = "[bold yellow]⚠ No Upstream[/bold yellow]"
        else:
            sync_text = "[dim]No Remote[/dim]"

        if r.remote_sync.fetch_error:
            sync_text += f" [dim red]({r.remote_sync.fetch_error})[/dim red]"

        stash_text = f"[yellow]{r.working_tree.stashes}[/yellow]" if r.working_tree.stashes > 0 else "[dim]0[/dim]"

        remote_info = _format_short_url(r.remote_sync.remote_url)
        if not remote_info and r.remote_sync.upstream:
            remote_info = r.remote_sync.upstream
        remote_display = f"[dim]{remote_info}[/dim]" if remote_info else "[dim]—[/dim]"

        table.add_row(
            repo_text,
            branch_text,
            wt_text,
            sync_text,
            stash_text,
            remote_display,
        )

    console.print(table)
    console.print()


def render_local_plain(
    results: List[RepoAuditResult],
    target_path: Path,
    fetched: bool,
    show_all: bool = False,
) -> None:
    """Render plain text table without rich formatting."""
    print(f"gitctl Local Workspace Audit: {target_path.resolve()} (Fetched: {fetched})")
    print("-" * 100)
    print(f"{'Repository':<24} | {'Branch':<15} | {'Local Status':<28} | {'Remote Sync':<20} | {'Stashes':<7}")
    print("-" * 100)

    for r in results:
        if not r.is_git:
            if show_all:
                print(f"{r.name:<24} | {'-':<15} | {'Not a git repo':<28} | {'-':<20} | {'0':<7}")
            continue

        wt = "Clean" if r.working_tree.is_clean else f"Dirty (+{r.working_tree.staged} ~{r.working_tree.unstaged} ?{r.working_tree.untracked})"
        sync = r.remote_sync.sync_state
        if sync == "ahead":
            sync = f"Ahead (+{r.remote_sync.ahead})"
        elif sync == "behind":
            sync = f"Behind (-{r.remote_sync.behind})"
        elif sync == "diverged":
            sync = f"Diverged (+{r.remote_sync.ahead}/-{r.remote_sync.behind})"

        print(f"{r.name:<24} | {r.branch:<15} | {wt:<28} | {sync:<20} | {r.working_tree.stashes:<7}")
    print("-" * 100)


def render_local_json(results: List[RepoAuditResult]) -> str:
    """Export local results as JSON."""
    return json.dumps([r.to_dict() for r in results], indent=2)


def render_local_csv(results: List[RepoAuditResult]) -> str:
    """Export local results as CSV."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Repository", "Path", "IsGit", "Branch", "IsClean", "Staged", "Unstaged",
        "Untracked", "Conflicted", "Stashes", "SyncState", "Ahead", "Behind", "Upstream", "RemoteURL"
    ])
    for r in results:
        if not r.is_git:
            writer.writerow([r.name, r.path, False, "", "", "", "", "", "", "", "", "", "", "", ""])
            continue
        writer.writerow([
            r.name, r.path, True, r.branch, r.working_tree.is_clean,
            r.working_tree.staged, r.working_tree.unstaged, r.working_tree.untracked,
            r.working_tree.conflicted, r.working_tree.stashes, r.remote_sync.sync_state,
            r.remote_sync.ahead, r.remote_sync.behind, r.remote_sync.upstream, r.remote_sync.remote_url
        ])
    return output.getvalue()


def resolve_path(raw_path: Optional[str]) -> Path:
    """Resolve target workspace path from argument, env, or default ~/projects."""
    p = raw_path or os.getenv("PROJECTS_DIR") or os.getenv("LAZYTOOLS_PROJECTS_DIR") or "~/projects"
    return Path(os.path.expanduser(p)).resolve()


def handle_local_command(args: argparse.Namespace) -> int:
    """Main handler for `gitctl local [status|dirty|unpushed]`."""
    target_path = resolve_path(getattr(args, "path", None) or getattr(args, "positional_path", None))

    if not target_path.exists():
        print_error(f"Target directory '{target_path}' does not exist.")
        return 1

    if not target_path.is_dir():
        print_error(f"Target path '{target_path}' is not a directory.")
        return 1

    # Detect shortcuts from subcommand name
    subcmd = getattr(args, "local_action", "status")
    show_dirty_only = getattr(args, "dirty", False) or subcmd == "dirty"
    show_unpushed_only = getattr(args, "unpushed", False) or subcmd == "unpushed"
    show_unpulled_only = getattr(args, "unpulled", False)

    scanner = GitScanner(timeout=getattr(args, "timeout", 5))
    is_fetching = getattr(args, "fetch", False)
    spinner_msg = f"Fetching remotes & auditing repositories in {target_path}..." if is_fetching else f"Scanning local repositories in {target_path}..."

    with status_spinner(spinner_msg, custom_console=get_console(getattr(args, "no_color", False))):
        results = scanner.audit_workspace(
            target_path=target_path,
            do_fetch=is_fetching,
            recursive=getattr(args, "recursive", False),
            max_depth=getattr(args, "depth", 1),
            threads=getattr(args, "threads", 8),
        )

    if not results:
        print_error(f"No subdirectories or Git repositories found in '{target_path}'.")
        return 0

    # Apply filters
    filtered_results = results
    if show_dirty_only:
        filtered_results = [r for r in filtered_results if r.is_git and not r.working_tree.is_clean]
    if show_unpushed_only:
        filtered_results = [r for r in filtered_results if r.is_git and r.remote_sync.ahead > 0]
    if show_unpulled_only:
        filtered_results = [r for r in filtered_results if r.is_git and r.remote_sync.behind > 0]

    if getattr(args, "json", False):
        print(render_local_json(filtered_results))
    elif getattr(args, "csv", False):
        print(render_local_csv(filtered_results), end="")
    else:
        if HAS_RICH and not getattr(args, "no_rich", False):
            render_local_rich(
                filtered_results,
                target_path=target_path,
                fetched=getattr(args, "fetch", False),
                show_all=getattr(args, "all", False),
                no_color=getattr(args, "no_color", False),
            )
        else:
            render_local_plain(
                filtered_results,
                target_path=target_path,
                fetched=getattr(args, "fetch", False),
                show_all=getattr(args, "all", False),
            )

    return 0
