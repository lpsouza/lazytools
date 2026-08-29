"""
GitHub Repository Topics audit command handler.
"""

from __future__ import annotations

import argparse
import json
from typing import Any, Dict, List

from gitctl.core.console import create_panel, create_table, get_console, print_error, print_warning, status_spinner
from gitctl.core.github_api import GitHubAPIError, GitHubClient


def handle_topics_command(args: argparse.Namespace) -> int:
    """Audit topics across all repositories for target owner."""
    console = get_console(no_color=getattr(args, "no_color", False))
    client = GitHubClient(timeout=getattr(args, "timeout", 15))
    owner = getattr(args, "owner", None)

    try:
        user = client.get_authenticated_user()
        target_owner = owner or user
        with status_spinner(f"Fetching repository topics for {target_owner}...", custom_console=console):
            repos = client.list_repositories(target_owner)
    except GitHubAPIError as e:
        print_error(str(e))
        return 1

    if not repos:
        print_warning(f"No repositories found for '{target_owner}'.")
        return 0

    # Extract topics
    repo_topics: List[Dict[str, Any]] = []
    all_unique_topics = set()
    no_topics_count = 0

    for r in repos:
        name = r["nameWithOwner"]
        topics_nodes = r.get("repositoryTopics", [])
        if isinstance(topics_nodes, list):
            topics = [t["name"] if isinstance(t, dict) and "name" in t else str(t) for t in topics_nodes]
        else:
            topics = []

        if not topics:
            no_topics_count += 1
        else:
            all_unique_topics.update(topics)

        repo_topics.append({
            "name": r["name"],
            "full_name": name,
            "is_private": r.get("isPrivate", False),
            "topics": topics,
        })

    # Apply filters
    filtered = repo_topics
    if getattr(args, "missing", False):
        filtered = [r for r in filtered if not r["topics"]]
    if getattr(args, "topic", None):
        target_topic = getattr(args, "topic").lower()
        filtered = [r for r in filtered if any(t.lower() == target_topic for t in r["topics"])]

    if getattr(args, "json", False):
        print(json.dumps(filtered, indent=2))
        return 0

    # Rich Visual Table & Summary Panel
    panel = create_panel(
        f"[bold cyan]Topics Audit for {target_owner}[/bold cyan]\n"
        f"[white]Total Repos: {len(repos)}  •  With Topics: {len(repos) - no_topics_count}  •  Without Topics: {no_topics_count}  •  Unique Topics: {len(all_unique_topics)}[/white]",
        title="[bold]GitHub Topics Audit[/bold]",
    )

    console.print()
    console.print(panel)
    console.print()

    table = create_table(expand=True)
    table.add_column("Repository", style="bold white", no_wrap=True, ratio=30)
    table.add_column("Type", justify="center", no_wrap=True, ratio=10)
    table.add_column("Topics", ratio=60)

    for r in filtered:
        vis = "[yellow]🔒 Private[/yellow]" if r["is_private"] else "[green]🌐 Public[/green]"
        if r["topics"]:
            topics_str = " ".join([f"[cyan]#{t}[/cyan]" for t in r["topics"]])
        else:
            topics_str = "[dim yellow]NO TOPICS[/dim yellow]"

        table.add_row(f"[bold]{r['name']}[/bold]", vis, topics_str)

    console.print(table)
    console.print()
    return 0
