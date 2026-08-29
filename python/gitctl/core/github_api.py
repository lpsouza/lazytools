"""
GitHub API Client wrapper leveraging the local authenticated `gh` CLI.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


class GitHubAPIError(Exception):
    """Exception raised for GitHub API / gh CLI failures."""
    pass


class GitHubClient:
    """High-level GitHub API client using `gh` CLI for authentication & token safety."""

    def __init__(self, timeout: int = 15):
        self.timeout = timeout
        self._ensure_installed()

    def _ensure_installed(self) -> None:
        """Check if `gh` CLI is installed and in PATH."""
        if not shutil.which("gh"):
            raise GitHubAPIError(
                "GitHub CLI ('gh') is not installed or not in PATH.\n"
                "Please install GitHub CLI and authenticate using 'gh auth login'."
            )

    def run_gh(self, args: List[str], check_auth: bool = True) -> str:
        """Execute a `gh` command and return stdout."""
        cmd = ["gh"] + args
        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=False,
            )
            if res.returncode != 0:
                err_msg = res.stderr.strip() or res.stdout.strip() or f"Command failed with code {res.returncode}"
                raise GitHubAPIError(err_msg)
            return res.stdout.strip()
        except subprocess.TimeoutExpired:
            raise GitHubAPIError(f"GitHub command timed out after {self.timeout}s: {' '.join(cmd)}")
        except Exception as e:
            raise GitHubAPIError(str(e))

    def get_authenticated_user(self) -> str:
        """Return the login of currently authenticated GitHub user."""
        try:
            output = self.run_gh(["api", "user", "--jq", ".login"])
            if not output:
                raise GitHubAPIError("Empty user response from GitHub API.")
            return output
        except Exception as e:
            raise GitHubAPIError(f"Failed to authenticate with GitHub CLI: {e}\nRun 'gh auth login'.")

    def list_repositories(self, owner: Optional[str] = None) -> List[Dict[str, Any]]:
        """List repositories for specified owner or current user with pagination."""
        current_user = self.get_authenticated_user()
        target_owner = owner or current_user

        output = self.run_gh([
            "repo", "list", target_owner,
            "--limit", "300",
            "--json", "name,nameWithOwner,isPrivate,isArchived,isFork,isTemplate,visibility,hasIssuesEnabled,hasWikiEnabled,hasProjectsEnabled,hasDiscussionsEnabled,repositoryTopics,pushedAt,url,description"
        ])

        try:
            repos = json.loads(output)
            return sorted(repos, key=lambda x: x.get("name", "").lower())
        except Exception as e:
            raise GitHubAPIError(f"Failed to parse repositories JSON: {e}")

    def get_repo_counts(self, full_name: str) -> Dict[str, int]:
        """Fetch counts for releases, packages, and deployments concurrently."""
        counts = {"releases": 0, "packages": 0, "deployments": 0}

        def _count(endpoint: str, key: str):
            try:
                out = self.run_gh(["api", f"repos/{full_name}/{endpoint}", "--jq", "length"])
                if out.isdigit():
                    counts[key] = int(out)
            except Exception:
                pass

        with ThreadPoolExecutor(max_workers=3) as executor:
            f_rel = executor.submit(_count, "releases", "releases")
            f_pkg = executor.submit(_count, "packages", "packages")
            f_dep = executor.submit(_count, "deployments", "deployments")
            f_rel.result()
            f_pkg.result()
            f_dep.result()

        return counts

    def update_repository_features(
        self,
        full_name: str,
        features: Dict[str, bool],
        is_archived: bool = False,
    ) -> None:
        """Update repository feature toggles, handling temporary unarchiving if needed."""
        # If archived, unarchive first
        if is_archived:
            self.run_gh(["api", "-X", "PATCH", f"repos/{full_name}", "-F", "archived=false"])

        args = ["api", "-X", "PATCH", f"repos/{full_name}"]
        for k, v in features.items():
            args.extend(["-F", f"{k}={str(v).lower()}"])

        self.run_gh(args)

        # Restore archived state if it was originally archived
        if is_archived:
            self.run_gh(["api", "-X", "PATCH", f"repos/{full_name}", "-F", "archived=true"])

    def list_webhooks(self, full_name: str) -> List[Dict[str, Any]]:
        """List all webhooks for a given repository."""
        try:
            output = self.run_gh(["api", f"repos/{full_name}/hooks", "--paginate"])
            if not output:
                return []
            return json.loads(output)
        except GitHubAPIError as e:
            if "Not Found" in str(e) or "404" in str(e):
                return []
            raise

    def get_last_delivery(self, full_name: str, hook_id: int) -> Dict[str, Any]:
        """Fetch the most recent delivery attempt for a webhook."""
        try:
            output = self.run_gh([
                "api", f"repos/{full_name}/hooks/{hook_id}/deliveries",
                "--paginate",
                "--jq", ".[0] | {status_code, delivered_at, event, duration}"
            ])
            if output:
                return json.loads(output)
        except Exception:
            pass
        return {"status_code": "N/A", "delivered_at": "N/A", "event": "N/A", "duration": 0}

    def create_webhook(
        self,
        full_name: str,
        url: str,
        secret: str = "",
        events: Optional[List[str]] = None,
        active: bool = True,
    ) -> Dict[str, Any]:
        """Create a new webhook on a repository."""
        event_list = events or ["push"]
        payload = {
            "name": "web",
            "active": active,
            "events": event_list,
            "config": {
                "url": url,
                "content_type": "json",
                "secret": secret,
                "insecure_ssl": "0",
            },
        }

        output = self.run_gh([
            "api", "-X", "POST", f"repos/{full_name}/hooks",
            "--input", "-"
        ])
        return json.loads(output)

    def delete_webhook(self, full_name: str, hook_id: int) -> None:
        """Delete a webhook by ID from a repository."""
        self.run_gh(["api", "-X", "DELETE", f"repos/{full_name}/hooks/{hook_id}"])
