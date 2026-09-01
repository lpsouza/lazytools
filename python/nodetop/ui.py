"""
Interactive TUI dashboard engine for nodetop using rich.live.Live.
"""

from collections import deque
import os
import queue
import select
import sys
import termios
import threading
import time
import tty
from typing import Dict, List, Optional

from rich.align import Align
from rich.box import DOUBLE, ROUNDED
from rich.console import Console, Group
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from nodetop.collector import NodeExporterCollector, NodeSnapshot
from nodetop.history import MetricsHistory
from nodetop.widgets import (
    CpuWidget,
    DiskWidget,
    FooterWidget,
    HeaderWidget,
    MemoryWidget,
    NetworkWidget,
    SystemWidget,
    format_bytes,
    format_duration,
)


class NodetopApp:
    """
    Main application engine running the live terminal dashboard.
    """

    def __init__(
        self,
        target_url: str,
        interval: float = 1.0,
        timeout: float = 3.0,
        no_color: bool = False,
    ) -> None:
        self.target_url = target_url
        self.interval = max(0.2, interval)
        self.timeout = timeout
        self.collector = NodeExporterCollector(target_url, timeout=timeout)
        self.history = MetricsHistory(max_samples=60)
        self.console = Console(no_color=no_color)
        self.running = False
        self.show_help = False
        self.status_message: Optional[str] = None
        self.status_msg_expires: float = 0.0

        # Panel visibility flags
        self.show_cpu = True
        self.show_mem = True
        self.show_disks = True
        self.show_net = True
        self.show_sys = True

        self._key_queue: queue.Queue[str] = queue.Queue()
        self._orig_termios = None

    def print_snapshot_once(self) -> None:
        """Collect two consecutive samples to compute rates and print a formatted summary."""
        self.console.print(f"[bold cyan]Scraping node_exporter at {self.target_url}...[/bold cyan]")
        _ = self.collector.collect()
        time.sleep(1.0)
        snapshot = self.collector.collect()

        if snapshot.error:
            self.console.print(f"[bold red]Error:[/] {snapshot.error}")
            return

        # Update history with initial data
        self.history.push(
            cpu_pct=snapshot.cpu.overall_usage_pct,
            mem_pct=snapshot.memory.used_pct,
            net_rx=sum(n.rx_bytes_sec for n in snapshot.network),
            net_tx=sum(n.tx_bytes_sec for n in snapshot.network),
            disk_read=sum(d.read_bytes_sec for d in snapshot.disk_io),
            disk_write=sum(d.write_bytes_sec for d in snapshot.disk_io),
        )

        header = HeaderWidget.render(snapshot, self.target_url, self.interval)
        cpu_panel = CpuWidget.render(snapshot, self.history)
        mem_panel = MemoryWidget.render(snapshot, self.history)
        disk_panel = DiskWidget.render(snapshot)
        net_panel = NetworkWidget.render(snapshot, self.history)
        sys_panel = SystemWidget.render(snapshot)

        self.console.print(header)
        self.console.print(cpu_panel)
        self.console.print(mem_panel)
        self.console.print(disk_panel)
        self.console.print(net_panel)
        self.console.print(sys_panel)

    def _start_keyboard_listener(self) -> None:
        """Starts a background thread reading keyboard input non-blockingly."""
        if not sys.stdin.isatty():
            return

        def listener_loop():
            try:
                self._orig_termios = termios.tcgetattr(sys.stdin)
                tty.setcbreak(sys.stdin.fileno())
                while self.running:
                    rlist, _, _ = select.select([sys.stdin], [], [], 0.2)
                    if rlist:
                        char = sys.stdin.read(1)
                        if char:
                            self._key_queue.put(char)
            except Exception:
                pass
            finally:
                if self._orig_termios:
                    try:
                        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self._orig_termios)
                    except Exception:
                        pass

        thread = threading.Thread(target=listener_loop, daemon=True)
        thread.start()

    def _restore_terminal(self) -> None:
        """Restores original terminal settings."""
        if self._orig_termios and sys.stdin.isatty():
            try:
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self._orig_termios)
            except Exception:
                pass

    def _set_status(self, message: str, duration: float = 3.0) -> None:
        """Display a temporary status notice in the footer."""
        self.status_message = message
        self.status_msg_expires = time.time() + duration

    def _handle_key(self, key: str) -> None:
        """Processes an interactive keypress."""
        if key in ("q", "Q", "\x03"):  # q or Ctrl+C
            self.running = False
        elif key in ("h", "?"):
            self.show_help = not self.show_help
        elif key == "r":
            self._set_status("Refreshing...")
        elif key in ("+", "="):
            self.interval = min(10.0, self.interval + 0.5)
            self._set_status(f"Interval: {self.interval:.1f}s")
        elif key in ("-", "_"):
            self.interval = max(0.5, self.interval - 0.5)
            self._set_status(f"Interval: {self.interval:.1f}s")
        elif key == "1":
            self.show_cpu = not self.show_cpu
            self._set_status(f"CPU Panel: {'ON' if self.show_cpu else 'OFF'}")
        elif key == "2":
            self.show_mem = not self.show_mem
            self._set_status(f"Memory Panel: {'ON' if self.show_mem else 'OFF'}")
        elif key == "3":
            self.show_disks = not self.show_disks
            self._set_status(f"Disks Panel: {'ON' if self.show_disks else 'OFF'}")
        elif key == "4":
            self.show_net = not self.show_net
            self._set_status(f"Network Panel: {'ON' if self.show_net else 'OFF'}")
        elif key == "5":
            self.show_sys = not self.show_sys
            self._set_status(f"System Panel: {'ON' if self.show_sys else 'OFF'}")

    def _render_help_modal(self) -> Panel:
        """Renders the help dialog overlay."""
        help_table = Table(box=ROUNDED, show_header=False, expand=True)
        help_table.add_column("Key", style="bold yellow", ratio=1)
        help_table.add_column("Action", style="white", ratio=3)

        help_table.add_row("q / Ctrl+C", "Quit nodetop")
        help_table.add_row("r", "Force immediate metrics refresh")
        help_table.add_row("+ / -", "Increase / decrease scrape interval (0.5s - 10s)")
        help_table.add_row("1", "Toggle CPU panel")
        help_table.add_row("2", "Toggle Memory & Swap panel")
        help_table.add_row("3", "Toggle Disks & Filesystems panel")
        help_table.add_row("4", "Toggle Network Interfaces panel")
        help_table.add_row("5", "Toggle System & Sockets panel")
        help_table.add_row("h / ?", "Toggle this help screen")

        return Panel(
            Align.center(help_table),
            box=DOUBLE,
            title="[bold yellow]nodetop Help & Keybindings[/bold yellow]",
            subtitle="[dim]Press [h] or [q] to close[/dim]",
            border_style="yellow",
        )

    def _render_error_panel(self, snapshot: NodeSnapshot) -> Panel:
        """Renders an error panel when node_exporter is unreachable."""
        text = Text()
        text.append("⚠ Unable to connect to node_exporter\n\n", style="bold red")
        text.append(f"Target:   {self.target_url}\n", style="bold white")
        text.append(f"Error:    {snapshot.error}\n\n", style="yellow")
        text.append(f"Retrying automatically every {self.interval:.1f}s...\n", style="dim white")
        text.append("Press [q] to quit or [r] to retry immediately.", style="dim cyan")

        return Panel(
            Align.center(text),
            box=DOUBLE,
            title="[bold red]Connection Failed[/bold red]",
            border_style="red",
        )

    def _build_layout(self, snapshot: NodeSnapshot) -> RenderableType:
        """Builds the full-screen layout structure."""
        if self.show_help:
            return self._render_help_modal()

        if snapshot.error:
            return Group(
                HeaderWidget.render(snapshot, self.target_url, self.interval),
                self._render_error_panel(snapshot),
                FooterWidget.render(self.status_message),
            )

        # Clear expired status message
        if self.status_message and time.time() > self.status_msg_expires:
            self.status_message = None

        layout = Layout(name="root")
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="body", ratio=1),
            Layout(name="footer", size=3),
        )

        layout["header"].update(HeaderWidget.render(snapshot, self.target_url, self.interval))
        layout["footer"].update(FooterWidget.render(self.status_message))

        # Dynamic body layout based on active panels
        upper_splits = []
        if self.show_cpu:
            upper_splits.append(Layout(name="cpu", ratio=3))
        if self.show_mem:
            upper_splits.append(Layout(name="mem", ratio=2))

        lower_splits = []
        if self.show_disks:
            lower_splits.append(Layout(name="disks", ratio=1))
        if self.show_net:
            lower_splits.append(Layout(name="net", ratio=1))

        body_rows = []
        if upper_splits:
            upper_row = Layout(name="upper_row", ratio=4)
            upper_row.split_row(*upper_splits)
            body_rows.append(upper_row)

        if lower_splits:
            lower_row = Layout(name="lower_row", ratio=3)
            lower_row.split_row(*lower_splits)
            body_rows.append(lower_row)

        if self.show_sys:
            body_rows.append(Layout(name="system", size=5))

        if body_rows:
            layout["body"].split_column(*body_rows)
            if self.show_cpu:
                layout["cpu"].update(CpuWidget.render(snapshot, self.history))
            if self.show_mem:
                layout["mem"].update(MemoryWidget.render(snapshot, self.history))
            if self.show_disks:
                layout["disks"].update(DiskWidget.render(snapshot))
            if self.show_net:
                layout["net"].update(NetworkWidget.render(snapshot, self.history))
            if self.show_sys:
                layout["system"].update(SystemWidget.render(snapshot))
        else:
            layout["body"].update(
                Panel(
                    Align.center("[yellow]All panels hidden. Press 1-5 to toggle panels.[/yellow]"),
                    box=ROUNDED,
                )
            )

        return layout

    def run(self) -> int:
        """Main execution loop for live dashboard."""
        self.running = True
        self._start_keyboard_listener()

        try:
            # Initial scrape
            snapshot = self.collector.collect()
            if not snapshot.error:
                # Immediate second scrape after short delay to seed initial deltas
                time.sleep(0.3)
                snapshot = self.collector.collect()
                self._update_history(snapshot)

            with Live(
                self._build_layout(snapshot),
                console=self.console,
                screen=True,
                auto_refresh=False,
            ) as live:
                last_scrape = time.time()

                while self.running:
                    # Process queued keys
                    while not self._key_queue.empty():
                        try:
                            key = self._key_queue.get_nowait()
                            self._handle_key(key)
                        except queue.Empty:
                            break

                    now = time.time()
                    if now - last_scrape >= self.interval:
                        snapshot = self.collector.collect()
                        if not snapshot.error:
                            self._update_history(snapshot)
                        last_scrape = now

                    live.update(self._build_layout(snapshot))
                    live.refresh()
                    time.sleep(0.1)

        except KeyboardInterrupt:
            pass
        finally:
            self.running = False
            self._restore_terminal()

        return 0

    def _update_history(self, snapshot: NodeSnapshot) -> None:
        """Push latest metrics to history ring buffer."""
        total_rx = sum(n.rx_bytes_sec for n in snapshot.network)
        total_tx = sum(n.tx_bytes_sec for n in snapshot.network)
        total_read = sum(d.read_bytes_sec for d in snapshot.disk_io)
        total_write = sum(d.write_bytes_sec for d in snapshot.disk_io)
        per_core = {c.core_id: c.usage_pct for c in snapshot.cpu.cores}

        self.history.push(
            cpu_pct=snapshot.cpu.overall_usage_pct,
            mem_pct=snapshot.memory.used_pct,
            net_rx=total_rx,
            net_tx=total_tx,
            disk_read=total_read,
            disk_write=total_write,
            per_core=per_core,
        )
