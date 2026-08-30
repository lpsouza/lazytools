"""
Main CLI argument parser and command router for gitctl.
"""

from __future__ import annotations

import argparse
import sys
from typing import List, Optional

from gitctl import __version__
from gitctl.commands.commit_cmd import handle_commit_command
from gitctl.commands.gh_features_cmd import handle_features_command
from gitctl.commands.gh_topics_cmd import handle_topics_command
from gitctl.commands.gh_webhooks_cmd import handle_webhooks_command
from gitctl.commands.local_cmd import handle_local_command


def build_parser() -> argparse.ArgumentParser:
    """Build comprehensive argparse hierarchy for gitctl."""
    parser = argparse.ArgumentParser(
        prog="gitctl",
        description="Unified Git & GitHub CLI Management Tool.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Scopes:
  gitctl commit               Generate AI commit message and commit interactively
  gitctl local                Operations on local repositories (~/projects)
  gitctl github (or remote)   Operations on remote GitHub repositories via API

Quick Examples:
  gitctl commit               Interactive AI commit from staged changes
  gitctl commit -y            Auto-accept AI commit message
  gitctl commit --hint "..."  Provide custom hint/guidance to AI
  gitctl status               Quick audit of local workspace repositories
  gitctl local status -f      Fetch all remotes in parallel and audit local repos
  gitctl local dirty          Show only local repositories with uncommitted changes
  gitctl github features      Audit features (issues, wiki, etc.) across all repos
  gitctl github topics        Audit topics assigned to GitHub repositories
  gitctl github webhooks      Audit webhook health and delivery failures
""",
    )

    parser.add_argument(
        "-v", "--version",
        action="version",
        version=f"gitctl {__version__}",
        help="Show gitctl version and exit.",
    )

    subparsers = parser.add_subparsers(dest="subcommand", title="Commands", metavar="<command>")

    # --- Top-level: `commit` (aliases: `ci`, `ai-commit`) ---
    commit_parser = subparsers.add_parser(
        "commit",
        aliases=["ci", "ai-commit"],
        help="Analyze staged changes and commit interactively using AI",
    )
    _add_commit_args(commit_parser)

    # --- Shortcut: `status` at root ---
    status_parser = subparsers.add_parser(
        "status",
        help="Quick shortcut for 'gitctl local status'",
    )
    _add_local_args(status_parser)

    # --- Scope 1: `local` (alias: `ws`) ---
    local_parser = subparsers.add_parser(
        "local",
        aliases=["ws"],
        help="Manage and audit local Git repositories on filesystem",
    )
    local_sub = local_parser.add_subparsers(dest="local_action", title="Local Actions", metavar="<action>")

    # local status
    l_status = local_sub.add_parser("status", help="Audit local workspace repositories")
    _add_local_args(l_status)

    # local dirty
    l_dirty = local_sub.add_parser("dirty", help="Show only repos with uncommitted/untracked changes")
    _add_local_args(l_dirty)

    # local unpushed
    l_unpushed = local_sub.add_parser("unpushed", help="Show only repos with unpushed commits (ahead of upstream)")
    _add_local_args(l_unpushed)

    # local commit
    l_commit = local_sub.add_parser(
        "commit",
        aliases=["ci", "ai-commit"],
        help="Analyze staged changes and commit interactively using AI",
    )
    _add_commit_args(l_commit)

    # Set default for local without action
    _add_local_args(local_parser)

    # --- Scope 2: `github` (aliases: `remote`, `gh`) ---
    gh_parser = subparsers.add_parser(
        "github",
        aliases=["remote", "gh"],
        help="Manage and audit remote GitHub repositories via API",
    )
    gh_sub = gh_parser.add_subparsers(dest="github_action", title="GitHub Actions", metavar="<action>")

    # 1. Features
    feat_parser = gh_sub.add_parser("features", help="Audit or configure repository features (Issues, Wiki, etc.)")
    feat_sub = feat_parser.add_subparsers(dest="features_action", title="Features Actions", metavar="<action>")
    
    f_audit = feat_sub.add_parser("audit", help="Audit features across repositories")
    _add_gh_common_args(f_audit)
    f_audit.add_argument("--csv", action="store_true", help="Output audit report in CSV format")

    f_config = feat_sub.add_parser("config", help="Interactively or declaratively configure features")
    _add_gh_common_args(f_config)
    f_config.add_argument("-r", "--repo", help="Target repository name or owner/name")
    f_config.add_argument("--issues", type=_str_to_bool, help="Enable or disable Issues (true/false)")
    f_config.add_argument("--wiki", type=_str_to_bool, help="Enable or disable Wiki (true/false)")
    f_config.add_argument("--projects", type=_str_to_bool, help="Enable or disable Projects (true/false)")
    f_config.add_argument("--discussions", type=_str_to_bool, help="Enable or disable Discussions (true/false)")

    _add_gh_common_args(feat_parser)

    # 2. Topics
    top_parser = gh_sub.add_parser("topics", help="Audit repository topics")
    top_sub = top_parser.add_subparsers(dest="topics_action", title="Topics Actions", metavar="<action>")
    t_audit = top_sub.add_parser("audit", help="Audit repository topics")
    _add_gh_common_args(t_audit)
    t_audit.add_argument("-m", "--missing", action="store_true", help="Filter: show only repositories missing topics")
    t_audit.add_argument("-t", "--topic", help="Filter: show only repositories matching specified topic")

    _add_gh_common_args(top_parser)
    top_parser.add_argument("-m", "--missing", action="store_true", help="Filter: show only repositories missing topics")
    top_parser.add_argument("-t", "--topic", help="Filter: show only repositories matching specified topic")

    # 3. Webhooks
    hook_parser = gh_sub.add_parser("webhooks", help="Manage and audit repository webhooks")
    hook_sub = hook_parser.add_subparsers(dest="webhooks_action", title="Webhooks Actions", metavar="<action>")

    h_audit = hook_sub.add_parser("audit", help="Scan webhooks and flag delivery failures")
    _add_gh_common_args(h_audit)
    h_audit.add_argument("-c", "--cleanup", action="store_true", help="Offer interactive cleanup for failing hooks")

    h_list = hook_sub.add_parser("list", help="List webhooks for a repository")
    _add_gh_common_args(h_list)
    h_list.add_argument("-r", "--repo", help="Target repository name or owner/name")

    h_add = hook_sub.add_parser("add", help="Add a new webhook to a repository")
    _add_gh_common_args(h_add)
    h_add.add_argument("-r", "--repo", help="Target repository name or owner/name")
    h_add.add_argument("-u", "--url", help="Webhook payload target URL")
    h_add.add_argument("-s", "--secret", default="", help="Webhook payload secret")
    h_add.add_argument("-e", "--events", help="Comma-separated events list (e.g. push,pull_request)")

    h_delete = hook_sub.add_parser("delete", help="Delete a webhook from a repository")
    _add_gh_common_args(h_delete)
    h_delete.add_argument("-r", "--repo", help="Target repository name or owner/name")
    h_delete.add_argument("--id", help="Webhook ID to delete")

    _add_gh_common_args(hook_parser)
    hook_parser.add_argument("-c", "--cleanup", action="store_true", help="Offer interactive cleanup for failing hooks")

    return parser


def _str_to_bool(value: str) -> bool:
    """Convert string to boolean."""
    if isinstance(value, bool):
        return value
    if value.lower() in ("yes", "true", "t", "y", "1"):
        return True
    elif value.lower() in ("no", "false", "f", "n", "0"):
        return False
    raise argparse.ArgumentTypeError(f"Boolean value expected, got '{value}'.")


def _add_local_args(p: argparse.ArgumentParser) -> None:
    """Add standard arguments for local workspace operations."""
    p.add_argument("positional_path", nargs="?", default=None, help="Target workspace path (default: ~/projects)")
    p.add_argument("-p", "--path", help="Target workspace directory")
    p.add_argument("-f", "--fetch", action="store_true", help="Fetch remotes in parallel before auditing")
    p.add_argument("-d", "--dirty", action="store_true", help="Filter: show only dirty repositories")
    p.add_argument("-u", "--unpushed", "--ahead", action="store_true", help="Filter: show only repos with unpushed commits")
    p.add_argument("--unpulled", "--behind", action="store_true", help="Filter: show only repos with unpulled commits")
    p.add_argument("-a", "--all", action="store_true", help="Include non-Git directories in report")
    p.add_argument("-r", "--recursive", action="store_true", help="Scan subdirectories recursively")
    p.add_argument("--depth", type=int, default=3, help="Max directory scan depth (default: 3)")
    p.add_argument("--timeout", type=int, default=5, help="Timeout in seconds for git operations (default: 5)")
    p.add_argument("--threads", type=int, default=8, help="Worker threads for parallel scan (default: 8)")
    p.add_argument("--json", action="store_true", help="Output in JSON format")
    p.add_argument("--csv", action="store_true", help="Output in CSV format")
    p.add_argument("--no-color", action="store_true", help="Disable ANSI color output")


def _add_commit_args(p: argparse.ArgumentParser) -> None:
    """Add standard arguments for AI commit operations."""
    p.add_argument("-y", "--yes", action="store_true", help="Auto-accept AI commit message without interactive prompt")
    p.add_argument("-e", "--edit", action="store_true", help="Edit message before committing")
    p.add_argument("-p", "--provider", choices=["auto", "agy", "copilot"], default="auto", help="AI provider (default: auto)")
    p.add_argument("--hint", help="Custom guidance or context for AI commit generator")
    p.add_argument("--dry-run", action="store_true", help="Generate and display commit message without executing git commit")
    p.add_argument("-a", "--all", action="store_true", help="Stage all modified/deleted tracked files before committing")
    p.add_argument("--amend", action="store_true", help="Amend previous commit")
    p.add_argument("--no-verify", action="store_true", help="Bypass git pre-commit hooks")
    p.add_argument("--no-color", action="store_true", help="Disable ANSI color output")
    p.add_argument("git_args", nargs=argparse.REMAINDER, help="Additional arguments forwarded to git commit")


def _add_gh_common_args(p: argparse.ArgumentParser) -> None:
    """Add standard arguments for GitHub operations."""
    p.add_argument("-o", "--owner", help="GitHub owner / organization (default: authenticated user)")
    p.add_argument("--timeout", type=int, default=15, help="API timeout in seconds (default: 15)")
    p.add_argument("--json", action="store_true", help="Output in JSON format")
    p.add_argument("--no-color", action="store_true", help="Disable ANSI color output")


def main(argv: Optional[List[str]] = None) -> int:
    """CLI Main entrypoint."""
    parser = build_parser()
    args = parser.parse_args(argv)

    # 1. No subcommand provided (e.g. `gitctl`) -> show main help
    if not args.subcommand:
        parser.print_help()
        return 0

    # 2. Explicit top-level shortcut: `gitctl commit`
    if args.subcommand in ("commit", "ci", "ai-commit"):
        return handle_commit_command(args)

    # 3. Explicit top-level shortcut: `gitctl status`
    if args.subcommand == "status":
        return handle_local_command(args)

    # 4. Local scope: `gitctl local [status|dirty|unpushed|commit]`
    if args.subcommand in ("local", "ws"):
        local_action = getattr(args, "local_action", None)
        if local_action in ("commit", "ci", "ai-commit"):
            return handle_commit_command(args)

        if not local_action:
            # If user ran `gitctl local` without action, print local help
            # (unless specific flags like -d, -u, -f, --path were passed)
            has_flags = any([
                getattr(args, "path", None),
                getattr(args, "positional_path", None),
                getattr(args, "fetch", False),
                getattr(args, "dirty", False),
                getattr(args, "unpushed", False),
                getattr(args, "unpulled", False),
                getattr(args, "json", False),
                getattr(args, "csv", False),
            ])
            if not has_flags:
                parser.parse_args([args.subcommand, "--help"])
                return 0
        return handle_local_command(args)

    # 5. GitHub scope: `gitctl github [features|topics|webhooks]`
    if args.subcommand in ("github", "remote", "gh"):
        gh_action = getattr(args, "github_action", None)
        if not gh_action:
            parser.parse_args([args.subcommand, "--help"])
            return 0

        if gh_action == "features":
            return handle_features_command(args)
        elif gh_action == "topics":
            return handle_topics_command(args)
        elif gh_action == "webhooks":
            return handle_webhooks_command(args)
        else:
            parser.parse_args([args.subcommand, "--help"])
            return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
