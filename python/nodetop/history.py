"""
Metrics history ring buffer and sparkline generator.
"""

from collections import deque
from typing import Deque, Dict, List, Optional


SPARK_CHARS = (" ", "▂", "▃", "▄", "▅", "▆", "▇", "█")


def render_sparkline(
    values: List[float],
    min_val: Optional[float] = None,
    max_val: Optional[float] = None,
    max_chars: Optional[int] = None,
) -> str:
    """
    Renders a list of float values as a Unicode sparkline.
    """
    if not values:
        return ""

    if max_chars is not None and max_chars > 0:
        values = values[-max_chars:]

    actual_min = min_val if min_val is not None else min(values)
    actual_max = max_val if max_val is not None else max(values)

    val_range = actual_max - actual_min
    if val_range <= 0:
        return SPARK_CHARS[0] * len(values)

    result = []
    num_chars = len(SPARK_CHARS)
    for v in values:
        clamped = max(actual_min, min(actual_max, v))
        norm = (clamped - actual_min) / val_range
        idx = int(norm * (num_chars - 1))
        result.append(SPARK_CHARS[idx])

    return "".join(result)


def render_sparkline_colored(
    values: List[float],
    min_val: float = 0.0,
    max_val: float = 100.0,
    max_chars: Optional[int] = None,
    low_color: str = "green",
    mid_color: str = "yellow",
    high_color: str = "red",
) -> str:
    """
    Renders a sparkline with Rich markup colors based on percentage thresholds.
    """
    if not values:
        return ""

    if max_chars is not None and max_chars > 0:
        values = values[-max_chars:]

    val_range = max_val - min_val
    if val_range <= 0:
        return SPARK_CHARS[0] * len(values)

    num_chars = len(SPARK_CHARS)
    result = []
    for v in values:
        clamped = max(min_val, min(max_val, v))
        norm = (clamped - min_val) / val_range
        idx = int(norm * (num_chars - 1))
        char = SPARK_CHARS[idx]

        if norm < 0.6:
            color = low_color
        elif norm < 0.85:
            color = mid_color
        else:
            color = high_color

        result.append(f"[{color}]{char}[/{color}]")

    return "".join(result)


class MetricsHistory:
    """
    Tracks rolling history for key metrics to provide sparkline graphs.
    """

    def __init__(self, max_samples: int = 60) -> None:
        self.max_samples = max_samples
        self.cpu_overall: Deque[float] = deque(maxlen=max_samples)
        self.memory_used_pct: Deque[float] = deque(maxlen=max_samples)
        self.net_rx_rate: Deque[float] = deque(maxlen=max_samples)
        self.net_tx_rate: Deque[float] = deque(maxlen=max_samples)
        self.disk_read_rate: Deque[float] = deque(maxlen=max_samples)
        self.disk_write_rate: Deque[float] = deque(maxlen=max_samples)
        self.per_core_cpu: Dict[str, Deque[float]] = {}

    def push(
        self,
        cpu_pct: float,
        mem_pct: float,
        net_rx: float,
        net_tx: float,
        disk_read: float,
        disk_write: float,
        per_core: Optional[Dict[str, float]] = None,
    ) -> None:
        """Append latest metric values to history buffers."""
        self.cpu_overall.append(cpu_pct)
        self.memory_used_pct.append(mem_pct)
        self.net_rx_rate.append(net_rx)
        self.net_tx_rate.append(net_tx)
        self.disk_read_rate.append(disk_read)
        self.disk_write_rate.append(disk_write)

        if per_core:
            for core_id, pct in per_core.items():
                if core_id not in self.per_core_cpu:
                    self.per_core_cpu[core_id] = deque(maxlen=self.max_samples)
                self.per_core_cpu[core_id].append(pct)
