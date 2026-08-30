"""
AI Provider abstraction and commit message generator for gitctl.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple


SYSTEM_PROMPT = """You are an expert Git commit message generator.
Analyze the provided Git diff and generate a concise, single-line commit message in English.

STRICT RULES:
1. The commit message MUST be a single line.
2. Use a natural, descriptive, imperative sentence (e.g. "Add webhook health check and retry mechanism" or "Fix race condition in background task scheduler").
3. Strictly DO NOT use Conventional Commits (do NOT use prefixes like "feat:", "fix:", "chore:", "docs:", "refactor:", "style:", "test:", "ci:").
4. Do NOT include markdown code blocks, backticks, quotation marks, or explanations.
5. Return ONLY the commit message text.
"""


def clean_commit_message(raw_text: str) -> str:
    """
    Sanitize and clean the raw AI response to ensure a clean single-line commit message.
    """
    if not raw_text:
        return ""

    text = raw_text.strip()

    # Remove markdown code block fences if present
    text = re.sub(r"^```[a-zA-Z0-9_-]*\n", "", text)
    text = re.sub(r"\n```$", "", text)
    text = text.strip()

    # If output contains multiple lines, take the first non-empty line
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if lines:
        text = lines[0]

    # Strip surrounding quotes
    if (text.startswith('"') and text.endswith('"')) or (text.startswith("'") and text.endswith("'")):
        text = text[1:-1].strip()

    # Strip markdown inline backticks
    if text.startswith("`") and text.endswith("`"):
        text = text[1:-1].strip()

    # Remove common conversational prefixes like "Commit message: ", "Here is the commit message: ", etc.
    prefix_patterns = [
        r"^(?:commit\s*message|suggested\s*commit\s*message|suggestion)\s*:\s*",
        r"^(?:here\s+is\s+the\s+commit\s+message|commit\s+summary)\s*:\s*",
    ]
    for pattern in prefix_patterns:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE).strip()

    # Remove Conventional Commits prefix if AI accidentally included it
    text = re.sub(
        r"^(?:feat|fix|chore|docs|style|refactor|perf|test|build|ci|revert)(?:\([^\)]+\))?!?:\s*",
        "",
        text,
        flags=re.IGNORECASE,
    ).strip()

    # Capitalize the first letter if it starts with lowercase
    if text and text[0].islower():
        text = text[0].upper() + text[1:]

    # Remove trailing period if present for consistency
    if text.endswith("."):
        text = text[:-1].strip()

    return text


def build_commit_prompt(
    diff_text: str,
    stat_text: str = "",
    hint: Optional[str] = None,
    max_diff_chars: int = 12000,
) -> str:
    """
    Construct the full prompt to send to the AI backend.
    """
    # Truncate diff if it exceeds the maximum size budget
    truncated_diff = diff_text
    is_truncated = False
    if len(diff_text) > max_diff_chars:
        truncated_diff = diff_text[:max_diff_chars]
        is_truncated = True

    prompt_parts: List[str] = [SYSTEM_PROMPT]

    if hint:
        prompt_parts.append(f"\nADDITIONAL USER GUIDANCE / CONTEXT:\n{hint.strip()}\n")

    if stat_text:
        prompt_parts.append(f"\nSTAGED FILES SUMMARY (git diff --stat):\n{stat_text.strip()}\n")

    prompt_parts.append("\nSTAGED DIFF CONTENT:")
    prompt_parts.append("```diff")
    prompt_parts.append(truncated_diff.strip())
    if is_truncated:
        prompt_parts.append("\n[... diff truncated due to size limit ...]")
    prompt_parts.append("```")

    prompt_parts.append("\nGenerate the single-line commit message in English:")
    return "\n".join(prompt_parts)


class AIProvider(ABC):
    """Abstract base class for AI CLI providers."""

    name: str

    @abstractmethod
    def is_available(self) -> bool:
        """Check if provider CLI binary is installed and executable."""
        pass

    @abstractmethod
    def generate(self, prompt: str, timeout: int = 45) -> str:
        """Execute AI CLI and return raw text response."""
        pass


class AntigravityProvider(AIProvider):
    """Provider utilizing Antigravity CLI (agy)."""

    name = "agy"

    def is_available(self) -> bool:
        return shutil.which("agy") is not None

    def generate(self, prompt: str, timeout: int = 45) -> str:
        cmd = [
            "agy",
            "-p",
            prompt,
            "--disable-slash-commands",
            "--output-format",
            "text",
        ]
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
            check=False,
        )
        if result.returncode != 0:
            err_msg = result.stderr.strip() or f"Process exited with code {result.returncode}"
            raise RuntimeError(f"Antigravity CLI ('agy') failed: {err_msg}")

        return result.stdout


class CopilotProvider(AIProvider):
    """Provider utilizing GitHub Copilot CLI (gh copilot or copilot)."""

    name = "copilot"

    def is_available(self) -> bool:
        if shutil.which("copilot"):
            return True
        if shutil.which("gh"):
            # Check if copilot extension is installed
            res = subprocess.run(
                ["gh", "copilot", "--help"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            return res.returncode == 0
        return False

    def generate(self, prompt: str, timeout: int = 45) -> str:
        if shutil.which("copilot"):
            cmd = ["copilot", "-p", prompt]
        else:
            cmd = ["gh", "copilot", "suggest", "-t", "shell", prompt]

        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
            check=False,
        )
        if result.returncode != 0:
            err_msg = result.stderr.strip() or f"Process exited with code {result.returncode}"
            raise RuntimeError(f"Copilot CLI failed: {err_msg}")

        return result.stdout


_PROVIDERS: Dict[str, AIProvider] = {
    "agy": AntigravityProvider(),
    "copilot": CopilotProvider(),
}


def get_available_providers() -> List[str]:
    """Return list of available provider names."""
    return [name for name, p in _PROVIDERS.items() if p.is_available()]


def resolve_provider(preferred: str = "auto") -> AIProvider:
    """
    Resolve and return an available AI provider.
    """
    pref = preferred.lower().strip()
    if pref in _PROVIDERS:
        provider = _PROVIDERS[pref]
        if not provider.is_available():
            raise RuntimeError(
                f"Requested AI provider '{preferred}' is not installed or not in PATH."
            )
        return provider

    if pref == "auto":
        # Check providers in priority order: agy, then copilot
        for name in ("agy", "copilot"):
            provider = _PROVIDERS[name]
            if provider.is_available():
                return provider

        raise RuntimeError(
            "No AI CLI provider found in PATH. Please ensure Antigravity CLI ('agy') "
            "or GitHub Copilot CLI ('gh copilot' / 'copilot') is installed."
        )

    raise ValueError(
        f"Unknown AI provider '{preferred}'. Supported providers: auto, agy, copilot"
    )


def generate_commit_message(
    diff_text: str,
    stat_text: str = "",
    hint: Optional[str] = None,
    provider_name: str = "auto",
    timeout: int = 45,
) -> Tuple[str, str]:
    """
    Generate and clean a commit message from git diff.
    Returns a tuple of (commit_message, provider_used).
    """
    provider = resolve_provider(provider_name)
    prompt = build_commit_prompt(diff_text, stat_text=stat_text, hint=hint)
    raw_output = provider.generate(prompt, timeout=timeout)
    message = clean_commit_message(raw_output)
    if not message:
        raise RuntimeError("AI provider returned an empty commit message.")
    return message, provider.name
