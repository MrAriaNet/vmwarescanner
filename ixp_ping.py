"""Automated IXP API ping tester."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
from tabulate import tabulate

IXP_PING_URL = "https://ixp.ir/api/ping-test"
REQUEST_TIMEOUT = 10.0


def load_targets(target: str) -> list[str]:
    """
    Resolve a single IP/domain or a file path into a list of targets.
    If `target` exists as a file, read lines (skip blanks and # comments).
    Otherwise treat it as a single host.
    """
    path = Path(target)
    if path.is_file():
        targets: list[str] = []
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                targets.append(line)
        return targets
    return [target.strip()] if target.strip() else []


def _extract_global_status(payload: Any) -> str | None:
    """Pull global_status from nested IXP response JSON."""
    if not isinstance(payload, dict):
        return None
    data = payload.get("data")
    if isinstance(data, dict):
        inner = data.get("data")
        if isinstance(inner, dict) and "global_status" in inner:
            return str(inner["global_status"])
        if "global_status" in data:
            return str(data["global_status"])
    if "global_status" in payload:
        return str(payload["global_status"])
    return None


def ping_target(
    client: httpx.Client,
    target: str,
    probe_node_id: int = 5,
) -> dict[str, str]:
    """POST a single ping-test request and return Target/Status/Details."""
    try:
        response = client.post(
            IXP_PING_URL,
            headers={"Content-Type": "application/json"},
            json={"target": target, "probe_node_id": probe_node_id},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        try:
            payload = response.json()
        except ValueError:
            return {
                "Target": target,
                "Status": "Disconnected",
                "Details": "Invalid JSON response",
            }

        global_status = _extract_global_status(payload)
        if global_status is None:
            return {
                "Target": target,
                "Status": "Disconnected",
                "Details": "Missing global_status in response",
            }

        if global_status.lower() == "up":
            return {
                "Target": target,
                "Status": "Connected",
                "Details": f"global_status={global_status}",
            }
        return {
            "Target": target,
            "Status": "Disconnected",
            "Details": f"global_status={global_status}",
        }
    except httpx.TimeoutException:
        return {
            "Target": target,
            "Status": "Disconnected",
            "Details": "Request timed out (10s)",
        }
    except httpx.HTTPStatusError as exc:
        return {
            "Target": target,
            "Status": "Disconnected",
            "Details": f"HTTP {exc.response.status_code}",
        }
    except httpx.HTTPError as exc:
        return {
            "Target": target,
            "Status": "Disconnected",
            "Details": str(exc) or exc.__class__.__name__,
        }


def write_report(results: list[dict[str, str]], output_file: str | Path) -> None:
    """Write a timestamped table report to output_file."""
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    table = tabulate(
        [[r["Target"], r["Status"], r["Details"]] for r in results],
        headers=["Target", "Status", "Details"],
        tablefmt="simple",
    )
    content = f"=== Ping Test Report ({stamp}) ===\n\n{table}\n"
    Path(output_file).write_text(content, encoding="utf-8")


def run_ping(
    target: str,
    output_file: str | Path = "ping_report.txt",
    probe_node_id: int = 5,
) -> list[dict[str, str]]:
    """
    Ping one or more targets via the IXP API.
    Prints live progress and writes ping_report.txt on completion.
    """
    targets = load_targets(target)
    if not targets:
        print(f"[error] No targets resolved from '{target}'")
        return []

    print(f"Pinging {len(targets)} target(s) via IXP API (probe_node_id={probe_node_id})")
    results: list[dict[str, str]] = []

    with httpx.Client() as client:
        for i, host in enumerate(targets, start=1):
            result = ping_target(client, host, probe_node_id=probe_node_id)
            results.append(result)
            print(
                f"[{i}/{len(targets)}] {result['Target']}: "
                f"{result['Status']} ({result['Details']})"
            )

    write_report(results, output_file)
    print(f"Report saved to {output_file}")
    return results
