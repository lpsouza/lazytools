"""
GitHub Repository Features audit and configuration command handler.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional

from gitctl.core.console import (
    create_panel,
    create_table,
    get_console,
    print_error,
    print_success,
    print_warning,
    status_spinner,
)
from gitctl.core.github_api import GitHubAPIError, GitHubClient

try:
    from rich.prompt import Confirm, Prompt
    HAS_RICH = True
except ImportError:
    HAS_RICH = False


FEATURE_KEYS = [
    ("Issues", "hasIssuesEnabled", "has_issues"),
    ("Wiki", "hasWikiEnabled", "has_wiki"),
    ("Projects", "hasProjectsEnabled", "has_projects"),
    ("Discussions", "hasDiscussionsEnabled", "has_discussions"),
    ("Archived", "isArchived", "archived"),
    ("Disabled", "isDisabled", "disabled"),
    ("Private", "isPrivate", "private"),
    ("Fork", "isFork", "is_fork"),
    ("Template", "isTemplate", "is_template"),
]


def audit_features(client: GitHubClient, args: argparse.Namespace) -> int:
    """Audit repository features across all repos for target owner."""
    console = get_console(no_color=getattr(args, "no_color", False))
    owner = getattr(args, "owner", None)

    try:
        user = client.get_authenticated_user()
        target_owner = owner or user

        with status_spinner(f"Fetching repositories for {target_owner}...", custom_console=console):
            repos = client.list_repositories(target_owner)
    except GitHubAPIError as e:
        print_error(str(e))
        return 1

    if not repos:
        print_warning(f"No repositories found for '{target_owner}'.")
        return 0

    # Fetch extra counts (releases, packages, deployments) concurrently
    extra_counts: Dict[str, Dict[str, int]] = {}
    with status_spinner(f"Auditing releases, packages, and deployments across {len(repos)} repos...", custom_console=console):
        with ThreadPoolExecutor(max_workers=8) as executor:
            future_to_repo = {
                executor.submit(client.get_repo_counts, r["nameWithOwner"]): r["nameWithOwner"]
                for r in repos
            }
            for future in as_completed(future_to_repo):
                name = future_to_repo[future]
                try:
                    extra_counts[name] = future.result()
                except Exception:
                    extra_counts[name] = {"releases": 0, "packages": 0, "deployments": 0}

    # JSON export
    if getattr(args, "json", False):
        enriched = []
        for r in repos:
            full_name = r["nameWithOwner"]
            item = dict(r)
            item["counts"] = extra_counts.get(full_name, {})
            enriched.append(item)
        print(json.dumps(enriched, indent=2))
        return 0

    # CSV export
    if getattr(args, "csv", False):
        output = io.StringIO()
        writer = csv.writer(output)
        headers = ["Repository", "Visibility", "Issues", "Wiki", "Projects", "Discussions", "Archived", "Private", "Releases", "Packages", "Deployments"]
        writer.writerow(headers)
        for r in repos:
            fn = r["nameWithOwner"]
            ec = extra_counts.get(fn, {})
            writer.writerow([
                fn,
                r.get("visibility", ""),
                "enabled" if r.get("hasIssuesEnabled") else "disabled",
                "enabled" if r.get("hasWikiEnabled") else "disabled",
                "enabled" if r.get("hasProjectsEnabled") else "disabled",
                "enabled" if r.get("hasDiscussionsEnabled") else "disabled",
                "yes" if r.get("isArchived") else "no",
                "yes" if r.get("isPrivate") else "no",
                ec.get("releases", 0),
                ec.get("packages", 0),
                ec.get("deployments", 0),
            ])
        print(output.getvalue(), end="")
        return 0

    # Rich Visual Table
    panel = create_panel(
        f"[bold cyan]Auditing repository features for {target_owner}[/bold cyan] [dim]({len(repos)} repositories)[/dim]",
        title="[bold]GitHub Features Audit[/bold]",
    )
    console.print()
    console.print(panel)
    console.print()

    table = create_table(expand=True)
    table.add_column("Repository", style="bold white", no_wrap=True)
    table.add_column("Visib", justify="center", no_wrap=True)
    table.add_column("Issues", justify="center", no_wrap=True)
    table.add_column("Wiki", justify="center", no_wrap=True)
    table.add_column("Projects", justify="center", no_wrap=True)
    table.add_column("Discuss", justify="center", no_wrap=True)
    table.add_column("Archived", justify="center", no_wrap=True)
    table.add_column("Releases", justify="center", no_wrap=True)
    table.add_column("Packages", justify="center", no_wrap=True)
    table.add_column("Deploys", justify="center", no_wrap=True)

    def _fmt_bool(val: Optional[bool]) -> str:
        return "[bold green]✔[/bold green]" if val else "[dim red]✘[/dim red]"

    for r in repos:
        fn = r["nameWithOwner"]
        ec = extra_counts.get(fn, {})

        vis = "[yellow]🔒 Pri[/yellow]" if r.get("isPrivate") else "[green]🌐 Pub[/green]"
        arch = "[bold yellow]Yes[/bold yellow]" if r.get("isArchived") else "[dim]No[/dim]"
        rel = f"[cyan]{ec.get('releases', 0)}[/cyan]" if ec.get("releases", 0) > 0 else "[dim]0[/dim]"
        pkg = f"[cyan]{ec.get('packages', 0)}[/cyan]" if ec.get("packages", 0) > 0 else "[dim]0[/dim]"
        dep = f"[cyan]{ec.get('deployments', 0)}[/cyan]" if ec.get("deployments", 0) > 0 else "[dim]0[/dim]"

        table.add_row(
            f"[bold]{r['name']}[/bold]",
            vis,
            _fmt_bool(r.get("hasIssuesEnabled")),
            _fmt_bool(r.get("hasWikiEnabled")),
            _fmt_bool(r.get("hasProjectsEnabled")),
            _fmt_bool(r.get("hasDiscussionsEnabled")),
            arch,
            rel,
            pkg,
            dep,
        )

    console.print(table)
    console.print()
    return 0


def config_features(client: GitHubClient, args: argparse.Namespace) -> int:
    """Interactively or declaratively configure features on a repository."""
    console = get_console(no_color=getattr(args, "no_color", False))
    repo_arg = getattr(args, "repo", None)

    try:
        user = client.get_authenticated_user()
        repos = client.list_repositories(user)
    except GitHubAPIError as e:
        print_error(str(e))
        return 1

    if not repos:
        print_error("No repositories found.")
        return 1

    selected_repo = None
    if repo_arg:
        for r in repos:
            if r["name"].lower() == repo_arg.lower() or r["nameWithOwner"].lower() == repo_arg.lower():
                selected_repo = r
                break
        if not selected_repo:
            print_error(f"Repository '{repo_arg}' not found.")
            return 1
    else:
        # Interactive selection
        console.print("[bold cyan]Available Repositories:[/bold cyan]")
        for idx, r in enumerate(repos, 1):
            console.print(f"  [yellow]{idx:2d})[/yellow] {r['nameWithOwner']}")

        choice = Prompt.ask("\nSelect repository number or name", default="1")
        if choice.isdigit() and 1 <= int(choice) <= len(repos):
            selected_repo = repos[int(choice) - 1]
        else:
            for r in repos:
                if r["name"].lower() == choice.lower() or r["nameWithOwner"].lower() == choice.lower():
                    selected_repo = r
                    break

    if not selected_repo:
        print_error("Invalid repository selection.")
        return 1

    full_name = selected_repo["nameWithOwner"]
    is_archived = selected_repo.get("isArchived", False)

    console.print(f"\n[bold green]Managing settings for:[/bold green] [bold white]{full_name}[/bold white]")
    if is_archived:
        print_warning("Repository is currently ARCHIVED. Modifying settings will temporarily unarchive and re-archive it.")

    # Current states
    current_issues = selected_repo.get("hasIssuesEnabled", False)
    current_wiki = selected_repo.get("hasWikiEnabled", False)
    current_projects = selected_repo.get("hasProjectsEnabled", False)
    current_discussions = selected_repo.get("hasDiscussionsEnabled", False)

    # If flags passed via CLI
    new_issues = getattr(args, "issues", None)
    new_wiki = getattr(args, "wiki", None)
    new_projects = getattr(args, "projects", None)
    new_discussions = getattr(args, "discussions", None)

    # If interactive
    if all(v is None for v in [new_issues, new_wiki, new_projects, new_discussions]):
        new_issues = Confirm.ask(f"Enable Issues? (currently {current_issues})", default=current_issues)
        new_wiki = Confirm.ask(f"Enable Wiki? (currently {current_wiki})", default=current_wiki)
        new_projects = Confirm.ask(f"Enable Projects? (currently {current_projects})", default=current_projects)
        new_discussions = Confirm.ask(f"Enable Discussions? (currently {current_discussions})", default=current_discussions)

    updates = {}
    if new_issues is not None and new_issues != current_issues:
        updates["has_issues"] = new_issues
    if new_wiki is not None and new_wiki != current_wiki:
        updates["has_wiki"] = new_wiki
    if new_projects is not None and new_projects != current_projects:
        updates["has_projects"] = new_projects
    if new_discussions is not None and new_discussions != current_discussions:
        updates["has_discussions"] = new_discussions

    if not updates:
        console.print("[dim]No changes requested.[/dim]")
        return 0

    console.print(f"[bold cyan]Applying changes to {full_name}:[/bold cyan] {updates}")
    try:
        client.update_repository_features(full_name, updates, is_archived=is_archived)
        print_success(f"Features updated successfully for {full_name}!")
        return 0
    except GitHubAPIError as e:
        print_error(f"Failed to update features: {e}")
        return 1


def handle_features_command(args: argparse.Namespace) -> int:
    """Entrypoint dispatcher for `gitctl github features [audit|config]`."""
    client = GitHubClient(timeout=getattr(args, "timeout", 15))
    action = getattr(args, "features_action", "audit")

    if action == "config":
        return config_features(client, args)
    return audit_features(client, args)
