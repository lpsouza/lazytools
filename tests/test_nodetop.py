"""
Unit tests for nodetop collector, history, sparkline, and formatters.
"""

import sys
import unittest
from pathlib import Path

# Add python directory to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "python"))

from nodetop.collector import NodeExporterCollector, parse_prometheus_text
from nodetop.history import MetricsHistory, render_sparkline, render_sparkline_colored
from nodetop.widgets import format_bytes, format_duration, make_color_pct, make_meter_bar


class TestNodetopCollector(unittest.TestCase):

    def test_url_normalization(self):
        norm = NodeExporterCollector._normalize_url
        self.assertEqual(norm("http://localhost:9100"), "http://localhost:9100/metrics")
        self.assertEqual(norm("localhost:9100"), "http://localhost:9100/metrics")
        self.assertEqual(norm("ukitake"), "http://ukitake:9100/metrics")
        self.assertEqual(norm("ukitake:9100"), "http://ukitake:9100/metrics")
        self.assertEqual(norm("http://ukitake:9100/metrics"), "http://ukitake:9100/metrics")
        self.assertEqual(norm("https://metrics.corp.internal/node"), "https://metrics.corp.internal/node")

    def test_parse_prometheus_text(self):
        sample = """
        # HELP node_boot_time_seconds Node boot time, in seconds.
        # TYPE node_boot_time_seconds gauge
        node_boot_time_seconds 1.788218507e+09
        # HELP node_cpu_seconds_total Seconds the CPUs spent in each mode.
        # TYPE node_cpu_seconds_total counter
        node_cpu_seconds_total{cpu="0",mode="idle"} 13532.3
        node_cpu_seconds_total{cpu="0",mode="user"} 76.32
        node_load1 0.25
        """
        families = parse_prometheus_text(sample)

        self.assertIn("node_boot_time_seconds", families)
        self.assertIn("node_cpu_seconds_total", families)
        self.assertIn("node_load1", families)

        boot_fam = families["node_boot_time_seconds"]
        self.assertEqual(len(boot_fam.samples), 1)
        self.assertEqual(boot_fam.samples[0][0], {})
        self.assertAlmostEqual(boot_fam.samples[0][1], 1.788218507e+09)

        cpu_fam = families["node_cpu_seconds_total"]
        self.assertEqual(len(cpu_fam.samples), 2)
        self.assertEqual(cpu_fam.samples[0][0], {"cpu": "0", "mode": "idle"})
        self.assertAlmostEqual(cpu_fam.samples[0][1], 13532.3)
        self.assertEqual(cpu_fam.samples[1][0], {"cpu": "0", "mode": "user"})
        self.assertAlmostEqual(cpu_fam.samples[1][1], 76.32)

    def test_cpu_delta_calculation(self):
        collector = NodeExporterCollector("http://localhost:9100")

        sample_t0 = """
        node_cpu_seconds_total{cpu="0",mode="idle"} 100.0
        node_cpu_seconds_total{cpu="0",mode="user"} 10.0
        node_cpu_seconds_total{cpu="0",mode="system"} 10.0
        """
        families_t0 = parse_prometheus_text(sample_t0)
        snap_t0 = collector._process_cpu(families_t0, delta_time=None)
        self.assertEqual(snap_t0.overall_usage_pct, 0.0)

        # 1 second later: 1.0s user, 0.0s system, 0.0s idle -> 100% active
        sample_t1 = """
        node_cpu_seconds_total{cpu="0",mode="idle"} 100.0
        node_cpu_seconds_total{cpu="0",mode="user"} 11.0
        node_cpu_seconds_total{cpu="0",mode="system"} 10.0
        """
        families_t1 = parse_prometheus_text(sample_t1)
        snap_t1 = collector._process_cpu(families_t1, delta_time=1.0)
        self.assertAlmostEqual(snap_t1.overall_usage_pct, 100.0)
        self.assertEqual(len(snap_t1.cores), 1)
        self.assertAlmostEqual(snap_t1.cores[0].usage_pct, 100.0)

    def test_interface_tier_classification(self):
        self.assertEqual(NodeExporterCollector._classify_interface_tier("eth0"), 0)
        self.assertEqual(NodeExporterCollector._classify_interface_tier("enp60s0"), 0)
        self.assertEqual(NodeExporterCollector._classify_interface_tier("tailscale0"), 0)
        self.assertEqual(NodeExporterCollector._classify_interface_tier("wg0"), 0)
        self.assertEqual(NodeExporterCollector._classify_interface_tier("docker0"), 1)
        self.assertEqual(NodeExporterCollector._classify_interface_tier("macvtap0"), 1)
        self.assertEqual(NodeExporterCollector._classify_interface_tier("br-469514f6ae65"), 2)
        self.assertEqual(NodeExporterCollector._classify_interface_tier("veth423966c"), 2)
        self.assertEqual(NodeExporterCollector._classify_interface_tier("lo"), 4)

    def test_network_interface_processing_and_up_state(self):
        collector = NodeExporterCollector("http://localhost:9100")
        sample = """
        node_network_receive_bytes_total{device="enp60s0"} 5000
        node_network_transmit_bytes_total{device="enp60s0"} 5000
        node_network_up{device="enp60s0"} 1

        node_network_receive_bytes_total{device="tailscale0"} 8000
        node_network_transmit_bytes_total{device="tailscale0"} 8000
        node_network_up{device="tailscale0"} 0
        node_network_carrier{device="tailscale0"} 1
        node_network_info{device="tailscale0",operstate="unknown",adminstate="up"} 1

        node_network_receive_bytes_total{device="br-469514f6ae65"} 2000
        node_network_transmit_bytes_total{device="br-469514f6ae65"} 2000
        node_network_up{device="br-469514f6ae65"} 1

        node_network_receive_bytes_total{device="veth423966c"} 1000
        node_network_transmit_bytes_total{device="veth423966c"} 1000
        node_network_up{device="veth423966c"} 1

        node_network_receive_bytes_total{device="lo"} 500
        node_network_transmit_bytes_total{device="lo"} 500
        node_network_up{device="lo"} 0
        """
        families = parse_prometheus_text(sample)
        ifaces = collector._process_network(families, delta_time=1.0)

        # Check tailscale0 is correctly identified as is_up=True
        tailscale_iface = next(i for i in ifaces if i.interface == "tailscale0")
        self.assertTrue(tailscale_iface.is_up)

        # Check sorting order: Tier 0 (tailscale0 & enp60s0) at the top, then Tier 1/2, then lo
        names = [i.interface for i in ifaces]
        self.assertEqual(names[0], "tailscale0")  # Tier 0, 16000 total bytes
        self.assertEqual(names[1], "enp60s0")      # Tier 0, 10000 total bytes
        self.assertEqual(names[2], "br-469514f6ae65")  # Tier 2, 4000 total bytes
        self.assertEqual(names[3], "veth423966c")      # Tier 2, 2000 total bytes
        self.assertEqual(names[4], "lo")               # Tier 4


class TestNodetopHistoryAndFormatters(unittest.TestCase):

    def test_sparkline(self):
        empty = render_sparkline([])
        self.assertEqual(empty, "")

        flat = render_sparkline([50.0, 50.0, 50.0])
        self.assertEqual(len(flat), 3)

        ramp = render_sparkline([0.0, 50.0, 100.0], min_val=0.0, max_val=100.0)
        self.assertEqual(len(ramp), 3)
        self.assertEqual(ramp[0], " ")
        self.assertEqual(ramp[-1], "█")

        truncated = render_sparkline([1.0, 2.0, 3.0, 4.0, 5.0], max_chars=3)
        self.assertEqual(len(truncated), 3)

    def test_history_buffer(self):
        hist = MetricsHistory(max_samples=5)
        for i in range(10):
            hist.push(
                cpu_pct=float(i),
                mem_pct=10.0,
                net_rx=100.0,
                net_tx=200.0,
                disk_read=10.0,
                disk_write=20.0,
            )
        self.assertEqual(len(hist.cpu_overall), 5)
        self.assertEqual(list(hist.cpu_overall), [5.0, 6.0, 7.0, 8.0, 9.0])

    def test_format_bytes(self):
        self.assertEqual(format_bytes(0), "0 B")
        self.assertEqual(format_bytes(1024), "1.00 KB")
        self.assertEqual(format_bytes(1024 * 1024), "1.00 MB")
        self.assertEqual(format_bytes(1024 * 1024 * 1024 * 5.5), "5.50 GB")
        self.assertEqual(format_bytes(2048, is_rate=True), "2.00 KB/s")

    def test_format_duration(self):
        self.assertEqual(format_duration(0), "0s")
        self.assertEqual(format_duration(45), "45s")
        self.assertEqual(format_duration(125), "2m 5s")
        self.assertEqual(format_duration(3665), "1h 1m")
        self.assertEqual(format_duration(90000), "1d 1h")

    def test_meter_bar(self):
        bar_0 = make_meter_bar(0.0, width=10)
        self.assertIn("░" * 10, bar_0.plain)

        bar_100 = make_meter_bar(100.0, width=10)
        self.assertIn("█" * 10, bar_100.plain)


if __name__ == "__main__":
    unittest.main()
