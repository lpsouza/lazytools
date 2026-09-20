"""
Unit tests for Windows cross-platform compatibility in lazytools.
"""

from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "python"))


class TestWindowsCompatibility(unittest.TestCase):

    def test_powershell_scripts_coverage(self):
        """Ensure all bash Docker wrapper scripts have a corresponding PowerShell script."""
        bash_dir = PROJECT_ROOT / "bash"
        pwsh_dir = PROJECT_ROOT / "powershell"

        self.assertTrue(bash_dir.is_dir(), "bash directory must exist")
        self.assertTrue(pwsh_dir.is_dir(), "powershell directory must exist")

        bash_scripts = {f.stem for f in bash_dir.glob("*.sh")}
        pwsh_scripts = {f.stem for f in pwsh_dir.glob("*.ps1")}

        self.assertTrue(len(bash_scripts) > 0, "bash scripts should be present")
        self.assertEqual(
            bash_scripts,
            pwsh_scripts,
            f"PowerShell scripts must cover all bash scripts. Missing: {bash_scripts - pwsh_scripts}",
        )

    def test_install_script_ps1_exists(self):
        """Ensure install-script.ps1 is present in repository root."""
        installer = PROJECT_ROOT / "install-script.ps1"
        self.assertTrue(installer.is_file(), "install-script.ps1 must exist")

    def test_commit_cmd_readline_fallback(self):
        """Ensure prompt_inline_edit works when readline is not installed (Windows)."""
        import gitctl.commands.commit_cmd as commit_cmd

        with patch.object(commit_cmd, "readline", None):
            if commit_cmd.HAS_RICH:
                with patch.object(commit_cmd.Prompt, "ask", return_value="custom commit"):
                    msg = commit_cmd.prompt_inline_edit("initial message")
                    self.assertEqual(msg, "custom commit")
            else:
                with patch("builtins.input", return_value="custom commit"):
                    msg = commit_cmd.prompt_inline_edit("initial message")
                    self.assertEqual(msg, "custom commit")

    def test_commit_cmd_editor_fallback_on_windows(self):
        """Ensure prompt_editor_edit uses notepad as default on win32."""
        import gitctl.commands.commit_cmd as commit_cmd

        with patch("sys.platform", "win32"), patch.dict("os.environ", {}, clear=True):
            with patch("subprocess.run") as mock_run:
                commit_cmd.prompt_editor_edit("hello")
                self.assertTrue(mock_run.called)
                args, _ = mock_run.call_args
                editor_cmd = args[0][0]
                self.assertEqual(editor_cmd, "notepad")

    def test_nodetop_ui_windows_compat(self):
        """Ensure nodetop NodetopApp handles Windows terminal restoration gracefully."""
        from nodetop.ui import NodetopApp

        app = NodetopApp("http://localhost:9100")
        with patch("sys.platform", "win32"):
            # Should not raise any exception when restoring terminal on Windows
            app._orig_termios = None
            app._restore_terminal()

    def test_gitctl_console_without_rich(self):
        """Ensure gitctl console and tables function even when rich is not installed."""
        import importlib
        with patch.dict("sys.modules", {"rich": None, "rich.console": None, "rich.table": None}):
            import gitctl.core.console as console_mod
            importlib.reload(console_mod)
            self.assertFalse(console_mod.HAS_RICH)
            self.assertIsNotNone(console_mod.console)

            # Test print, table, panel
            with patch("builtins.print"):
                console_mod.console.print("test message")
            tbl = console_mod.create_table(title="Test")
            tbl.add_column("Col A")
            tbl.add_row("Val 1")
            self.assertIn("Val 1", str(tbl))

            panel = console_mod.create_panel("panel content", title="Title")
            self.assertIn("panel content", str(panel))

        # Reload back to normal
        import gitctl.core.console as console_mod
        importlib.reload(console_mod)

    def test_nodetop_cli_without_rich(self):
        """Ensure nodetop cli exits gracefully when rich is missing."""
        import nodetop.cli as nodetop_cli
        with patch.object(nodetop_cli, "NodetopApp", None):
            with patch("sys.stderr.write"):
                res = nodetop_cli.main([])
                self.assertEqual(res, 1)

    def test_requirements_and_gitignore_venv(self):
        """Ensure requirements.txt and .gitignore include venv patterns."""
        req_file = PROJECT_ROOT / "requirements.txt"
        gitignore_file = PROJECT_ROOT / ".gitignore"

        self.assertTrue(req_file.is_file(), "requirements.txt must exist")
        self.assertIn("rich", req_file.read_text())

        self.assertTrue(gitignore_file.is_file(), ".gitignore must exist")
        self.assertIn(".venv/", gitignore_file.read_text())

    def test_bootstrap_ensure_venv_behavior(self):
        """Ensure bootstrap.ensure_venv behaves properly when venv is missing or active."""
        from bootstrap import ensure_venv

        # 1. When no .venv exists, should return immediately without executing
        with patch("pathlib.Path.is_dir", return_value=False):
            with patch("os.execv") as mock_execv, patch("subprocess.call") as mock_call:
                ensure_venv()
                self.assertFalse(mock_execv.called)
                self.assertFalse(mock_call.called)


if __name__ == "__main__":
    unittest.main()
