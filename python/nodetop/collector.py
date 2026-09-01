"""
Prometheus node_exporter metrics scraper, parser, and delta calculation engine.
"""

from dataclasses import dataclass, field
import re
import time
from typing import Any, Dict, List, Optional, Tuple
import urllib.error
import urllib.request


LABEL_PATTERN = re.compile(r'([a-zA-Z_][a-zA-Z0-9_]*)="([^"\\]*(?:\\.[^"\\]*)*)"')


@dataclass
class MetricFamily:
    name: str
    samples: List[Tuple[Dict[str, str], float]] = field(default_factory=list)


@dataclass
class CpuCoreMetrics:
    core_id: str
    usage_pct: float = 0.0
    user_pct: float = 0.0
    system_pct: float = 0.0
    iowait_pct: float = 0.0
    frequency_mhz: float = 0.0
    temperature_celsius: Optional[float] = None


@dataclass
class CpuSnapshot:
    overall_usage_pct: float = 0.0
    user_pct: float = 0.0
    system_pct: float = 0.0
    iowait_pct: float = 0.0
    idle_pct: float = 0.0
    cores: List[CpuCoreMetrics] = field(default_factory=list)
    package_temp_celsius: Optional[float] = None


@dataclass
class MemorySnapshot:
    total_bytes: float = 0.0
    free_bytes: float = 0.0
    available_bytes: float = 0.0
    buffers_bytes: float = 0.0
    cached_bytes: float = 0.0
    slab_bytes: float = 0.0
    dirty_bytes: float = 0.0
    swap_total_bytes: float = 0.0
    swap_free_bytes: float = 0.0

    @property
    def used_bytes(self) -> float:
        # If MemAvailable is present, used = total - available
        if self.available_bytes > 0:
            return max(0.0, self.total_bytes - self.available_bytes)
        return max(0.0, self.total_bytes - self.free_bytes - self.buffers_bytes - self.cached_bytes)

    @property
    def used_pct(self) -> float:
        if self.total_bytes > 0:
            return (self.used_bytes / self.total_bytes) * 100.0
        return 0.0

    @property
    def swap_used_bytes(self) -> float:
        return max(0.0, self.swap_total_bytes - self.swap_free_bytes)

    @property
    def swap_used_pct(self) -> float:
        if self.swap_total_bytes > 0:
            return (self.swap_used_bytes / self.swap_total_bytes) * 100.0
        return 0.0


@dataclass
class FilesystemMetrics:
    mountpoint: str
    device: str
    fstype: str
    total_bytes: float
    free_bytes: float
    avail_bytes: float

    @property
    def used_bytes(self) -> float:
        return max(0.0, self.total_bytes - self.free_bytes)

    @property
    def used_pct(self) -> float:
        if self.total_bytes > 0:
            return (self.used_bytes / self.total_bytes) * 100.0
        return 0.0


@dataclass
class DiskIoMetrics:
    device: str
    read_bytes_sec: float = 0.0
    write_bytes_sec: float = 0.0
    io_util_pct: float = 0.0
    read_iops: float = 0.0
    write_iops: float = 0.0


@dataclass
class NetworkInterfaceMetrics:
    interface: str
    rx_bytes_sec: float = 0.0
    tx_bytes_sec: float = 0.0
    rx_total_bytes: float = 0.0
    tx_total_bytes: float = 0.0
    rx_errs: float = 0.0
    tx_errs: float = 0.0
    rx_drop: float = 0.0
    tx_drop: float = 0.0
    is_up: bool = True


@dataclass
class SystemSnapshot:
    hostname: str = "unknown"
    os_name: str = ""
    kernel_release: str = ""
    machine_arch: str = ""
    uptime_seconds: float = 0.0
    boot_time: float = 0.0
    load1: float = 0.0
    load5: float = 0.0
    load15: float = 0.0
    procs_running: int = 0
    procs_blocked: int = 0
    forks_total: int = 0
    tcp_established: int = 0
    tcp_in_use: int = 0
    tcp_tw: int = 0
    udp_in_use: int = 0
    sockets_used: int = 0
    fd_allocated: int = 0
    fd_maximum: int = 0
    psi_cpu_stall_pct: float = 0.0
    psi_mem_stall_pct: float = 0.0
    psi_io_stall_pct: float = 0.0


@dataclass
class NodeSnapshot:
    timestamp: float
    latency_ms: float
    status_code: int = 200
    error: Optional[str] = None
    system: SystemSnapshot = field(default_factory=SystemSnapshot)
    cpu: CpuSnapshot = field(default_factory=CpuSnapshot)
    memory: MemorySnapshot = field(default_factory=MemorySnapshot)
    filesystems: List[FilesystemMetrics] = field(default_factory=list)
    disk_io: List[DiskIoMetrics] = field(default_factory=list)
    network: List[NetworkInterfaceMetrics] = field(default_factory=list)


def parse_prometheus_text(text: str) -> Dict[str, MetricFamily]:
    """
    Parses Prometheus text exposition format into metric families.
    """
    families: Dict[str, MetricFamily] = {}

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        idx = line.find("{")
        if idx != -1:
            name = line[:idx]
            rest = line[idx + 1 :]
            labels_part, val_part = rest.rsplit("}", 1)
            labels = dict(LABEL_PATTERN.findall(labels_part))
            try:
                val = float(val_part.strip())
            except ValueError:
                continue
        else:
            parts = line.split()
            if len(parts) < 2:
                continue
            name = parts[0]
            labels = {}
            try:
                val = float(parts[1])
            except ValueError:
                continue

        if name not in families:
            families[name] = MetricFamily(name=name)
        families[name].samples.append((labels, val))

    return families


class NodeExporterCollector:
    """
    Scrapes and computes system snapshots from Prometheus node_exporter.
    """

    def __init__(self, target_url: str, timeout: float = 3.0) -> None:
        self.target_url = self._normalize_url(target_url)
        self.timeout = timeout
        self.prev_timestamp: Optional[float] = None
        self.prev_cpu_modes: Dict[str, Dict[str, float]] = {}  # cpu -> {mode: seconds}
        self.prev_disk_io: Dict[str, Dict[str, float]] = {}    # dev -> {metric: val}
        self.prev_net_io: Dict[str, Dict[str, float]] = {}     # iface -> {rx: val, tx: val}
        self.prev_psi: Dict[str, float] = {}                   # psi_key -> seconds

    @staticmethod
    def _normalize_url(url: str) -> str:
        url = url.strip()
        if not url.startswith("http://") and not url.startswith("https://"):
            url = f"http://{url}"

        import urllib.parse
        parsed = urllib.parse.urlparse(url)
        netloc = parsed.netloc
        path = parsed.path

        # If no port specified in netloc and no custom sub-path
        if ":" not in netloc:
            if not path or path == "/":
                netloc = f"{netloc}:9100"

        if not path or path == "/":
            path = "/metrics"

        return urllib.parse.urlunparse(
            (parsed.scheme, netloc, path, parsed.params, parsed.query, parsed.fragment)
        )

    def fetch_metrics(self) -> Tuple[str, float, int]:
        """Fetch raw metrics payload, returning (data, latency_ms, status_code)."""
        req = urllib.request.Request(
            self.target_url,
            headers={"User-Agent": "lazytools-nodetop/1.0", "Accept": "text/plain"},
        )
        start = time.time()
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            data = resp.read().decode("utf-8", errors="replace")
            status = resp.status
        latency = (time.time() - start) * 1000.0
        return data, latency, status

    def collect(self) -> NodeSnapshot:
        """Collect and parse metrics, computing deltas for rates and utilization."""
        now = time.time()
        try:
            raw_text, latency, status_code = self.fetch_metrics()
        except urllib.error.URLError as err:
            return NodeSnapshot(
                timestamp=now,
                latency_ms=0.0,
                status_code=getattr(err, "code", 0) or 0,
                error=f"Connection failed: {err.reason if hasattr(err, 'reason') else err}",
            )
        except Exception as err:
            return NodeSnapshot(
                timestamp=now,
                latency_ms=0.0,
                status_code=0,
                error=f"Fetch error: {err}",
            )

        families = parse_prometheus_text(raw_text)
        delta_time = (now - self.prev_timestamp) if self.prev_timestamp else None
        self.prev_timestamp = now

        snapshot = NodeSnapshot(
            timestamp=now,
            latency_ms=latency,
            status_code=status_code,
            system=self._process_system(families, now),
            cpu=self._process_cpu(families, delta_time),
            memory=self._process_memory(families),
            filesystems=self._process_filesystems(families),
            disk_io=self._process_disk_io(families, delta_time),
            network=self._process_network(families, delta_time),
        )

        return snapshot

    def _get_first_val(self, families: Dict[str, MetricFamily], name: str, default: float = 0.0) -> float:
        fam = families.get(name)
        if fam and fam.samples:
            return fam.samples[0][1]
        return default

    def _process_system(self, families: Dict[str, MetricFamily], now: float) -> SystemSnapshot:
        sys_snap = SystemSnapshot()

        # uname info
        if "node_uname_info" in families:
            labels = families["node_uname_info"].samples[0][0]
            sys_snap.hostname = labels.get("nodename", "unknown")
            sys_snap.kernel_release = labels.get("release", "")
            sys_snap.machine_arch = labels.get("machine", "")

        # os info
        if "node_os_info" in families:
            labels = families["node_os_info"].samples[0][0]
            sys_snap.os_name = labels.get("pretty_name") or labels.get("name", "")

        # boot time & uptime
        boot_time = self._get_first_val(families, "node_boot_time_seconds")
        sys_snap.boot_time = boot_time
        if boot_time > 0:
            sys_snap.uptime_seconds = max(0.0, now - boot_time)

        # load averages
        sys_snap.load1 = self._get_first_val(families, "node_load1")
        sys_snap.load5 = self._get_first_val(families, "node_load5")
        sys_snap.load15 = self._get_first_val(families, "node_load15")

        # procs
        sys_snap.procs_running = int(self._get_first_val(families, "node_procs_running"))
        sys_snap.procs_blocked = int(self._get_first_val(families, "node_procs_blocked"))
        sys_snap.forks_total = int(self._get_first_val(families, "node_forks_total"))

        # sockets & netstat
        sys_snap.tcp_established = int(self._get_first_val(families, "node_netstat_Tcp_CurrEstab"))
        sys_snap.tcp_in_use = int(self._get_first_val(families, "node_sockstat_TCP_inuse"))
        sys_snap.tcp_tw = int(self._get_first_val(families, "node_sockstat_TCP_tw"))
        sys_snap.udp_in_use = int(self._get_first_val(families, "node_sockstat_UDP_inuse"))
        sys_snap.sockets_used = int(self._get_first_val(families, "node_sockstat_sockets_used"))

        # file descriptors
        sys_snap.fd_allocated = int(self._get_first_val(families, "node_filefd_allocated"))
        sys_snap.fd_maximum = int(self._get_first_val(families, "node_filefd_maximum"))

        # Pressure Stall Information (PSI)
        # We calculate delta stall / delta time if available
        return sys_snap

    def _process_cpu(
        self, families: Dict[str, MetricFamily], delta_time: Optional[float]
    ) -> CpuSnapshot:
        cpu_snap = CpuSnapshot()
        cpu_modes: Dict[str, Dict[str, float]] = {}

        if "node_cpu_seconds_total" in families:
            for labels, val in families["node_cpu_seconds_total"].samples:
                cpu_id = labels.get("cpu", "0")
                mode = labels.get("mode", "idle")
                if cpu_id not in cpu_modes:
                    cpu_modes[cpu_id] = {}
                cpu_modes[cpu_id][mode] = val

        # Scaling frequency
        freqs: Dict[str, float] = {}
        freq_fam = families.get("node_cpu_scaling_frequency_hertz") or families.get("node_cpu_frequency_hertz")
        if freq_fam:
            for labels, val in freq_fam.samples:
                cpu_id = labels.get("cpu", "")
                if cpu_id:
                    freqs[cpu_id] = val / 1e6  # to MHz

        # Temperatures
        temps: Dict[str, float] = {}
        pkg_temp: Optional[float] = None

        if "node_hwmon_temp_celsius" in families:
            for labels, val in families["node_hwmon_temp_celsius"].samples:
                chip = labels.get("chip", "")
                sensor = labels.get("sensor", "")
                if "coretemp" in chip:
                    if sensor == "temp1" and pkg_temp is None:
                        pkg_temp = val
                    # Core mapping
                    try:
                        idx = int(sensor.replace("temp", "")) - 2
                        if idx >= 0:
                            temps[str(idx)] = val
                    except ValueError:
                        pass
        if pkg_temp is None and "node_thermal_zone_temp" in families:
            for labels, val in families["node_thermal_zone_temp"].samples:
                if labels.get("type") == "x86_pkg_temp":
                    pkg_temp = val
                    break

        cpu_snap.package_temp_celsius = pkg_temp

        # Sort CPU IDs numerically
        sorted_cpus = sorted(cpu_modes.keys(), key=lambda x: int(x) if x.isdigit() else x)

        if not self.prev_cpu_modes or not delta_time or delta_time <= 0:
            # First run: initialize without deltas
            self.prev_cpu_modes = cpu_modes
            for cpu_id in sorted_cpus:
                cpu_snap.cores.append(
                    CpuCoreMetrics(
                        core_id=cpu_id,
                        frequency_mhz=freqs.get(cpu_id, 0.0),
                        temperature_celsius=temps.get(cpu_id, pkg_temp),
                    )
                )
            return cpu_snap

        total_active_all = 0.0
        total_delta_all = 0.0
        total_user_all = 0.0
        total_system_all = 0.0
        total_iowait_all = 0.0
        total_idle_all = 0.0

        for cpu_id in sorted_cpus:
            curr = cpu_modes[cpu_id]
            prev = self.prev_cpu_modes.get(cpu_id, {})

            deltas: Dict[str, float] = {}
            for m, val in curr.items():
                prev_val = prev.get(m, val)
                deltas[m] = max(0.0, val - prev_val)

            core_delta = sum(deltas.values())
            idle_delta = deltas.get("idle", 0.0)
            user_delta = deltas.get("user", 0.0) + deltas.get("nice", 0.0)
            sys_delta = deltas.get("system", 0.0) + deltas.get("irq", 0.0) + deltas.get("softirq", 0.0)
            iowait_delta = deltas.get("iowait", 0.0)
            active_delta = max(0.0, core_delta - idle_delta)

            usage_pct = (active_delta / core_delta * 100.0) if core_delta > 0 else 0.0
            u_pct = (user_delta / core_delta * 100.0) if core_delta > 0 else 0.0
            s_pct = (sys_delta / core_delta * 100.0) if core_delta > 0 else 0.0
            io_pct = (iowait_delta / core_delta * 100.0) if core_delta > 0 else 0.0

            total_active_all += active_delta
            total_delta_all += core_delta
            total_user_all += user_delta
            total_system_all += sys_delta
            total_iowait_all += iowait_delta
            total_idle_all += idle_delta

            cpu_snap.cores.append(
                CpuCoreMetrics(
                    core_id=cpu_id,
                    usage_pct=min(100.0, usage_pct),
                    user_pct=u_pct,
                    system_pct=s_pct,
                    iowait_pct=io_pct,
                    frequency_mhz=freqs.get(cpu_id, 0.0),
                    temperature_celsius=temps.get(cpu_id, pkg_temp),
                )
            )

        self.prev_cpu_modes = cpu_modes

        if total_delta_all > 0:
            cpu_snap.overall_usage_pct = min(100.0, (total_active_all / total_delta_all) * 100.0)
            cpu_snap.user_pct = (total_user_all / total_delta_all) * 100.0
            cpu_snap.system_pct = (total_system_all / total_delta_all) * 100.0
            cpu_snap.iowait_pct = (total_iowait_all / total_delta_all) * 100.0
            cpu_snap.idle_pct = (total_idle_all / total_delta_all) * 100.0

        return cpu_snap

    def _process_memory(self, families: Dict[str, MetricFamily]) -> MemorySnapshot:
        return MemorySnapshot(
            total_bytes=self._get_first_val(families, "node_memory_MemTotal_bytes"),
            free_bytes=self._get_first_val(families, "node_memory_MemFree_bytes"),
            available_bytes=self._get_first_val(families, "node_memory_MemAvailable_bytes"),
            buffers_bytes=self._get_first_val(families, "node_memory_Buffers_bytes"),
            cached_bytes=self._get_first_val(families, "node_memory_Cached_bytes"),
            slab_bytes=self._get_first_val(families, "node_memory_Slab_bytes"),
            dirty_bytes=self._get_first_val(families, "node_memory_Dirty_bytes"),
            swap_total_bytes=self._get_first_val(families, "node_memory_SwapTotal_bytes"),
            swap_free_bytes=self._get_first_val(families, "node_memory_SwapFree_bytes"),
        )

    def _process_filesystems(self, families: Dict[str, MetricFamily]) -> List[FilesystemMetrics]:
        results: List[FilesystemMetrics] = []
        if "node_filesystem_size_bytes" not in families:
            return results

        free_map: Dict[Tuple[str, str], float] = {}
        avail_map: Dict[Tuple[str, str], float] = {}

        if "node_filesystem_free_bytes" in families:
            for labels, val in families["node_filesystem_free_bytes"].samples:
                free_map[(labels.get("mountpoint", ""), labels.get("device", ""))] = val

        if "node_filesystem_avail_bytes" in families:
            for labels, val in families["node_filesystem_avail_bytes"].samples:
                avail_map[(labels.get("mountpoint", ""), labels.get("device", ""))] = val

        ignored_types = {"tmpfs", "devtmpfs", "overlay", "squashfs", "iso9660", "autofs"}

        for labels, size in families["node_filesystem_size_bytes"].samples:
            mp = labels.get("mountpoint", "")
            dev = labels.get("device", "")
            fstype = labels.get("fstype", "")

            # Filter pseudo/virtual fs, keeping real disks or main mounts
            if fstype in ignored_types and mp != "/":
                continue
            if size <= 0:
                continue

            key = (mp, dev)
            results.append(
                FilesystemMetrics(
                    mountpoint=mp,
                    device=dev,
                    fstype=fstype,
                    total_bytes=size,
                    free_bytes=free_map.get(key, 0.0),
                    avail_bytes=avail_map.get(key, 0.0),
                )
            )

        # Sort: root '/' first, then by mountpoint
        results.sort(key=lambda x: (0 if x.mountpoint == "/" else 1, x.mountpoint))
        return results

    def _process_disk_io(
        self, families: Dict[str, MetricFamily], delta_time: Optional[float]
    ) -> List[DiskIoMetrics]:
        reads: Dict[str, float] = {}
        writes: Dict[str, float] = {}
        io_times: Dict[str, float] = {}
        reads_ops: Dict[str, float] = {}
        writes_ops: Dict[str, float] = {}

        if "node_disk_read_bytes_total" in families:
            for labels, val in families["node_disk_read_bytes_total"].samples:
                reads[labels.get("device", "")] = val
        if "node_disk_written_bytes_total" in families:
            for labels, val in families["node_disk_written_bytes_total"].samples:
                writes[labels.get("device", "")] = val
        if "node_disk_io_time_seconds_total" in families:
            for labels, val in families["node_disk_io_time_seconds_total"].samples:
                io_times[labels.get("device", "")] = val
        if "node_disk_reads_completed_total" in families:
            for labels, val in families["node_disk_reads_completed_total"].samples:
                reads_ops[labels.get("device", "")] = val
        if "node_disk_writes_completed_total" in families:
            for labels, val in families["node_disk_writes_completed_total"].samples:
                writes_ops[labels.get("device", "")] = val

        results: List[DiskIoMetrics] = []
        all_devs = sorted(set(reads.keys()) | set(writes.keys()))

        # Filter out ram/loop devices
        all_devs = [d for d in all_devs if not d.startswith(("ram", "loop"))]

        for dev in all_devs:
            curr_read = reads.get(dev, 0.0)
            curr_write = writes.get(dev, 0.0)
            curr_io_time = io_times.get(dev, 0.0)
            curr_rops = reads_ops.get(dev, 0.0)
            curr_wops = writes_ops.get(dev, 0.0)

            prev = self.prev_disk_io.get(dev, {})
            read_rate = 0.0
            write_rate = 0.0
            util_pct = 0.0
            rops_rate = 0.0
            wops_rate = 0.0

            if prev and delta_time and delta_time > 0:
                d_read = max(0.0, curr_read - prev.get("read", curr_read))
                d_write = max(0.0, curr_write - prev.get("write", curr_write))
                d_io_time = max(0.0, curr_io_time - prev.get("io_time", curr_io_time))
                d_rops = max(0.0, curr_rops - prev.get("rops", curr_rops))
                d_wops = max(0.0, curr_wops - prev.get("wops", curr_wops))

                read_rate = d_read / delta_time
                write_rate = d_write / delta_time
                util_pct = min(100.0, (d_io_time / delta_time) * 100.0)
                rops_rate = d_rops / delta_time
                wops_rate = d_wops / delta_time

            self.prev_disk_io[dev] = {
                "read": curr_read,
                "write": curr_write,
                "io_time": curr_io_time,
                "rops": curr_rops,
                "wops": curr_wops,
            }

            results.append(
                DiskIoMetrics(
                    device=dev,
                    read_bytes_sec=read_rate,
                    write_bytes_sec=write_rate,
                    io_util_pct=util_pct,
                    read_iops=rops_rate,
                    write_iops=wops_rate,
                )
            )

        return results

    def _process_network(
        self, families: Dict[str, MetricFamily], delta_time: Optional[float]
    ) -> List[NetworkInterfaceMetrics]:
        rx_map: Dict[str, float] = {}
        tx_map: Dict[str, float] = {}
        rx_errs: Dict[str, float] = {}
        tx_errs: Dict[str, float] = {}
        rx_drops: Dict[str, float] = {}
        tx_drops: Dict[str, float] = {}
        up_map: Dict[str, bool] = {}

        if "node_network_receive_bytes_total" in families:
            for labels, val in families["node_network_receive_bytes_total"].samples:
                rx_map[labels.get("device", "")] = val
        if "node_network_transmit_bytes_total" in families:
            for labels, val in families["node_network_transmit_bytes_total"].samples:
                tx_map[labels.get("device", "")] = val
        if "node_network_receive_errs_total" in families:
            for labels, val in families["node_network_receive_errs_total"].samples:
                rx_errs[labels.get("device", "")] = val
        if "node_network_transmit_errs_total" in families:
            for labels, val in families["node_network_transmit_errs_total"].samples:
                tx_errs[labels.get("device", "")] = val
        if "node_network_receive_drop_total" in families:
            for labels, val in families["node_network_receive_drop_total"].samples:
                rx_drops[labels.get("device", "")] = val
        if "node_network_transmit_drop_total" in families:
            for labels, val in families["node_network_transmit_drop_total"].samples:
                tx_drops[labels.get("device", "")] = val
        if "node_network_up" in families:
            for labels, val in families["node_network_up"].samples:
                up_map[labels.get("device", "")] = bool(val > 0)

        results: List[NetworkInterfaceMetrics] = []
        all_ifaces = sorted(set(rx_map.keys()) | set(tx_map.keys()))

        for iface in all_ifaces:
            curr_rx = rx_map.get(iface, 0.0)
            curr_tx = tx_map.get(iface, 0.0)
            prev = self.prev_net_io.get(iface, {})

            rx_rate = 0.0
            tx_rate = 0.0

            if prev and delta_time and delta_time > 0:
                d_rx = max(0.0, curr_rx - prev.get("rx", curr_rx))
                d_tx = max(0.0, curr_tx - prev.get("tx", curr_tx))
                rx_rate = d_rx / delta_time
                tx_rate = d_tx / delta_time

            self.prev_net_io[iface] = {"rx": curr_rx, "tx": curr_tx}

            results.append(
                NetworkInterfaceMetrics(
                    interface=iface,
                    rx_bytes_sec=rx_rate,
                    tx_bytes_sec=tx_rate,
                    rx_total_bytes=curr_rx,
                    tx_total_bytes=curr_tx,
                    rx_errs=rx_errs.get(iface, 0.0),
                    tx_errs=tx_errs.get(iface, 0.0),
                    rx_drop=rx_drops.get(iface, 0.0),
                    tx_drop=tx_drops.get(iface, 0.0),
                    is_up=up_map.get(iface, True),
                )
            )

        # Order: Active non-loopback with traffic/up first, lo last
        results.sort(
            key=lambda x: (
                1 if x.interface == "lo" else 0,
                0 if (x.rx_bytes_sec > 0 or x.tx_bytes_sec > 0 or x.is_up) else 1,
                x.interface,
            )
        )
        return results
