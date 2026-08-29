"""
Local Git repository inspection and scanner engine.
"""

from __future__ import annotations

import os
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class WorkingTreeStatus:
    """Represents local working tree state."""
    staged: int = 0
    unstaged: int = 0
    untracked: int = 0
    conflicted: int = 0
    stashes: int = 0

    @property
    def is_clean(self) -> bool:
        return (
            self.staged == 0
            and self.unstaged == 0
            and self.untracked == 0
            and self.conflicted == 0
        )


@dataclass
class RemoteSyncStatus:
    """Represents upstream tracking and synchronization state."""
    has_remote: bool = False
    remote_name: str = ""
    remote_url: str = ""
    upstream: str = ""
    ahead: int = 0
    behind: int = 0
    fetch_error: Optional[str] = None

    @property
    def sync_state(self) -> str:
        if not self.has_remote:
            return "no_remote"
        if not self.upstream:
            return "no_upstream"
        if self.ahead > 0 and self.behind > 0:
            return "diverged"
        if self.ahead > 0:
            return "ahead"
        if self.behind > 0:
            return "behind"
        return "synced"


@dataclass
class RepoAuditResult:
    """Complete audit state for a single repository."""
    name: str
    path: str
    is_git: bool
    branch: str = ""
    is_detached: bool = False
    working_tree: WorkingTreeStatus = field(default_factory=WorkingTreeStatus)
    remote_sync: RemoteSyncStatus = field(default_factory=RemoteSyncStatus)
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "path": self.path,
            "is_git": self.is_git,
            "branch": self.branch,
            "is_detached": self.is_detached,
            "working_tree": asdict(self.working_tree),
            "remote_sync": {
                "has_remote": self.remote_sync.has_remote,
                "remote_name": self.remote_sync.remote_name,
                "remote_url": self.remote_sync.remote_url,
                "upstream": self.remote_sync.upstream,
                "ahead": self.remote_sync.ahead,
                "behind": self.remote_sync.behind,
                "sync_state": self.remote_sync.sync_state,
                "fetch_error": self.remote_sync.fetch_error,
            },
            "error_message": self.error_message,
        }


class GitScanner:
    """Discovers and inspects Git repositories on local filesystem."""

    def __init__(self, timeout: int = 5):
        self.timeout = timeout

    @staticmethod
    def is_git_repo(path: Path) -> bool:
        """Check if path is a Git repository root or worktree."""
        git_dir = path / ".git"
        if git_dir.exists():
            return True
        try:
            res = subprocess.run(
                ["git", "-C", str(path), "rev-parse", "--is-inside-work-tree"],
                capture_output=True,
                text=True,
                check=False,
            )
            return res.returncode == 0 and res.stdout.strip() == "true"
        except Exception:
            return False

    def discover_directories(
        self, base_path: Path, max_depth: int = 3, recursive: bool = False
    ) -> List[Path]:
        """Discover Git repositories in workspace directory.
        
        Searches immediate subdirectories and nested folders (e.g. ~/projects/folder/repo).
        Stops descending once a Git repository is detected.
        """
        if not base_path.exists() or not base_path.is_dir():
            return []

        if self.is_git_repo(base_path):
            return [base_path]

        discovered: List[Path] = []

        def _walk(current: Path, current_depth: int):
            if not recursive and current_depth > max_depth:
                return
            try:
                for child in sorted(current.iterdir()):
                    if not child.is_dir() or child.name.startswith("."):
                        continue
                    if self.is_git_repo(child):
                        discovered.append(child)
                    else:
                        _walk(child, current_depth + 1)
            except OSError:
                pass

        _walk(base_path, 1)
        return discovered

    def fetch_remote(self, repo_path: Path) -> Optional[str]:
        """Run git fetch with timeout to refresh remote refs."""
        try:
            res = subprocess.run(
                ["git", "-C", str(repo_path), "fetch", "--prune", "--quiet"],
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=False,
            )
            if res.returncode != 0:
                raw_err = (res.stderr.strip() or res.stdout.strip()).lower()
                if "could not read from remote" in raw_err or "permission denied" in raw_err:
                    return "auth error"
                if "could not resolve host" in raw_err or "network is unreachable" in raw_err:
                    return "network error"
                return "fetch failed"
            return None
        except subprocess.TimeoutExpired:
            return f"timeout ({self.timeout}s)"
        except Exception:
            return "fetch error"

    def audit_repository(
        self, repo_path: Path, do_fetch: bool = False, base_path: Optional[Path] = None
    ) -> RepoAuditResult:
        """Inspect a directory and gather full git status."""
        if base_path and repo_path != base_path:
            try:
                name = str(repo_path.relative_to(base_path))
            except ValueError:
                name = repo_path.name
        else:
            name = repo_path.name

        path_str = str(repo_path.resolve())

        if not self.is_git_repo(repo_path):
            return RepoAuditResult(
                name=name,
                path=path_str,
                is_git=False,
                error_message="Not a git repository",
            )

        fetch_err = None
        if do_fetch:
            fetch_err = self.fetch_remote(repo_path)

        # 1. Parse branch and working tree state via porcelain v2
        branch = "unknown"
        upstream = ""
        ahead = 0
        behind = 0
        is_detached = False
        staged = 0
        unstaged = 0
        untracked = 0
        conflicted = 0

        try:
            status_res = subprocess.run(
                ["git", "-C", str(repo_path), "status", "--porcelain=v2", "--branch"],
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=False,
            )

            if status_res.returncode == 0:
                for line in status_res.stdout.splitlines():
                    if line.startswith("# branch.head "):
                        branch_head = line.split(maxsplit=2)[2]
                        if branch_head == "(detached)":
                            is_detached = True
                            head_res = subprocess.run(
                                ["git", "-C", str(repo_path), "describe", "--tags", "--always"],
                                capture_output=True,
                                text=True,
                                check=False,
                            )
                            branch = head_res.stdout.strip() or "(detached)"
                        else:
                            branch = branch_head
                    elif line.startswith("# branch.upstream "):
                        upstream = line.split(maxsplit=2)[2]
                    elif line.startswith("# branch.ab "):
                        parts = line.split()
                        if len(parts) >= 4:
                            ahead_str = parts[2].lstrip("+")
                            behind_str = parts[3].lstrip("-")
                            ahead = int(ahead_str) if ahead_str.isdigit() else 0
                            behind = int(behind_str) if behind_str.isdigit() else 0
                    elif line.startswith("1 ") or line.startswith("2 "):
                        xy = line.split()[1]
                        if xy[0] != ".":
                            staged += 1
                        if xy[1] != ".":
                            unstaged += 1
                    elif line.startswith("u "):
                        conflicted += 1
                    elif line.startswith("? "):
                        untracked += 1
            else:
                return RepoAuditResult(
                    name=name,
                    path=path_str,
                    is_git=True,
                    error_message=status_res.stderr.strip() or "Failed to get git status",
                )
        except Exception as e:
            return RepoAuditResult(
                name=name,
                path=path_str,
                is_git=True,
                error_message=f"Git status error: {e}",
            )

        # 2. Count stashes
        stashes = 0
        try:
            stash_res = subprocess.run(
                ["git", "-C", str(repo_path), "rev-list", "--walk-reflogs", "--count", "refs/stash"],
                capture_output=True,
                text=True,
                check=False,
            )
            if stash_res.returncode == 0 and stash_res.stdout.strip().isdigit():
                stashes = int(stash_res.stdout.strip())
        except Exception:
            pass

        # 3. Check Remotes
        has_remote = False
        remote_name = ""
        remote_url = ""
        try:
            remote_res = subprocess.run(
                ["git", "-C", str(repo_path), "remote"],
                capture_output=True,
                text=True,
                check=False,
            )
            remotes = [r for r in remote_res.stdout.strip().splitlines() if r]
            if remotes:
                has_remote = True
                remote_name = "origin" if "origin" in remotes else remotes[0]
                url_res = subprocess.run(
                    ["git", "-C", str(repo_path), "remote", "get-url", remote_name],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if url_res.returncode == 0:
                    remote_url = url_res.stdout.strip()
        except Exception:
            pass

        wt = WorkingTreeStatus(
            staged=staged,
            unstaged=unstaged,
            untracked=untracked,
            conflicted=conflicted,
            stashes=stashes,
        )

        remote_sync = RemoteSyncStatus(
            has_remote=has_remote,
            remote_name=remote_name,
            remote_url=remote_url,
            upstream=upstream,
            ahead=ahead,
            behind=behind,
            fetch_error=fetch_err,
        )

        return RepoAuditResult(
            name=name,
            path=path_str,
            is_git=True,
            branch=branch,
            is_detached=is_detached,
            working_tree=wt,
            remote_sync=remote_sync,
        )

    def audit_workspace(
        self,
        target_path: Path,
        do_fetch: bool = False,
        recursive: bool = False,
        max_depth: int = 3,
        threads: int = 8,
    ) -> List[RepoAuditResult]:
        """Discover and audit all repositories in target workspace concurrently."""
        candidate_dirs = self.discover_directories(
            base_path=target_path,
            max_depth=max_depth,
            recursive=recursive,
        )

        if not candidate_dirs:
            return []

        results: List[RepoAuditResult] = []
        max_workers = min(threads, max(len(candidate_dirs), 1))

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_path = {
                executor.submit(self.audit_repository, d, do_fetch, target_path): d
                for d in candidate_dirs
            }
            for future in as_completed(future_to_path):
                try:
                    res = future.result()
                    results.append(res)
                except Exception as e:
                    path = future_to_path[future]
                    try:
                        name = str(path.relative_to(target_path))
                    except ValueError:
                        name = path.name
                    results.append(
                        RepoAuditResult(
                            name=name,
                            path=str(path),
                            is_git=False,
                            error_message=str(e),
                        )
                    )

        results.sort(key=lambda x: x.name.lower())
        return results
