"""
network_scanner.py
Discovers devices on the local network using a ping sweep + ARP table read,
then categorises each by MAC vendor into: Phone, Laptop/PC, or Other.

Works on Windows, Ubuntu, and Raspberry Pi OS without admin rights.
Vendor lookup uses the 'manuf' library (IEEE OUI database).
"""

import re
import sys
import socket
import logging
import subprocess
import ipaddress
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Dict, List, Optional

IS_WINDOWS = sys.platform == "win32"

# Suppress CMD window pop-ups on Windows --windowed builds
_NO_WINDOW = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0

logger = logging.getLogger(__name__)

# ── Vendor keyword → category ─────────────────────────────────────────────────
# Match against the lowercase vendor string returned by manuf / OUI lookup
PHONE_KEYWORDS = [
    "apple",        # iPhone, iPad (and some Macs — acceptable for home nets)
    "samsung",      # Galaxy phones / tablets
    "xiaomi",       # Xiaomi / Redmi / POCO
    "huawei",       # Huawei phones
    "oppo",         # OPPO / OnePlus / Realme share parent company
    "vivo",
    "oneplus",
    "realme",
    "motorola",
    "nokia",
    "lg electronics",
    "sony mobile",
    "zte",
    "tcl communication",
    "honor",
    "meizu",
    "nothing technology",
    "wiko",
    "transsion",    # Tecno, Infinix, itel
    "infinix",
    "tecno",
]

PC_KEYWORDS = [
    "intel",        # Intel WiFi/LAN chips — almost always in laptops/desktops
    "realtek",      # Realtek NICs — common in desktops & laptops
    "dell",
    "hewlett",      # HP
    "hp enterprise",
    "lenovo",
    "asustek",      # ASUS
    "asus",
    "acer",
    "microsoft",    # Surface devices
    "msi",
    "gigabyte",
    "asrock",
    "razer",
    "toshiba",
    "fujitsu",
    "panasonic",
    "qualcomm atheros",  # WiFi chips common in laptops
    "broadcom",          # WiFi chips common in laptops/PCs
    "apple",             # Also catches MacBooks — we'll leave Apple as Phone priority
]

# Override: if ANY of these exact strings appear in the vendor, force Laptop/PC
# (handles Apple MacBooks which share OUI space with iPhones)
PC_OVERRIDE_KEYWORDS = [
    "intel",
    "realtek",
    "dell",
    "hewlett",
    "lenovo",
    "asustek",
    "acer",
    "microsoft",
    "msi",
    "gigabyte",
    "asrock",
    "razer",
    "toshiba",
    "broadcom",
    "qualcomm atheros",
]


def _categorize(vendor: str) -> str:
    """Map a vendor name string to a simple device category."""
    if not vendor:
        return "Other"
    v = vendor.lower()

    # PC-specific chips/brands take priority (avoids Apple ambiguity for Macs)
    for kw in PC_OVERRIDE_KEYWORDS:
        if kw in v:
            return "Laptop/PC"

    for kw in PHONE_KEYWORDS:
        if kw in v:
            return "Phone"

    return "Other"


def _lookup_vendor(mac: str) -> str:
    """
    Look up the manufacturer name for a MAC address.
    Tries manuf library first; falls back to a short hard-coded OUI table.
    """
    try:
        from manuf import manuf as manuf_lib
        parser = manuf_lib.MacParser(update=False)
        result = parser.get_manuf(mac)
        return result or ""
    except Exception:
        pass

    # ── Minimal fallback OUI table (first 3 bytes, uppercase no-colon) ─────
    FALLBACK_OUI: Dict[str, str] = {
        # Apple
        "000A95": "Apple", "000D93": "Apple", "001124": "Apple",
        "001451": "Apple", "40B395": "Apple", "70CD60": "Apple",
        "A4C361": "Apple", "D8BB2C": "Apple", "3C0754": "Apple",
        # Samsung
        "001599": "Samsung", "B4EF39": "Samsung", "F49F54": "Samsung",
        "8C71F8": "Samsung", "CC07AB": "Samsung", "C0BD61": "Samsung",
        # Xiaomi
        "0CF105": "Xiaomi", "34CE00": "Xiaomi", "78DA07": "Xiaomi",
        "60AB14": "Xiaomi", "9C99A0": "Xiaomi",
        # Huawei
        "001E10": "Huawei", "307B0C": "Huawei", "001877": "Huawei",
        # OPPO
        "0439AB": "OPPO", "14B169": "OPPO", "546C0E": "OPPO",
        # Vivo
        "086987": "Vivo", "507DBA": "Vivo", "CC9695": "Vivo",
        # Motorola
        "001A76": "Motorola", "9CD917": "Motorola",
        # Nokia
        "001377": "Nokia", "782A68": "Nokia",
        # Intel
        "001B21": "Intel", "002241": "Intel", "0C5485": "Intel",
        "18D9E4": "Intel", "347246": "Intel", "5CF370": "Intel",
        "647A1E": "Intel", "803013": "Intel", "88B111": "Intel",
        "9C4E36": "Intel", "A45E60": "Intel", "B4B680": "Intel",
        "D054E0": "Intel", "E0AEB9": "Intel", "F46D04": "Intel",
        # Realtek
        "001832": "Realtek", "00E04C": "Realtek", "44E43D": "Realtek",
        # Dell
        "001143": "Dell", "0014FF": "Dell", "18A994": "Dell",
        "34179F": "Dell", "747D24": "Dell", "B82A72": "Dell",
        # HP
        "000D9D": "HP", "001060": "HP", "10604B": "HP",
        "3C4AF8": "HP", "706D6B": "HP",
        # Lenovo
        "001EF7": "Lenovo", "485293": "Lenovo", "600F5A": "Lenovo",
        "70720D": "Lenovo", "8CB00B": "Lenovo", "A02BB8": "Lenovo",
        # ASUS
        "001A92": "ASUSTeK", "107B44": "ASUSTeK", "30B4B8": "ASUSTeK",
        "5CE8EB": "ASUSTeK", "A0F3C1": "ASUSTeK", "BC4EA3": "ASUSTeK",
        # Acer
        "00156D": "Acer", "001E6B": "Acer",
        # Microsoft
        "3C8348": "Microsoft", "985FD3": "Microsoft", "DC530E": "Microsoft",
        # TP-Link
        "D04457": "TP-Link", "30B49E": "TP-Link", "54C80F": "TP-Link",
        # Cisco
        "000C85": "Cisco", "000F66": "Cisco",
        # Amazon
        "FC65DE": "Amazon", "74C246": "Amazon",
        # Raspberry Pi
        "B827EB": "Raspberry Pi Foundation", "DC1680": "Raspberry Pi Foundation",
        # Espressif (IoT)
        "18FE34": "Espressif", "2CF432": "Espressif", "5CCF7F": "Espressif",
        "AC67B2": "Espressif", "B4E62D": "Espressif",
    }

    oui = mac.upper().replace(":", "").replace("-", "")[:6]
    return FALLBACK_OUI.get(oui, "")


@dataclass
class DeviceScan:
    """Result of a network scan."""
    total: int = 0
    phones: int = 0
    laptops: int = 0
    other: int = 0
    devices: List[Dict] = field(default_factory=list)


def _get_local_subnet() -> Optional[str]:
    """Return the /24 subnet of the machine's primary outbound interface."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        net = ipaddress.IPv4Network(f"{local_ip}/24", strict=False)
        return str(net)
    except Exception as e:
        logger.warning(f"Could not determine local subnet: {e}")
        return None



def _ping(ip: str):
    """Send a single ICMP ping silently (populates the ARP / neighbour cache)."""
    if IS_WINDOWS:
        cmd = ["ping", "-n", "1", "-w", "300", ip]
        kwargs = dict(stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                      creationflags=_NO_WINDOW)
    else:
        # -c 1 = one packet, -W 1 = 1 second timeout
        cmd = ["ping", "-c", "1", "-W", "1", ip]
        kwargs = dict(stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(cmd, **kwargs)


def _ping_sweep(subnet: str, max_workers: int = 100):
    """Ping all hosts in the subnet in parallel to populate the ARP cache."""
    hosts = [str(h) for h in ipaddress.IPv4Network(subnet).hosts()]
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        pool.map(_ping, hosts)


def _read_arp_table() -> List[Dict[str, str]]:
    """
    Read the ARP / neighbour table and return {ip, mac} dicts for active entries.
    Handles both Windows ('arp -a' with 'dynamic') and
    Linux ('ip neigh' with REACHABLE / STALE / DELAY / PROBE states).
    """
    entries = []
    seen_ips: set = set()

    # Regex that matches a standard MAC in either aa:bb:cc or aa-bb-cc notation
    MAC_RE = r"[0-9a-f]{2}(?:[:\-][0-9a-f]{2}){5}"

    if IS_WINDOWS:
        # Windows: "  192.168.1.1    aa-bb-cc-dd-ee-ff    dynamic"
        result = subprocess.run(
            ["arp", "-a"], capture_output=True, text=True,
            creationflags=_NO_WINDOW
        )
        pattern = re.compile(
            r"(\d{1,3}(?:\.\d{1,3}){3})\s+(" + MAC_RE + r")\s+dynamic",
            re.IGNORECASE
        )
        for line in result.stdout.splitlines():
            m = pattern.search(line)
            if not m:
                continue
            ip = m.group(1)
            mac = m.group(2).upper().replace("-", ":")
            if ip.endswith(".255") or mac == "FF:FF:FF:FF:FF:FF":
                continue
            if ip not in seen_ips:
                seen_ips.add(ip)
                entries.append({"ip": ip, "mac": mac})
    else:
        # Linux: "192.168.1.5 dev wlan0 lladdr aa:bb:cc:dd:ee:ff REACHABLE"
        result = subprocess.run(
            ["ip", "neigh"], capture_output=True, text=True
        )
        # Valid states: REACHABLE, STALE, DELAY, PROBE (exclude FAILED/INCOMPLETE)
        active_states = {"REACHABLE", "STALE", "DELAY", "PROBE"}
        pattern = re.compile(
            r"(\d{1,3}(?:\.\d{1,3}){3}).*?(" + MAC_RE + r")\s+(\S+)\s*$",
            re.IGNORECASE
        )
        for line in result.stdout.splitlines():
            m = pattern.search(line)
            if not m:
                continue
            ip = m.group(1)
            mac = m.group(2).upper()
            state = m.group(3).upper()
            if state not in active_states:
                continue
            if ip.endswith(".255") or mac == "FF:FF:FF:FF:FF:FF":
                continue
            if ip not in seen_ips:
                seen_ips.add(ip)
                entries.append({"ip": ip, "mac": mac})

    return entries


def scan_network(do_ping_sweep: bool = True) -> DeviceScan:
    """
    Scan the local /24 subnet and categorise connected devices.

    Args:
        do_ping_sweep: If True, ping all hosts first to populate the ARP cache
                       (~3-5 seconds). If False, only reads the existing cache
                       (faster but may miss idle devices).

    Returns:
        DeviceScan with counts per category and a list of device dicts.
    """
    result = DeviceScan()

    subnet = _get_local_subnet()
    if not subnet:
        logger.warning("Network scan skipped — could not determine subnet.")
        return result

    logger.info(f"Scanning subnet {subnet}...")

    if do_ping_sweep:
        logger.info("Ping sweep in progress...")
        try:
            _ping_sweep(subnet)
        except Exception as e:
            logger.warning(f"Ping sweep error (non-fatal): {e}")

    devices = _read_arp_table()
    logger.info(f"ARP table: {len(devices)} device(s) found.")

    for dev in devices:
        vendor = _lookup_vendor(dev["mac"])
        category = _categorize(vendor)
        dev["vendor"] = vendor or "Unknown"
        dev["category"] = category

        result.total += 1
        if category == "Phone":
            result.phones += 1
        elif category == "Laptop/PC":
            result.laptops += 1
        else:
            result.other += 1

        result.devices.append(dev)
        logger.debug(f"  {dev['ip']:16s} {dev['mac']}  {vendor or 'Unknown':30s} → {category}")

    logger.info(
        f"Scan complete: {result.total} device(s) — "
        f"{result.phones} Phone(s), {result.laptops} Laptop/PC(s), {result.other} Other"
    )
    return result
