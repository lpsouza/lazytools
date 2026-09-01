"""
UI Widgets and renderables for nodetop terminal dashboard using rich.
"""

from datetime import datetime, timedelta
import math
from typing import Dict, List, Optional

from rich.align import Align
from rich.box import ROUNDED, SIMPLE, SIMPLE_HEAVY
from rich.console import Console, Group, RenderableType
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from nodetop.collector import NodeSnapshot
from nodetop.history import MetricsHistory, render_sparkline_colored


def format_bytes(num_bytes: float, is_rate: bool = False) -> str:
    """Format bytes into human readable binary/decimal units."""
    if num_bytes < 0:
        return f"-{format_bytes(-num_bytes, is_rate)}"

    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    suffix = "/s" if is_rate else ""
    unit_idx = 0
    val = float(num_bytes)

    while val >= 1024.0 and unit_idx < len(units) - 1:
        val /= 1024.0
        unit_idx += 1

    if unit_idx == 0:
        return f"{int(val)} {units[0]}{suffix}"
    if val >= 100:
        return f"{val:.0f} {units[unit_idx]}{suffix}"
    if val >= 10:
        return f"{val:.1f} {units[unit_idx]}{suffix}"
    return f"{val:.2f} {units[unit_idx]}{suffix}"


def format_duration(seconds: float) -> str:
    """Format seconds into human readable duration (e.g., 3d 14h 22m)."""
    if seconds <= 0:
        return "0s"
    td = timedelta(seconds=int(seconds))
    days = td.days
    hours, remainder = divmod(td.seconds, 3600)
    minutes, secs = divmod(remainder, 60)

    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0 or days > 0:
        parts.append(f"{hours}h")
    if minutes > 0 or (days == 0 and hours > 0):
        parts.append(f"{minutes}m")
    if days == 0 and hours == 0:
        parts.append(f"{secs}s")

    return " ".join(parts)


def make_meter_bar(pct: float, width: int = 15) -> Text:
    """
    Creates a styled ASCII progress meter bar with color gradients.
    """
    clamped = max(0.0, min(100.0, pct))
    filled_chars = int(round((clamped / 100.0) * width))
    empty_chars = max(0, width - filled_chars)

    text = Text()
    text.append("[", style="bright_black")

    for i in range(filled_chars):
        ratio = i / max(1, width)
        if ratio < 0.6:
            color = "green"
        elif ratio < 0.85:
            color = "yellow"
        else:
            color = "red"
        text.append("█", style=color)

    text.append("░" * empty_chars, style="bright_black")
    text.append("]", style="bright_black")
    return text


def make_color_pct(pct: float) -> Tuple[str, str]:
    """Returns formatted percentage string and its style."""
    if pct >= 85.0:
        return f"{pct:5.1f}%", "bold red"
    if pct >= 60.0:
        return f"{pct:5.1f}%", "bold yellow"
    return f"{pct:5.1f}%", "bold green"


class HeaderWidget:
    """Renders the top title and system information bar."""

    @staticmethod
    def render(snapshot: NodeSnapshot, target_url: str, interval: float) -> Panel:
        sys = snapshot.system
        now_str = datetime.now().strftime("%H:%M:%S")

        table = Table.grid(expand=True)
        table.add_column(justify="left", ratio=3)
        table.add_column(justify="center", ratio=4)
        table.add_column(justify="right", ratio=3)

        # Left: Host & Target
        left_text = Text()
        left_text.append(" 󰒋 ", style="bold cyan")
        left_text.append(f"{sys.hostname} ", style="bold white")
        left_text.append(f"({target_url})", style="dim cyan")

        # Center: OS, Kernel & Arch
        center_text = Text()
        if sys.os_name:
            center_text.append(f"{sys.os_name} ", style="bold bright_blue")
        if sys.kernel_release:
            center_text.append(f"| {sys.kernel_release} ", style="dim white")
        if sys.machine_arch:
            center_text.append(f"({sys.machine_arch})", style="dim white")

        # Right: Uptime, Load, Latency & Clock
        right_text = Text()
        right_text.append(f"Up: {format_duration(sys.uptime_seconds)} ", style="green")
        right_text.append(f"| Load: {sys.load1:.2f} {sys.load5:.2f} {sys.load15:.2f} ", style="bright_yellow")
        right_text.append(f"| {snapshot.latency_ms:.0f}ms ", style="dim magenta")
        right_text.append(f"| {now_str} ", style="bold white")

        table.add_row(left_text, center_text, right_text)

        return Panel(
            table,
            box=ROUNDED,
            style="cyan",
            title="[bold cyan]nodetop[/bold cyan]",
            title_align="left",
            subtitle=f"[dim]Refresh: {interval:.1f}s[/dim]",
            subtitle_align="right",
        )


class CpuWidget:
    """Renders CPU overall usage, history graph, and per-core grid."""

    @staticmethod
    def render(snapshot: NodeSnapshot, history: MetricsHistory) -> Panel:
        cpu = snapshot.cpu
        overall_pct = cpu.overall_usage_pct
        sparkline = render_sparkline_colored(
            list(history.cpu_overall), min_val=0.0, max_val=100.0, max_chars=25
        )

        main_table = Table.grid(expand=True)
        main_table.add_column()

        # Top summary row
        summary_table = Table.grid(expand=True)
        summary_table.add_column(ratio=1, justify="left")
        summary_table.add_column(ratio=1, justify="right")

        meter = make_meter_bar(overall_pct, width=12)
        pct_str, pct_style = make_color_pct(overall_pct)
        temp_str = f" {cpu.package_temp_celsius:.0f}°C" if cpu.package_temp_celsius is not None else ""

        left_sum = Text(no_wrap=True, overflow="crop")
        left_sum.append("Total: ", style="bold white")
        left_sum.append_text(meter)
        left_sum.append(f" {pct_str}", style=pct_style)
        if temp_str:
            left_sum.append(temp_str, style="dim yellow")

        right_sum = Text(no_wrap=True, overflow="crop")
        right_sum.append(f"usr: [cyan]{cpu.user_pct:.1f}%[/cyan]  ", style="dim")
        right_sum.append(f"sys: [blue]{cpu.system_pct:.1f}%[/blue]  ", style="dim")
        right_sum.append(f"io: [yellow]{cpu.iowait_pct:.1f}%[/yellow]", style="dim")

        summary_table.add_row(left_sum, right_sum)
        main_table.add_row(summary_table)

        # History row
        hist_text = Text(no_wrap=True, overflow="crop")
        hist_text.append("History: ", style="dim white")
        hist_text.append_text(Text.from_markup(sparkline or "[dim]collecting...[/dim]"))
        main_table.add_row(hist_text)
        main_table.add_row(Text("─" * 60, style="dim bright_black"))

        # Cores grid (2 columns or 3 columns depending on core count)
        num_cores = len(cpu.cores)
        num_cols = 3 if num_cores >= 12 else (2 if num_cores >= 4 else 1)
        cores_table = Table.grid(expand=True, padding=(0, 2))
        for _ in range(num_cols):
            cores_table.add_column(ratio=1)

        rows_needed = math.ceil(num_cores / num_cols) if num_cores > 0 else 0
        for r in range(rows_needed):
            row_items = []
            for c in range(num_cols):
                idx = c * rows_needed + r
                if idx < num_cores:
                    core = cpu.cores[idx]
                    core_text = Text()
                    core_label = f"C{int(core.core_id):02d}" if core.core_id.isdigit() else f"C{core.core_id[:3]}"
                    core_text.append(f"{core_label}: ", style="bold bright_black")
                    core_text.append_text(make_meter_bar(core.usage_pct, width=8))
                    c_pct_str, c_pct_style = make_color_pct(core.usage_pct)
                    core_text.append(f" {c_pct_str}", style=c_pct_style)
                    if core.frequency_mhz > 0:
                        ghz = core.frequency_mhz / 1000.0
                        core_text.append(f" {ghz:.1f}G", style="dim cyan")
                    if core.temperature_celsius is not None:
                        core_text.append(f" {core.temperature_celsius:.0f}°C", style="dim yellow")
                    row_items.append(core_text)
                else:
                    row_items.append(Text(""))
            cores_table.add_row(*row_items)

        main_table.add_row(cores_table)

        title = f"[bold green]CPU ({num_cores} Cores)[/bold green]"
        return Panel(main_table, box=ROUNDED, title=title, title_align="left", border_style="green")


class MemoryWidget:
    """Renders Memory and Swap usage meters and breakdown."""

    @staticmethod
    def render(snapshot: NodeSnapshot, history: MetricsHistory) -> Panel:
        mem = snapshot.memory
        sparkline = render_sparkline_colored(
            list(history.memory_used_pct), min_val=0.0, max_val=100.0, max_chars=18
        )

        main_table = Table.grid(expand=True)
        main_table.add_column()

        # RAM row
        ram_row = Table.grid(expand=True, padding=(0, 1))
        ram_row.add_column(ratio=5)
        ram_row.add_column(ratio=3)

        ram_left = Text(no_wrap=True, overflow="crop")
        ram_left.append("RAM:  ", style="bold white")
        ram_left.append_text(make_meter_bar(mem.used_pct, width=10))
        ram_left.append(f" {mem.used_pct:5.1f}% ", style="bold white")
        ram_left.append(f"({format_bytes(mem.used_bytes)} / {format_bytes(mem.total_bytes)})", style="dim")

        ram_right = Text(no_wrap=True, overflow="crop")
        ram_right.append("Graph: ", style="dim white")
        ram_right.append_text(Text.from_markup(sparkline or "[dim]collecting...[/dim]"))
        ram_row.add_row(ram_left, ram_right)
        main_table.add_row(ram_row)

        # SWAP row
        if mem.swap_total_bytes > 0:
            swap_left = Text(no_wrap=True, overflow="crop")
            swap_left.append("SWAP: ", style="bold white")
            swap_left.append_text(make_meter_bar(mem.swap_used_pct, width=10))
            swap_left.append(f" {mem.swap_used_pct:5.1f}% ", style="bold white")
            swap_left.append(
                f"({format_bytes(mem.swap_used_bytes)} / {format_bytes(mem.swap_total_bytes)})",
                style="dim",
            )
            main_table.add_row(swap_left)

        main_table.add_row(Text("─" * 40, style="dim bright_black"))

        # Breakdown stats
        stats_table = Table.grid(expand=True)
        stats_table.add_column(ratio=1)
        stats_table.add_column(ratio=1)
        stats_table.add_column(ratio=1)

        col1 = Text()
        col1.append("Avail: ", style="dim")
        col1.append(format_bytes(mem.available_bytes), style="bold green")
        col1.append("\nFree:  ", style="dim")
        col1.append(format_bytes(mem.free_bytes), style="green")

        col2 = Text()
        col2.append("Cached:  ", style="dim")
        col2.append(format_bytes(mem.cached_bytes), style="cyan")
        col2.append("\nBuffers: ", style="dim")
        col2.append(format_bytes(mem.buffers_bytes), style="cyan")

        col3 = Text()
        col3.append("Slab:  ", style="dim")
        col3.append(format_bytes(mem.slab_bytes), style="yellow")
        col3.append("\nDirty: ", style="dim")
        col3.append(format_bytes(mem.dirty_bytes), style="yellow")

        stats_table.add_row(col1, col2, col3)
        main_table.add_row(stats_table)

        return Panel(
            main_table,
            box=ROUNDED,
            title="[bold magenta]Memory & Swap[/bold magenta]",
            title_align="left",
            border_style="magenta",
        )


class DiskWidget:
    """Renders mounted filesystems and disk IO throughput."""

    @staticmethod
    def render(snapshot: NodeSnapshot) -> Panel:
        main_table = Table.grid(expand=True)
        main_table.add_column()

        # Filesystem table
        fs_table = Table(
            box=SIMPLE,
            expand=True,
            show_header=True,
            header_style="bold blue",
            pad_edge=False,
        )
        fs_table.add_column("Mount", style="bold white")
        fs_table.add_column("Type", style="dim", justify="center")
        fs_table.add_column("Usage", justify="left")
        fs_table.add_column("Used / Total", justify="right")
        fs_table.add_column("Free", justify="right", style="green")

        for fs in snapshot.filesystems[:5]:  # show top 5 mounts
            bar = make_meter_bar(fs.used_pct, width=10)
            usage_text = Text()
            usage_text.append_text(bar)
            usage_text.append(f" {fs.used_pct:4.1f}%")

            fs_table.add_row(
                Text(fs.mountpoint, style="bold white"),
                Text(fs.fstype, style="dim"),
                usage_text,
                f"{format_bytes(fs.used_bytes)} / {format_bytes(fs.total_bytes)}",
                Text(format_bytes(fs.avail_bytes), style="green"),
            )

        main_table.add_row(fs_table)

        # Disk I/O activity row
        if snapshot.disk_io:
            main_table.add_row(Text("─" * 40, style="dim bright_black"))
            io_text = Text()
            io_text.append("Disk I/O: ", style="bold white")
            active_ios = [d for d in snapshot.disk_io if d.read_bytes_sec > 0 or d.write_bytes_sec > 0 or d.io_util_pct > 0]
            if not active_ios:
                active_ios = snapshot.disk_io[:2]

            for d in active_ios[:3]:
                io_text.append(f"{d.device} ", style="bold cyan")
                io_text.append(f"▼ {format_bytes(d.read_bytes_sec, is_rate=True)} ", style="green")
                io_text.append(f"▲ {format_bytes(d.write_bytes_sec, is_rate=True)} ", style="magenta")
                if d.io_util_pct > 0:
                    io_text.append(f"({d.io_util_pct:.1f}% util) ", style="yellow")
            main_table.add_row(io_text)

        return Panel(
            main_table,
            box=ROUNDED,
            title="[bold blue]Disks & Filesystems[/bold blue]",
            title_align="left",
            border_style="blue",
        )


class NetworkWidget:
    """Renders active network interfaces, bandwidth rates, and total transfers."""

    @staticmethod
    def render(snapshot: NodeSnapshot, history: MetricsHistory) -> Panel:
        main_table = Table.grid(expand=True)
        main_table.add_column()

        net_table = Table(
            box=SIMPLE,
            expand=True,
            show_header=True,
            header_style="bold yellow",
            pad_edge=False,
        )
        net_table.add_column("Interface", style="bold white")
        net_table.add_column("Rx Speed", justify="right")
        net_table.add_column("Tx Speed", justify="right")
        net_table.add_column("Total Rx", justify="right", style="dim")
        net_table.add_column("Total Tx", justify="right", style="dim")
        net_table.add_column("State", justify="center")

        # Filter active or important interfaces (max 5)
        display_ifaces = [
            n for n in snapshot.network
            if (n.rx_bytes_sec > 0 or n.tx_bytes_sec > 0 or n.is_up or n.interface in ("eth0", "enp60s0", "tailscale0", "wlan0"))
            and n.interface != "lo"
        ][:5]

        if not display_ifaces:
            display_ifaces = snapshot.network[:3]

        for iface in display_ifaces:
            rx_style = "bold green" if iface.rx_bytes_sec > 0 else "dim green"
            tx_style = "bold magenta" if iface.tx_bytes_sec > 0 else "dim magenta"
            status_text = Text("UP", style="bold green") if iface.is_up else Text("DOWN", style="dim red")

            net_table.add_row(
                Text(iface.interface, style="bold white"),
                Text(f"▼ {format_bytes(iface.rx_bytes_sec, is_rate=True)}", style=rx_style),
                Text(f"▲ {format_bytes(iface.tx_bytes_sec, is_rate=True)}", style=tx_style),
                Text(format_bytes(iface.rx_total_bytes), style="dim"),
                Text(format_bytes(iface.tx_total_bytes), style="dim"),
                status_text,
            )

        main_table.add_row(net_table)

        # Sparkline row
        spark_rx = render_sparkline_colored(
            list(history.net_rx_rate),
            min_val=0.0,
            max_val=max(list(history.net_rx_rate) or [1.0]),
            max_chars=20,
        )
        spark_tx = render_sparkline_colored(
            list(history.net_tx_rate),
            min_val=0.0,
            max_val=max(list(history.net_tx_rate) or [1.0]),
            max_chars=20,
        )

        spark_row = Table.grid(expand=True, padding=(0, 2))
        spark_row.add_column(ratio=1)
        spark_row.add_column(ratio=1)

        rx_graph = Text(no_wrap=True, overflow="crop")
        rx_graph.append("Rx Hist: ", style="dim green")
        rx_graph.append_text(Text.from_markup(spark_rx or "[dim]none[/dim]"))

        tx_graph = Text(no_wrap=True, overflow="crop")
        tx_graph.append("Tx Hist: ", style="dim magenta")
        tx_graph.append_text(Text.from_markup(spark_tx or "[dim]none[/dim]"))

        spark_row.add_row(rx_graph, tx_graph)
        main_table.add_row(spark_row)

        return Panel(
            main_table,
            box=ROUNDED,
            title="[bold yellow]Network Interfaces[/bold yellow]",
            title_align="left",
            border_style="yellow",
        )


class SystemWidget:
    """Renders System Sockets, PSI pressure stall, and process counters."""

    @staticmethod
    def render(snapshot: NodeSnapshot) -> Panel:
        sys = snapshot.system
        table = Table.grid(expand=True)
        table.add_column(ratio=1)
        table.add_column(ratio=1)
        table.add_column(ratio=1)

        col1 = Text()
        col1.append("Sockets: ", style="bold white")
        col1.append(f"{sys.sockets_used}\n", style="cyan")
        col1.append("TCP Estab: ", style="dim")
        col1.append(f"{sys.tcp_established} ", style="green")
        col1.append(f"(InUse: {sys.tcp_in_use}, TW: {sys.tcp_tw})\n", style="dim")
        col1.append("UDP InUse: ", style="dim")
        col1.append(f"{sys.udp_in_use}", style="yellow")

        col2 = Text()
        col2.append("Processes: \n", style="bold white")
        col2.append("Running: ", style="dim")
        col2.append(f"{sys.procs_running} ", style="bold green")
        col2.append("Blocked: ", style="dim")
        col2.append(f"{sys.procs_blocked}\n", style="bold red" if sys.procs_blocked > 0 else "dim")
        col2.append("Forks Total: ", style="dim")
        col2.append(f"{sys.forks_total:,}", style="dim white")

        col3 = Text()
        col3.append("File Descriptors:\n", style="bold white")
        if sys.fd_maximum > 100_000_000_000:
            col3.append("Allocated: ", style="dim")
            col3.append(f"{sys.fd_allocated:,}\n", style="cyan")
            col3.append("Max: ", style="dim")
            col3.append("unlimited", style="dim white")
        else:
            fd_pct = (sys.fd_allocated / sys.fd_maximum * 100.0) if sys.fd_maximum > 0 else 0.0
            col3.append("Allocated: ", style="dim")
            col3.append(f"{sys.fd_allocated:,} / {sys.fd_maximum:,} ", style="cyan")
            col3.append(f"({fd_pct:.1f}%)", style="dim")

        table.add_row(col1, col2, col3)

        return Panel(
            table,
            box=ROUNDED,
            title="[bold cyan]System & Sockets[/bold cyan]",
            title_align="left",
            border_style="cyan",
        )


class FooterWidget:
    """Renders hotkey navigation shortcuts and message line."""

    @staticmethod
    def render(status_msg: Optional[str] = None) -> Panel:
        grid = Table.grid(expand=True)
        grid.add_column(justify="left", ratio=7)
        grid.add_column(justify="right", ratio=3)

        keys_text = Text()
        shortcuts = [
            ("q", "Quit"),
            ("r", "Refresh"),
            ("+/-", "Speed"),
            ("1-4", "Panels"),
            ("s", "Snapshot"),
            ("h", "Help"),
        ]
        for key, desc in shortcuts:
            keys_text.append(f"[{key}] ", style="bold yellow")
            keys_text.append(f"{desc}  ", style="white")

        msg_text = Text()
        if status_msg:
            msg_text.append(status_msg, style="bold green")
        else:
            msg_text.append("lazytools nodetop v1.0", style="dim cyan")

        grid.add_row(keys_text, msg_text)
        return Panel(grid, box=SIMPLE, style="dim white")
