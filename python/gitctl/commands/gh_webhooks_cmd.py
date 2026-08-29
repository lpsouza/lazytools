"""
GitHub Webhooks audit, management, and cleanup command handler.
"""

from __future__ import annotations

import argparse
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


COMMON_EVENTS = [
    "push",
    "pull_request",
    "release",
    "issues",
    "workflow_run",
    "deployment",
    "create",
    "delete",
]


def audit_webhooks(client: GitHubClient, args: argparse.Namespace) -> int:
    """Scan all repositories, check webhook delivery logs, flag failing hooks."""
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

    # Gather webhooks concurrently
    repo_hooks: Dict[str, List[Dict[str, Any]]] = {}
    with status_spinner(f"Scanning webhooks across {len(repos)} repositories...", custom_console=console):
        with ThreadPoolExecutor(max_workers=8) as executor:
            future_to_repo = {
                executor.submit(client.list_webhooks, r["nameWithOwner"]): r["nameWithOwner"]
                for r in repos
            }
            for future in as_completed(future_to_repo):
                name = future_to_repo[future]
                try:
                    hooks = future.result()
                    if hooks:
                        repo_hooks[name] = hooks
                except Exception:
                    pass

    total_hooks = sum(len(h) for h in repo_hooks.values())

    if total_hooks == 0:
        print_success(f"Scanned {len(repos)} repositories. No webhooks found.")
        return 0

    # Inspect delivery statuses concurrently
    audited_hooks: List[Dict[str, Any]] = []

    def _inspect_hook(full_repo: str, hook: Dict[str, Any]) -> Dict[str, Any]:
        hook_id = hook["id"]
        url = hook.get("config", {}).get("url", "N/A")
        active = hook.get("active", True)
        events = hook.get("events", [])

        delivery_info = {"status_code": "N/A", "delivered_at": "N/A"}
        if active:
            delivery_info = client.get_last_delivery(full_repo, hook_id)

        status_code = delivery_info.get("status_code", "N/A")
        delivered_at = delivery_info.get("delivered_at", "N/A")

        is_failed = False
        if not active:
            health = "inactive"
        elif str(status_code).startswith("2"):
            health = "healthy"
        else:
            health = "failing"
            is_failed = True

        return {
            "repo": full_repo,
            "id": hook_id,
            "url": url,
            "active": active,
            "events": events,
            "status_code": status_code,
            "delivered_at": delivered_at,
            "health": health,
            "is_failed": is_failed,
        }

    with status_spinner(f"Inspecting delivery logs for {total_hooks} webhooks...", custom_console=console):
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = []
            for full_name, hooks in repo_hooks.items():
                for h in hooks:
                    futures.append(executor.submit(_inspect_hook, full_name, h))
            for f in as_completed(futures):
                audited_hooks.append(f.result())

    audited_hooks.sort(key=lambda x: (x["repo"], x["id"]))

    if getattr(args, "json", False):
        print(json.dumps(audited_hooks, indent=2))
        return 0

    # Render Table
    table = create_table(expand=True)
    table.add_column("Repository", style="bold white", no_wrap=True, ratio=25)
    table.add_column("Hook ID", justify="center", no_wrap=True, ratio=10)
    table.add_column("Status / Delivery", justify="center", no_wrap=True, ratio=18)
    table.add_column("Webhook Target URL", overflow="ellipsis", ratio=35)
    table.add_column("Events", no_wrap=True, ratio=12)

    failing_hooks = []

    for h in audited_hooks:
        if h["health"] == "healthy":
            status_text = f"[bold green]✔ 2xx[/bold green] [dim]({h['status_code']})[/dim]"
        elif h["health"] == "inactive":
            status_text = "[bold yellow]⚠ Inactive[/bold yellow]"
        else:
            status_text = f"[bold red]✖ Failed[/bold red] [red]({h['status_code']})[/red]"
            failing_hooks.append(h)

        events_str = ",".join(h["events"][:2]) + ("..." if len(h["events"]) > 2 else "")

        table.add_row(
            f"[bold]{h['repo']}[/bold]",
            str(h["id"]),
            status_text,
            h["url"],
            f"[cyan]{events_str}[/cyan]",
        )

    console.print(table)
    console.print()

    # Interactive Cleanup Offer
    if failing_hooks and getattr(args, "cleanup", False):
        console.print(f"[bold yellow]Found {len(failing_hooks)} failing or broken webhooks.[/bold yellow]")
        for fh in failing_hooks:
            if Confirm.ask(f"Delete broken hook {fh['id']} on {fh['repo']} ({fh['url']})?", default=False):
                try:
                    client.delete_webhook(fh["repo"], fh["id"])
                    print_success(f"Deleted webhook {fh['id']} on {fh['repo']}.")
                except GitHubAPIError as e:
                    print_error(f"Failed to delete hook: {e}")

    return 0


def list_webhooks(client: GitHubClient, args: argparse.Namespace) -> int:
    """List webhooks for a specific repository."""
    console = get_console(no_color=getattr(args, "no_color", False))
    repo_arg = getattr(args, "repo", None)

    try:
        user = client.get_authenticated_user()
        if not repo_arg:
            repos = client.list_repositories(user)
            console.print("[bold cyan]Select repository:[/bold cyan]")
            for idx, r in enumerate(repos, 1):
                console.print(f"  [yellow]{idx:2d})[/yellow] {r['nameWithOwner']}")
            choice = Prompt.ask("\nEnter repository number or name", default="1")
            if choice.isdigit() and 1 <= int(choice) <= len(repos):
                target_repo = repos[int(choice) - 1]["nameWithOwner"]
            else:
                target_repo = choice if "/" in choice else f"{user}/{choice}"
        else:
            target_repo = repo_arg if "/" in repo_arg else f"{user}/{repo_arg}"

        hooks = client.list_webhooks(target_repo)
    except GitHubAPIError as e:
        print_error(str(e))
        return 1

    if not hooks:
        console.print(f"[dim]No webhooks configured for {target_repo}.[/dim]")
        return 0

    table = create_table(expand=True)
    table.add_column("Hook ID", justify="center", no_wrap=True)
    table.add_column("Active", justify="center", no_wrap=True)
    table.add_column("Events", no_wrap=True)
    table.add_column("URL", overflow="ellipsis")

    for h in hooks:
        active_str = "[green]✔ Active[/green]" if h.get("active") else "[yellow]Inactive[/yellow]"
        events_str = ", ".join(h.get("events", []))
        url_str = h.get("config", {}).get("url", "N/A")
        table.add_row(str(h["id"]), active_str, events_str, url_str)

    console.print(f"\n[bold cyan]Webhooks for {target_repo}:[/bold cyan]")
    console.print(table)
    console.print()
    return 0


def add_webhook(client: GitHubClient, args: argparse.Namespace) -> int:
    """Add a new webhook to a repository."""
    console = get_console(no_color=getattr(args, "no_color", False))
    repo_arg = getattr(args, "repo", None)
    url_arg = getattr(args, "url", None)
    secret_arg = getattr(args, "secret", "")
    events_arg = getattr(args, "events", None)

    try:
        user = client.get_authenticated_user()
        if not repo_arg:
            repos = client.list_repositories(user)
            console.print("[bold cyan]Select repository to add webhook:[/bold cyan]")
            for idx, r in enumerate(repos, 1):
                console.print(f"  [yellow]{idx:2d})[/yellow] {r['nameWithOwner']}")
            choice = Prompt.ask("\nEnter repository number or name", default="1")
            if choice.isdigit() and 1 <= int(choice) <= len(repos):
                target_repo = repos[int(choice) - 1]["nameWithOwner"]
            else:
                target_repo = choice if "/" in choice else f"{user}/{choice}"
        else:
            target_repo = repo_arg if "/" in repo_arg else f"{user}/{repo_arg}"

        target_url = url_arg or Prompt.ask("Enter Webhook Payload URL (e.g. https://api.example.com/hook)")
        if not target_url.startswith(("http://", "https://")):
            print_error("Invalid URL: must start with http:// or https://")
            return 1

        if not secret_arg and getattr(args, "prompt_secret", False):
            secret_arg = Prompt.ask("Enter Webhook Secret (optional, press enter to skip)", default="", password=True)

        if not events_arg:
            events_input = Prompt.ask("Enter event types comma-separated (e.g. push,pull_request,release)", default="push")
            events_list = [e.strip() for e in events_input.split(",") if e.strip()]
        else:
            events_list = [e.strip() for e in events_arg.split(",") if e.strip()]

        console.print(f"\n[bold cyan]Creating webhook on {target_repo}...[/bold cyan]")
        result = client.create_webhook(
            full_name=target_repo,
            url=target_url,
            secret=secret_arg,
            events=events_list,
        )
        print_success(f"Webhook created successfully! ID: {result.get('id')}")
        return 0
    except GitHubAPIError as e:
        print_error(f"Failed to create webhook: {e}")
        return 1


def delete_webhook(client: GitHubClient, args: argparse.Namespace) -> int:
    """Delete a webhook from a repository."""
    console = get_console(no_color=getattr(args, "no_color", False))
    repo_arg = getattr(args, "repo", None)
    hook_id_arg = getattr(args, "id", None)

    try:
        user = client.get_authenticated_user()
        if not repo_arg:
            repos = client.list_repositories(user)
            console.print("[bold cyan]Select repository:[/bold cyan]")
            for idx, r in enumerate(repos, 1):
                console.print(f"  [yellow]{idx:2d})[/yellow] {r['nameWithOwner']}")
            choice = Prompt.ask("\nEnter repository number or name", default="1")
            if choice.isdigit() and 1 <= int(choice) <= len(repos):
                target_repo = repos[int(choice) - 1]["nameWithOwner"]
            else:
                target_repo = choice if "/" in choice else f"{user}/{choice}"
        else:
            target_repo = repo_arg if "/" in repo_arg else f"{user}/{repo_arg}"

        if not hook_id_arg:
            hooks = client.list_webhooks(target_repo)
            if not hooks:
                console.print(f"[dim]No webhooks found for {target_repo}.[/dim]")
                return 0

            console.print(f"\n[bold cyan]Webhooks on {target_repo}:[/bold cyan]")
            for idx, h in enumerate(hooks, 1):
                url = h.get("config", {}).get("url", "N/A")
                console.print(f"  [yellow]{idx:2d})[/yellow] ID: {h['id']} - URL: {url}")

            choice = Prompt.ask("\nEnter webhook number or ID to delete")
            if choice.isdigit():
                if 1 <= int(choice) <= len(hooks):
                    target_id = hooks[int(choice) - 1]["id"]
                else:
                    target_id = int(choice)
            else:
                print_error("Invalid selection.")
                return 1
        else:
            target_id = int(hook_id_arg)

        if Confirm.ask(f"Are you sure you want to delete webhook {target_id} on {target_repo}?", default=False):
            client.delete_webhook(target_repo, target_id)
            print_success(f"Webhook {target_id} deleted successfully.")
        else:
            console.print("[dim]Aborted.[/dim]")
        return 0
    except GitHubAPIError as e:
        print_error(f"Failed to delete webhook: {e}")
        return 1


def handle_webhooks_command(args: argparse.Namespace) -> int:
    """Entrypoint dispatcher for `gitctl github webhooks [audit|list|add|delete]`."""
    client = GitHubClient(timeout=getattr(args, "timeout", 15))
    action = getattr(args, "webhooks_action", "audit")

    if action == "list":
        return list_webhooks(client, args)
    elif action == "add":
        return add_webhook(client, args)
    elif action == "delete":
        return delete_webhook(client, args)
    return audit_webhooks(client, args)
