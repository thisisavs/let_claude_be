#!/usr/bin/env python3
"""
Beautiful System Info Display
Built by Claude on Raspberry Pi 5

Uses the Rich library for beautiful terminal output.
"""

import platform
import subprocess
from datetime import datetime

import psutil
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.layout import Layout
from rich import box


def get_pi_model():
    """Get Raspberry Pi model info"""
    try:
        with open('/proc/device-tree/model', 'r') as f:
            return f.read().strip().rstrip('\x00')
    except Exception:
        return "Unknown Model"


def get_cpu_temp():
    """Get CPU temperature"""
    try:
        result = subprocess.run(
            ['vcgencmd', 'measure_temp'],
            capture_output=True,
            text=True
        )
        return result.stdout.strip().split('=')[1]
    except Exception:
        return "N/A"


def format_bytes(bytes_val):
    """Format bytes to human readable"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_val < 1024:
            return f"{bytes_val:.1f} {unit}"
        bytes_val /= 1024
    return f"{bytes_val:.1f} PB"


def get_uptime():
    """Get system uptime"""
    boot = datetime.fromtimestamp(psutil.boot_time())
    uptime = datetime.now() - boot
    days = uptime.days
    hours, remainder = divmod(uptime.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{days}d {hours}h {minutes}m {seconds}s"


def main():
    console = Console()

    # Header
    header_text = """
    ╦═╗╔═╗╔═╗╔═╗╔╗ ╔═╗╦═╗╦═╗╦ ╦  ╔═╗╦
    ╠╦╝╠═╣╚═╗╠═╝╠╩╗║╣ ╠╦╝╠╦╝╚╦╝  ╠═╝║
    ╩╚═╩ ╩╚═╝╩  ╚═╝╚═╝╩╚═╩╚═ ╩   ╩  ╩
    """

    console.print(Panel(
        Text(header_text, style="bold cyan", justify="center"),
        title="[bold green]System Information[/bold green]",
        subtitle="[dim]Built by Claude[/dim]",
        border_style="green"
    ))

    # System Info Table
    sys_table = Table(title="System", box=box.ROUNDED, border_style="cyan")
    sys_table.add_column("Property", style="cyan")
    sys_table.add_column("Value", style="green")

    sys_table.add_row("Model", get_pi_model())
    sys_table.add_row("Hostname", platform.node())
    sys_table.add_row("Kernel", platform.release())
    sys_table.add_row("Architecture", platform.machine())
    sys_table.add_row("Python", platform.python_version())
    sys_table.add_row("Uptime", get_uptime())

    # CPU Table
    cpu_table = Table(title="CPU", box=box.ROUNDED, border_style="yellow")
    cpu_table.add_column("Property", style="yellow")
    cpu_table.add_column("Value", style="green")

    cpu_freq = psutil.cpu_freq()
    cpu_table.add_row("Cores", str(psutil.cpu_count()))
    cpu_table.add_row("Frequency", f"{cpu_freq.current:.0f} MHz" if cpu_freq else "N/A")
    cpu_table.add_row("Usage", f"{psutil.cpu_percent():.1f}%")
    cpu_table.add_row("Temperature", get_cpu_temp())

    load = psutil.getloadavg()
    cpu_table.add_row("Load (1/5/15m)", f"{load[0]:.2f} / {load[1]:.2f} / {load[2]:.2f}")

    # Memory Table
    mem_table = Table(title="Memory", box=box.ROUNDED, border_style="magenta")
    mem_table.add_column("Property", style="magenta")
    mem_table.add_column("Value", style="green")

    mem = psutil.virtual_memory()
    swap = psutil.swap_memory()

    mem_table.add_row("Total RAM", format_bytes(mem.total))
    mem_table.add_row("Used RAM", f"{format_bytes(mem.used)} ({mem.percent:.1f}%)")
    mem_table.add_row("Available", format_bytes(mem.available))
    mem_table.add_row("Swap Used", f"{format_bytes(swap.used)} ({swap.percent:.1f}%)")

    # Disk Table
    disk_table = Table(title="Storage", box=box.ROUNDED, border_style="blue")
    disk_table.add_column("Property", style="blue")
    disk_table.add_column("Value", style="green")

    disk = psutil.disk_usage('/')
    disk_table.add_row("Total", format_bytes(disk.total))
    disk_table.add_row("Used", f"{format_bytes(disk.used)} ({disk.percent:.1f}%)")
    disk_table.add_row("Free", format_bytes(disk.free))

    # Network Table
    net_table = Table(title="Network", box=box.ROUNDED, border_style="red")
    net_table.add_column("Interface", style="red")
    net_table.add_column("IP Address", style="green")

    for iface, addrs in psutil.net_if_addrs().items():
        for addr in addrs:
            if addr.family.name == 'AF_INET' and addr.address != '127.0.0.1':
                net_table.add_row(iface, addr.address)

    # Print all tables
    console.print()
    console.print(sys_table)
    console.print()
    console.print(cpu_table)
    console.print()
    console.print(mem_table)
    console.print()
    console.print(disk_table)
    console.print()
    console.print(net_table)
    console.print()

    # Footer
    console.print(Panel(
        "[dim]Run [cyan]python3 pi_dashboard.py[/cyan] for the web dashboard\n"
        "Run [cyan]python3 network_scanner.py[/cyan] to discover network devices[/dim]",
        title="[green]More Tools[/green]",
        border_style="dim"
    ))


if __name__ == '__main__':
    main()
