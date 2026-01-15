#!/usr/bin/env python3
"""
Internet Speed Test
Built by Claude on Raspberry Pi 5

A simple speed test using common test servers.
"""

import time
import urllib.request
import socket
from concurrent.futures import ThreadPoolExecutor
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.panel import Panel


def test_download_speed(url, size_mb):
    """Test download speed from a URL"""
    try:
        start = time.time()
        response = urllib.request.urlopen(url, timeout=30)
        data = response.read()
        elapsed = time.time() - start
        speed_mbps = (len(data) * 8) / (elapsed * 1_000_000)
        return speed_mbps, len(data), elapsed
    except Exception as e:
        return None, 0, 0


def test_latency(host, port=80):
    """Test latency to a host"""
    try:
        start = time.time()
        sock = socket.create_connection((host, port), timeout=5)
        latency = (time.time() - start) * 1000
        sock.close()
        return latency
    except Exception:
        return None


def main():
    console = Console()

    console.print(Panel(
        "[bold cyan]Internet Speed Test[/bold cyan]\n"
        "[dim]Built by Claude on Raspberry Pi 5[/dim]",
        border_style="cyan"
    ))
    console.print()

    # Test servers
    test_urls = [
        ("Cloudflare", "https://speed.cloudflare.com/__down?bytes=10000000"),
        ("Google", "https://www.google.com/images/branding/googlelogo/2x/googlelogo_color_272x92dp.png"),
    ]

    latency_hosts = [
        ("Google DNS", "8.8.8.8"),
        ("Cloudflare DNS", "1.1.1.1"),
        ("Local Gateway", "192.168.1.1"),
    ]

    # Test latency
    console.print("[bold yellow]Testing Latency...[/bold yellow]")

    for name, host in latency_hosts:
        latency = test_latency(host)
        if latency:
            color = "green" if latency < 50 else "yellow" if latency < 100 else "red"
            console.print(f"  {name}: [{color}]{latency:.1f} ms[/{color}]")
        else:
            console.print(f"  {name}: [red]Failed[/red]")

    console.print()

    # Test download
    console.print("[bold yellow]Testing Download Speed...[/bold yellow]")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        console=console
    ) as progress:

        speeds = []
        for name, url in test_urls:
            task = progress.add_task(f"Testing {name}...", total=100)
            progress.update(task, advance=50)

            speed, size, elapsed = test_download_speed(url, 10)

            progress.update(task, advance=50)

            if speed:
                speeds.append(speed)
                console.print(f"  {name}: [green]{speed:.2f} Mbps[/green] ({size/1024/1024:.1f} MB in {elapsed:.1f}s)")
            else:
                console.print(f"  {name}: [red]Failed[/red]")

    console.print()

    if speeds:
        avg_speed = sum(speeds) / len(speeds)
        console.print(Panel(
            f"[bold green]Average Download Speed: {avg_speed:.2f} Mbps[/bold green]",
            border_style="green"
        ))
    else:
        console.print("[red]Could not complete speed test[/red]")


if __name__ == '__main__':
    main()
