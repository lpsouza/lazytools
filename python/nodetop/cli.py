"""
Command-line interface and argument parsing for nodetop.
"""

import argparse
import os
import sys

from nodetop import __version__
from nodetop.ui import NodetopApp


def parse_args(args=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="nodetop",
        description="A btop-inspired terminal monitoring dashboard for Prometheus node_exporter.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  nodetop                            # Connect to default http://localhost:9100
  nodetop ukitake                    # Connect to http://ukitake:9100
  nodetop http://ukitake:9100        # Connect to explicit URL
  nodetop ukitake -i 0.5             # Scrape every 500ms
  nodetop ukitake --once             # Print single snapshot summary and exit
        """,
    )

    default_target = (
        os.environ.get("NODETOP_URL")
        or os.environ.get("NODE_EXPORTER_URL")
        or "http://localhost:9100"
    )

    parser.add_argument(
        "target",
        nargs="?",
        default=default_target,
        help=f"Target node_exporter host or URL (default: {default_target})",
    )
    parser.add_argument(
        "-i",
        "--interval",
        type=float,
        default=1.0,
        help="Scrape and dashboard refresh interval in seconds (default: 1.0)",
    )
    parser.add_argument(
        "-t",
        "--timeout",
        type=float,
        default=3.0,
        help="HTTP connection timeout in seconds (default: 3.0)",
    )
    parser.add_argument(
        "-o",
        "--once",
        action="store_true",
        help="Capture a single snapshot, print formatted metrics, and exit",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable ANSI colored output",
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    return parser.parse_args(args)


def main(args=None) -> int:
    parsed = parse_args(args)

    app = NodetopApp(
        target_url=parsed.target,
        interval=parsed.interval,
        timeout=parsed.timeout,
        no_color=parsed.no_color,
    )

    if parsed.once:
        app.print_snapshot_once()
        return 0

    return app.run()


if __name__ == "__main__":
    sys.exit(main())
