#!/usr/bin/env python3
"""
Network Scanner - Discover devices on your local network
Built by Claude on Raspberry Pi 5

Uses ARP scanning to find devices on the local network.
"""

import socket
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from ipaddress import IPv4Network


def get_local_network():
    """Get the local network CIDR"""
    try:
        result = subprocess.run(
            ['ip', 'route', 'get', '1'],
            capture_output=True,
            text=True
        )
        # Parse output like: "1.0.0.0 via 192.168.1.1 dev eth0 src 192.168.1.15"
        parts = result.stdout.split()
        local_ip = None
        for i, part in enumerate(parts):
            if part == 'src' and i + 1 < len(parts):
                local_ip = parts[i + 1]
                break

        if local_ip:
            # Assume /24 network
            network = '.'.join(local_ip.split('.')[:-1]) + '.0/24'
            return network, local_ip

    except Exception as e:
        print(f"Error detecting network: {e}")

    return None, None


def ping_host(ip):
    """Ping a single host"""
    try:
        result = subprocess.run(
            ['ping', '-c', '1', '-W', '1', str(ip)],
            capture_output=True,
            timeout=2
        )
        return result.returncode == 0
    except Exception:
        return False


def get_hostname(ip):
    """Try to resolve hostname"""
    try:
        return socket.gethostbyaddr(str(ip))[0]
    except Exception:
        return None


def get_mac_address(ip):
    """Get MAC address from ARP table"""
    try:
        result = subprocess.run(
            ['arp', '-n', str(ip)],
            capture_output=True,
            text=True
        )
        parts = result.stdout.split()
        for i, part in enumerate(parts):
            if ':' in part and len(part) == 17:  # MAC address format
                return part
    except Exception:
        pass
    return None


def scan_network(network, local_ip):
    """Scan the network for active hosts"""
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║                   NETWORK SCANNER                             ║
║               Built by Claude on Pi 5                         ║
╚══════════════════════════════════════════════════════════════╝

Scanning network: {network}
Your IP: {local_ip}
""")

    hosts = list(IPv4Network(network, strict=False).hosts())
    active_hosts = []

    print(f"Scanning {len(hosts)} hosts...")
    print("-" * 60)

    with ThreadPoolExecutor(max_workers=50) as executor:
        future_to_ip = {executor.submit(ping_host, ip): ip for ip in hosts}

        completed = 0
        for future in as_completed(future_to_ip):
            ip = future_to_ip[future]
            completed += 1

            # Progress indicator
            if completed % 25 == 0:
                print(f"  Progress: {completed}/{len(hosts)} hosts checked...")

            if future.result():
                hostname = get_hostname(ip)
                mac = get_mac_address(ip)
                active_hosts.append({
                    'ip': str(ip),
                    'hostname': hostname,
                    'mac': mac,
                    'is_self': str(ip) == local_ip
                })

    print("\n" + "=" * 60)
    print(f"\n  Found {len(active_hosts)} active hosts:\n")
    print(f"  {'IP Address':<16} {'Hostname':<25} {'MAC Address':<18}")
    print(f"  {'-'*16} {'-'*25} {'-'*18}")

    for host in sorted(active_hosts, key=lambda x: [int(p) for p in x['ip'].split('.')]):
        marker = " <-- YOU" if host['is_self'] else ""
        hostname = host['hostname'] or '(unknown)'
        mac = host['mac'] or '(unknown)'
        print(f"  {host['ip']:<16} {hostname:<25} {mac:<18}{marker}")

    print("\n" + "=" * 60)
    return active_hosts


def main():
    network, local_ip = get_local_network()
    if not network:
        print("Could not detect local network!")
        sys.exit(1)

    scan_network(network, local_ip)


if __name__ == '__main__':
    main()
