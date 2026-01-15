#!/usr/bin/env python3
"""
Disk Usage Analyzer
Built by Claude on Raspberry Pi 5

Shows what's taking up space on your Pi.
"""

import os
import sys
from pathlib import Path

from rich.console import Console
from rich.tree import Tree
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn


console = Console()


def format_size(size_bytes):
    """Format bytes to human readable"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} PB"


def get_dir_size(path):
    """Get total size of a directory"""
    total = 0
    try:
        for entry in os.scandir(path):
            try:
                if entry.is_file(follow_symlinks=False):
                    total += entry.stat().st_size
                elif entry.is_dir(follow_symlinks=False):
                    total += get_dir_size(entry.path)
            except (PermissionError, OSError):
                pass
    except (PermissionError, OSError):
        pass
    return total


def analyze_directory(path, depth=1, min_size_mb=10):
    """Analyze disk usage of a directory"""
    path = Path(path)

    if not path.exists():
        console.print(f"[red]Path does not exist: {path}[/red]")
        return

    console.print(Panel(
        f"[bold cyan]Disk Usage Analyzer[/bold cyan]\n"
        f"[dim]Analyzing: {path}[/dim]",
        border_style="cyan"
    ))

    min_size = min_size_mb * 1024 * 1024

    # Collect directory sizes
    dirs_with_sizes = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task("Scanning directories...", total=None)

        try:
            for entry in os.scandir(path):
                try:
                    if entry.is_dir(follow_symlinks=False):
                        progress.update(task, description=f"Scanning {entry.name}...")
                        size = get_dir_size(entry.path)
                        dirs_with_sizes.append((entry.name, size, entry.path))
                    elif entry.is_file(follow_symlinks=False):
                        size = entry.stat().st_size
                        if size >= min_size:
                            dirs_with_sizes.append((entry.name, size, entry.path))
                except (PermissionError, OSError):
                    pass
        except PermissionError:
            console.print(f"[red]Permission denied: {path}[/red]")
            return

    # Sort by size descending
    dirs_with_sizes.sort(key=lambda x: x[1], reverse=True)

    # Calculate total
    total_size = sum(d[1] for d in dirs_with_sizes)

    # Build tree
    tree = Tree(f"[bold cyan]{path}[/bold cyan] ({format_size(total_size)})")

    for name, size, full_path in dirs_with_sizes:
        if size < min_size:
            continue

        percent = (size / total_size * 100) if total_size > 0 else 0

        # Color based on size
        if size > 1024 * 1024 * 1024:  # > 1GB
            color = "red"
        elif size > 100 * 1024 * 1024:  # > 100MB
            color = "yellow"
        else:
            color = "green"

        is_dir = os.path.isdir(full_path)
        icon = "/" if is_dir else ""

        tree.add(f"[{color}]{name}{icon}[/{color}] - {format_size(size)} ({percent:.1f}%)")

    console.print()
    console.print(tree)
    console.print()

    # Summary
    console.print(f"[dim]Showing items >= {min_size_mb}MB[/dim]")
    console.print(f"[dim]Total analyzed: {format_size(total_size)}[/dim]")


def main():
    if len(sys.argv) > 1:
        if sys.argv[1] in ['--help', '-h']:
            console.print("""
[yellow]Usage:[/yellow]
  python3 disk_analyzer.py           # Analyze home directory
  python3 disk_analyzer.py /path     # Analyze specific path
  python3 disk_analyzer.py /path 5   # Show items >= 5MB (default: 10MB)

[dim]Shows what's taking up space on your disk[/dim]
""")
            return

        path = sys.argv[1]
        min_size = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    else:
        path = str(Path.home())
        min_size = 10

    analyze_directory(path, min_size_mb=min_size)


if __name__ == '__main__':
    main()
