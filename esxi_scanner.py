"""Fast async ESXi subnet scanner (HTTP/HTTPS fingerprinting)."""

from __future__ import annotations

import asyncio
import ssl
from pathlib import Path
from typing import Iterable

import aiohttp
from netaddr import AddrFormatError, IPNetwork
from tqdm import tqdm

ESXI_MARKERS = (
    "vmware esxi",
    "vsphere",
    "vmware",
    "id_eesx_welcome",
    "/ui",
    "esxi",
    "welcome to esxi",
)


def load_subnets(path: str | Path) -> list[str]:
    """Read CIDR lines from a file, ignoring blanks and # comments."""
    subnets: list[str] = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            subnets.append(line)
    return subnets


def expand_hosts(subnets: Iterable[str]) -> list[str]:
    """Expand CIDR subnets into host IP strings."""
    hosts: list[str] = []
    seen: set[str] = set()
    for cidr in subnets:
        try:
            network = IPNetwork(cidr)
        except (AddrFormatError, ValueError) as exc:
            print(f"[warn] Skipping invalid subnet '{cidr}': {exc}")
            continue
        for ip in network.iter_hosts():
            ip_str = str(ip)
            if ip_str not in seen:
                seen.add(ip_str)
                hosts.append(ip_str)
        # /31 and /32: iter_hosts() may be empty; include usable addresses
        if network.prefixlen >= 31:
            for ip in network:
                ip_str = str(ip)
                if ip_str not in seen:
                    seen.add(ip_str)
                    hosts.append(ip_str)
    return hosts


def _looks_like_esxi(headers: dict, body: str) -> bool:
    parts: list[str] = []
    if headers:
        for key, value in headers.items():
            parts.append(f"{key}: {value}")
    parts.append(body)
    blob = "\n".join(parts).lower()
    return any(marker in blob for marker in ESXI_MARKERS)


async def _probe_url(
    session: aiohttp.ClientSession,
    url: str,
    ssl_ctx: ssl.SSLContext | bool,
) -> bool:
    try:
        async with session.get(url, ssl=ssl_ctx, allow_redirects=True) as resp:
            # Limit body read for speed
            body = await resp.text(errors="ignore")
            body = body[:65536]
            header_map = {k: v for k, v in resp.headers.items()}
            location = resp.headers.get("Location", "")
            if location:
                header_map["Location"] = location
            return _looks_like_esxi(header_map, body)
    except (aiohttp.ClientError, asyncio.TimeoutError, UnicodeDecodeError, OSError):
        return False


async def _check_host(
    session: aiohttp.ClientSession,
    ip: str,
    semaphore: asyncio.Semaphore,
    ssl_ctx: ssl.SSLContext,
) -> bool:
    async with semaphore:
        http_hit = await _probe_url(session, f"http://{ip}/", False)
        if http_hit:
            return True
        return await _probe_url(session, f"https://{ip}/", ssl_ctx)


async def scan_subnets(
    subnets_file: str | Path,
    output_file: str | Path = "esxi_hosts.txt",
    concurrency: int = 200,
    timeout: float = 2.5,
) -> list[str]:
    """
    Scan subnets for ESXi hosts. Writes discovered IPs to output_file in real time.
    Returns the list of discovered IPs.
    """
    subnets = load_subnets(subnets_file)
    if not subnets:
        print(f"[error] No subnets found in {subnets_file}")
        return []

    hosts = expand_hosts(subnets)
    if not hosts:
        print("[error] No host IPs to scan after expanding subnets")
        return []

    print(f"Scanning {len(hosts)} host(s) from {len(subnets)} subnet(s) "
          f"(concurrency={concurrency}, timeout={timeout}s)")

    out_path = Path(output_file)
    out_path.write_text("", encoding="utf-8")

    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE

    client_timeout = aiohttp.ClientTimeout(total=timeout, connect=timeout)
    semaphore = asyncio.Semaphore(concurrency)
    write_lock = asyncio.Lock()
    found: list[str] = []

    connector = aiohttp.TCPConnector(
        limit=concurrency,
        ssl=False,
        force_close=True,
        enable_cleanup_closed=True,
    )

    async with aiohttp.ClientSession(
        timeout=client_timeout,
        connector=connector,
        headers={"User-Agent": "ESXi-Scanner/1.0"},
    ) as session:
        pbar = tqdm(total=len(hosts), desc="Scanning", unit="host")

        async def worker(ip: str) -> None:
            is_esxi = await _check_host(session, ip, semaphore, ssl_ctx)
            if is_esxi:
                async with write_lock:
                    found.append(ip)
                    with open(out_path, "a", encoding="utf-8") as fh:
                        fh.write(ip + "\n")
                        fh.flush()
                tqdm.write(f"[found] {ip}")
            pbar.update(1)

        await asyncio.gather(*(worker(ip) for ip in hosts))
        pbar.close()

    print(f"Done. Found {len(found)} ESXi host(s). Saved to {out_path}")
    return found


def run_scan(
    subnets_file: str | Path,
    output_file: str | Path = "esxi_hosts.txt",
    concurrency: int = 200,
    timeout: float = 2.5,
) -> list[str]:
    """Synchronous entry point for the ESXi scanner."""
    return asyncio.run(
        scan_subnets(
            subnets_file=subnets_file,
            output_file=output_file,
            concurrency=concurrency,
            timeout=timeout,
        )
    )
