#!/usr/bin/env python3
"""Unified CLI for ESXi subnet scanning and IXP API ping testing."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from esxi_scanner import run_scan
from ixp_ping import run_ping


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fast ESXi subnet scanner and IXP API ping tester",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    scan = sub.add_parser("scan", help="Scan CIDR subnets for VMware ESXi hosts")
    scan.add_argument(
        "--subnets",
        default="subnets.txt",
        help="Path to subnet list file (default: subnets.txt)",
    )
    scan.add_argument(
        "--output",
        default="esxi_hosts.txt",
        help="Output file for discovered ESXi IPs (default: esxi_hosts.txt)",
    )
    scan.add_argument(
        "--concurrency",
        type=int,
        default=200,
        help="Max concurrent probe tasks (default: 200)",
    )
    scan.add_argument(
        "--timeout",
        type=float,
        default=2.5,
        help="Per-host connection timeout in seconds (default: 2.5)",
    )

    ping = sub.add_parser("ping", help="Ping targets via the IXP API")
    ping.add_argument(
        "target",
        help="Single IP/domain or path to a file of targets",
    )
    ping.add_argument(
        "--output",
        default="ping_report.txt",
        help="Ping report output file (default: ping_report.txt)",
    )
    ping.add_argument(
        "--probe-node-id",
        type=int,
        default=5,
        dest="probe_node_id",
        help="IXP probe_node_id (default: 5)",
    )

    both = sub.add_parser(
        "both",
        help="Scan for ESXi hosts, then ping discovered IPs via IXP",
    )
    both.add_argument(
        "--subnets",
        default="subnets.txt",
        help="Path to subnet list file (default: subnets.txt)",
    )
    both.add_argument(
        "--scan-output",
        default="esxi_hosts.txt",
        help="Output file for discovered ESXi IPs (default: esxi_hosts.txt)",
    )
    both.add_argument(
        "--ping-output",
        default="ping_report.txt",
        help="Ping report output file (default: ping_report.txt)",
    )
    both.add_argument(
        "--concurrency",
        type=int,
        default=200,
        help="Max concurrent probe tasks (default: 200)",
    )
    both.add_argument(
        "--timeout",
        type=float,
        default=2.5,
        help="Per-host connection timeout in seconds (default: 2.5)",
    )
    both.add_argument(
        "--probe-node-id",
        type=int,
        default=5,
        dest="probe_node_id",
        help="IXP probe_node_id (default: 5)",
    )

    return parser


def cmd_scan(args: argparse.Namespace) -> int:
    subnets = Path(args.subnets)
    if not subnets.is_file():
        print(f"[error] Subnets file not found: {subnets}")
        return 1
    run_scan(
        subnets_file=subnets,
        output_file=args.output,
        concurrency=args.concurrency,
        timeout=args.timeout,
    )
    return 0


def cmd_ping(args: argparse.Namespace) -> int:
    run_ping(
        target=args.target,
        output_file=args.output,
        probe_node_id=args.probe_node_id,
    )
    return 0


def cmd_both(args: argparse.Namespace) -> int:
    subnets = Path(args.subnets)
    if not subnets.is_file():
        print(f"[error] Subnets file not found: {subnets}")
        return 1

    found = run_scan(
        subnets_file=subnets,
        output_file=args.scan_output,
        concurrency=args.concurrency,
        timeout=args.timeout,
    )
    if not found:
        print("[info] No ESXi hosts discovered; skipping ping.")
        return 0

    run_ping(
        target=str(args.scan_output),
        output_file=args.ping_output,
        probe_node_id=args.probe_node_id,
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "scan":
        return cmd_scan(args)
    if args.command == "ping":
        return cmd_ping(args)
    if args.command == "both":
        return cmd_both(args)
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
