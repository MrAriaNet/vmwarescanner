# VMware ESXi Scanner + IXP Ping CLI

**Fast async discovery of VMware ESXi hosts across CIDR ranges, plus automated connectivity checks via the [IXP.ir](https://ixp.ir) ping API — all from one Python CLI.**

Ideal for network operators, infra teams, and lab environments that need to map ESXi management interfaces at scale and verify reachability from an Iranian IXP probe.

---

## Features

### ESXi Subnet Scanner
- Reads CIDR subnets from a text file (`192.168.1.0/24`, `10.0.0.0/16`, …)
- Probes **HTTP (80)** and **HTTPS (443)** with async concurrency (default **200** tasks)
- Fingerprints ESXi via response headers and HTML body (`VMware ESXi`, `vSphere`, welcome page markers, …)
- Skips SSL verification for self-signed ESXi certificates
- Fast timeouts (~2.5s) and live progress with **tqdm**
- Writes discovered IPs to `esxi_hosts.txt` **as they are found**

### IXP API Ping Tester
- Accepts a single IP/domain **or** a file of targets
- POSTs to `https://ixp.ir/api/ping-test` with configurable `probe_node_id`
- Maps `global_status == "up"` → **Connected**, otherwise **Disconnected**
- Live console progress while testing
- Generates a clean timestamped report in `ping_report.txt`

### Unified CLI
- Three modes: `scan`, `ping`, and `both` (scan → ping discovered hosts)

---

## Requirements

- Python **3.10+** (tested on 3.13)
- Network access to target subnets and to `ixp.ir`

---

## Installation

```bash
git clone https://github.com/MrAriaNet/vmwarescanner.git
cd vmwarescanner

python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux / macOS
source .venv/bin/activate

pip install -r requirements.txt
```

---

## Quick Start

### 1. Prepare subnets

Copy the example file and edit it:

```bash
cp subnets.txt.example subnets.txt
```

```text
# subnets.txt — one CIDR per line
192.168.1.0/24
10.10.0.0/24
# 172.16.0.0/16
```

Empty lines and `#` comments are ignored.

### 2. Scan for ESXi hosts

```bash
python main.py scan --subnets subnets.txt
```

Discovered hosts are written to `esxi_hosts.txt` in real time.

### 3. Ping via IXP API

Single target:

```bash
python main.py ping 8.8.8.8
```

From a file:

```bash
python main.py ping esxi_hosts.txt
```

### 4. Scan + ping in one shot

```bash
python main.py both --subnets subnets.txt
```

Runs the scanner first, then pings every IP found in `esxi_hosts.txt`.

---

## CLI Reference

### `scan`

| Flag | Default | Description |
|------|---------|-------------|
| `--subnets` | `subnets.txt` | Input file of CIDR subnets |
| `--output` | `esxi_hosts.txt` | File for discovered ESXi IPs |
| `--concurrency` | `200` | Max concurrent probe tasks |
| `--timeout` | `2.5` | Per-host timeout (seconds) |

```bash
python main.py scan --subnets subnets.txt --concurrency 300 --timeout 3 --output esxi_hosts.txt
```

### `ping`

| Argument / Flag | Default | Description |
|-----------------|---------|-------------|
| `target` | *(required)* | IP/domain **or** path to a targets file |
| `--output` | `ping_report.txt` | Report output path |
| `--probe-node-id` | `5` | IXP probe node ID |

```bash
python main.py ping targets.txt --probe-node-id 5 --output ping_report.txt
```

### `both`

| Flag | Default | Description |
|------|---------|-------------|
| `--subnets` | `subnets.txt` | Subnet list for scanning |
| `--scan-output` | `esxi_hosts.txt` | ESXi discovery output |
| `--ping-output` | `ping_report.txt` | Ping report output |
| `--concurrency` | `200` | Scanner concurrency |
| `--timeout` | `2.5` | Scanner timeout |
| `--probe-node-id` | `5` | IXP probe node ID |

```bash
python main.py both --subnets subnets.txt --concurrency 200 --probe-node-id 5
```

---

## How It Works

```text
┌─────────────────┐     expand CIDRs      ┌──────────────────────┐
│  subnets.txt    │ ───────────────────►  │  Async probe pool    │
└─────────────────┘                       │  HTTP :80 / HTTPS:443│
                                          └──────────┬───────────┘
                                                     │ fingerprint
                                                     ▼
                                          ┌──────────────────────┐
                                          │  esxi_hosts.txt      │
                                          │  (live append)       │
                                          └──────────┬───────────┘
                                                     │ both / ping
                                                     ▼
                                          ┌──────────────────────┐
                                          │  IXP ping-test API   │
                                          │  → ping_report.txt   │
                                          └──────────────────────┘
```

### ESXi detection

Each host is checked on ports **80** and **443**. A match is recorded if headers or body content suggest a VMware ESXi / vSphere management UI (case-insensitive markers such as `VMware ESXi`, `vSphere`, welcome-page strings, and related paths). HTTPS uses certificate verification disabled so self-signed ESXi certs do not block discovery.

### IXP ping

Requests are sent as:

```http
POST https://ixp.ir/api/ping-test
Content-Type: application/json

{
  "target": "<ip_or_domain>",
  "probe_node_id": 5
}
```

The tool reads `data.data.global_status` from the JSON response:
- `"up"` → **Connected**
- anything else / errors → **Disconnected** (with a short details string)

---

## Output Examples

### `esxi_hosts.txt`

```text
192.168.1.10
192.168.1.55
10.10.0.8
```

### `ping_report.txt`

```text
=== Ping Test Report (2026-08-07 22:15:03) ===

Target         Status        Details
-------------  ------------  ----------------------
192.168.1.10   Connected     global_status=up
192.168.1.55   Disconnected  global_status=down
10.10.0.8      Disconnected  Request timed out (10s)
```

---

## Project Structure

```text
vmwarescanner/
├── main.py                 # Argparse CLI entrypoint
├── esxi_scanner.py         # Async ESXi subnet scanner
├── ixp_ping.py             # IXP API ping tester + report
├── requirements.txt        # Python dependencies
├── subnets.txt.example     # Sample CIDR input
└── README.md
```

---

## Dependencies

| Package | Role |
|---------|------|
| `aiohttp` | High-concurrency async HTTP/HTTPS probing |
| `httpx` | Reliable sync client for IXP API calls |
| `netaddr` | CIDR parsing and host expansion |
| `tqdm` | Live scan progress bar |
| `tabulate` | Formatted ping report tables |

---

## Tips

- Start with a small subnet (`/28` or `/29`) to validate detection before scanning large ranges.
- Raise `--concurrency` on fast networks; lower it if you hit rate limits or overload a firewall.
- For `ping`, if the argument is an existing file path it is treated as a list; otherwise it is treated as a single host.
- Output files are truncated at the start of each run so old results are not mixed in.

---

## Legal & Ethical Use

Use this tool **only** on networks and systems you own or are explicitly authorized to test.

Unauthorized scanning of third-party infrastructure may be illegal. The authors assume no liability for misuse. Always follow your organization’s security policies and local laws.

---

## License

Released under the **MIT License**. Add a `LICENSE` file in the repo root before publishing if you want GitHub to detect it automatically.

---

## Contributing

Issues and pull requests are welcome. If you change CLI flags, detection markers, or report formats, please keep `--help` and this README in sync.
