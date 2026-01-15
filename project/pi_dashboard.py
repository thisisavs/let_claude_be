#!/usr/bin/env python3
"""
Raspberry Pi System Monitor Dashboard
Built by Claude on a Raspberry Pi 5

A real-time web dashboard for monitoring your Pi's health.
"""

import json
import subprocess
import time
from collections import deque
from datetime import datetime
from threading import Lock

import psutil
from flask import Flask, jsonify, render_template_string

app = Flask(__name__)

# History storage (last 60 readings, ~1 per second)
MAX_HISTORY = 60
history_lock = Lock()
cpu_history = deque(maxlen=MAX_HISTORY)
memory_history = deque(maxlen=MAX_HISTORY)
temp_history = deque(maxlen=MAX_HISTORY)
network_history = deque(maxlen=MAX_HISTORY)

# Track network bytes for rate calculation
last_net_io = None
last_net_time = None


def get_cpu_temp():
    """Get CPU temperature using vcgencmd"""
    try:
        result = subprocess.run(
            ['vcgencmd', 'measure_temp'],
            capture_output=True,
            text=True,
            timeout=2
        )
        temp_str = result.stdout.strip()
        # Parse "temp=54.9'C"
        temp = float(temp_str.split('=')[1].split("'")[0])
        return temp
    except Exception:
        return None


def get_throttle_status():
    """Get throttling status from vcgencmd"""
    try:
        result = subprocess.run(
            ['vcgencmd', 'get_throttled'],
            capture_output=True,
            text=True,
            timeout=2
        )
        # Returns "throttled=0x0" format
        hex_val = result.stdout.strip().split('=')[1]
        val = int(hex_val, 16)

        status = {
            'under_voltage': bool(val & 0x1),
            'arm_freq_capped': bool(val & 0x2),
            'currently_throttled': bool(val & 0x4),
            'soft_temp_limit': bool(val & 0x8),
            'under_voltage_occurred': bool(val & 0x10000),
            'arm_freq_capped_occurred': bool(val & 0x20000),
            'throttled_occurred': bool(val & 0x40000),
            'soft_temp_limit_occurred': bool(val & 0x80000),
        }
        return status
    except Exception:
        return None


def get_network_speed():
    """Calculate network speed in bytes/sec"""
    global last_net_io, last_net_time

    current = psutil.net_io_counters()
    current_time = time.time()

    if last_net_io is None:
        last_net_io = current
        last_net_time = current_time
        return {'rx_speed': 0, 'tx_speed': 0}

    time_delta = current_time - last_net_time
    if time_delta > 0:
        rx_speed = (current.bytes_recv - last_net_io.bytes_recv) / time_delta
        tx_speed = (current.bytes_sent - last_net_io.bytes_sent) / time_delta
    else:
        rx_speed = tx_speed = 0

    last_net_io = current
    last_net_time = current_time

    return {'rx_speed': rx_speed, 'tx_speed': tx_speed}


def format_bytes(bytes_val):
    """Format bytes to human readable string"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_val < 1024:
            return f"{bytes_val:.1f} {unit}"
        bytes_val /= 1024
    return f"{bytes_val:.1f} PB"


def get_system_stats():
    """Gather all system statistics"""
    # CPU
    cpu_percent = psutil.cpu_percent(interval=0.1)
    cpu_freq = psutil.cpu_freq()
    cpu_count = psutil.cpu_count()
    per_cpu = psutil.cpu_percent(interval=0.1, percpu=True)

    # Memory
    mem = psutil.virtual_memory()
    swap = psutil.swap_memory()

    # Disk
    disk = psutil.disk_usage('/')

    # Network
    net_io = psutil.net_io_counters()
    net_speed = get_network_speed()

    # Network interfaces
    net_if = {}
    for iface, addrs in psutil.net_if_addrs().items():
        for addr in addrs:
            if addr.family.name == 'AF_INET':
                net_if[iface] = addr.address

    # Temperature
    temp = get_cpu_temp()

    # Throttle status
    throttle = get_throttle_status()

    # Uptime
    boot_time = datetime.fromtimestamp(psutil.boot_time())
    uptime = datetime.now() - boot_time
    uptime_str = str(uptime).split('.')[0]  # Remove microseconds

    # Load average
    load_avg = psutil.getloadavg()

    # Top processes
    processes = []
    for proc in sorted(psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']),
                       key=lambda x: x.info['cpu_percent'] or 0, reverse=True)[:10]:
        try:
            processes.append({
                'pid': proc.info['pid'],
                'name': proc.info['name'][:30],
                'cpu': proc.info['cpu_percent'] or 0,
                'mem': proc.info['memory_percent'] or 0
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    stats = {
        'timestamp': datetime.now().isoformat(),
        'cpu': {
            'percent': cpu_percent,
            'per_cpu': per_cpu,
            'frequency': cpu_freq.current if cpu_freq else 0,
            'count': cpu_count,
        },
        'memory': {
            'total': mem.total,
            'used': mem.used,
            'available': mem.available,
            'percent': mem.percent,
            'total_human': format_bytes(mem.total),
            'used_human': format_bytes(mem.used),
        },
        'swap': {
            'total': swap.total,
            'used': swap.used,
            'percent': swap.percent,
        },
        'disk': {
            'total': disk.total,
            'used': disk.used,
            'free': disk.free,
            'percent': disk.percent,
            'total_human': format_bytes(disk.total),
            'used_human': format_bytes(disk.used),
            'free_human': format_bytes(disk.free),
        },
        'network': {
            'bytes_sent': net_io.bytes_sent,
            'bytes_recv': net_io.bytes_recv,
            'bytes_sent_human': format_bytes(net_io.bytes_sent),
            'bytes_recv_human': format_bytes(net_io.bytes_recv),
            'rx_speed': net_speed['rx_speed'],
            'tx_speed': net_speed['tx_speed'],
            'rx_speed_human': format_bytes(net_speed['rx_speed']) + '/s',
            'tx_speed_human': format_bytes(net_speed['tx_speed']) + '/s',
            'interfaces': net_if,
        },
        'temperature': temp,
        'throttle': throttle,
        'uptime': uptime_str,
        'load_avg': load_avg,
        'processes': processes,
    }

    # Update history
    with history_lock:
        cpu_history.append({'time': stats['timestamp'], 'value': cpu_percent})
        memory_history.append({'time': stats['timestamp'], 'value': mem.percent})
        if temp:
            temp_history.append({'time': stats['timestamp'], 'value': temp})
        network_history.append({
            'time': stats['timestamp'],
            'rx': net_speed['rx_speed'],
            'tx': net_speed['tx_speed']
        })

    return stats


# HTML Template - Terminal/Hacker aesthetic
DASHBOARD_HTML = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Pi Monitor - Claude's Dashboard</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        :root {
            --bg-primary: #0a0a0a;
            --bg-secondary: #111111;
            --bg-card: #1a1a1a;
            --text-primary: #00ff88;
            --text-secondary: #00cc6a;
            --text-dim: #666666;
            --accent: #00ffcc;
            --warning: #ffcc00;
            --danger: #ff4444;
            --border: #333333;
        }

        body {
            background: var(--bg-primary);
            color: var(--text-primary);
            font-family: 'Courier New', 'Fira Code', monospace;
            min-height: 100vh;
            padding: 20px;
        }

        .header {
            text-align: center;
            margin-bottom: 30px;
            padding: 20px;
            border: 1px solid var(--border);
            background: var(--bg-secondary);
        }

        .header h1 {
            font-size: 2em;
            color: var(--accent);
            text-shadow: 0 0 10px var(--accent);
            margin-bottom: 10px;
        }

        .header .subtitle {
            color: var(--text-dim);
            font-size: 0.9em;
        }

        .ascii-art {
            color: var(--text-secondary);
            font-size: 0.6em;
            line-height: 1.2;
            margin-bottom: 15px;
        }

        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }

        .card {
            background: var(--bg-card);
            border: 1px solid var(--border);
            padding: 20px;
            position: relative;
        }

        .card::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 2px;
            background: linear-gradient(90deg, var(--text-primary), transparent);
        }

        .card-title {
            color: var(--accent);
            font-size: 1.1em;
            margin-bottom: 15px;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .card-title::before {
            content: '>';
            color: var(--text-primary);
        }

        .stat-row {
            display: flex;
            justify-content: space-between;
            padding: 8px 0;
            border-bottom: 1px solid var(--border);
        }

        .stat-row:last-child {
            border-bottom: none;
        }

        .stat-label {
            color: var(--text-dim);
        }

        .stat-value {
            color: var(--text-primary);
            font-weight: bold;
        }

        .progress-bar {
            width: 100%;
            height: 20px;
            background: var(--bg-secondary);
            border: 1px solid var(--border);
            margin: 10px 0;
            position: relative;
            overflow: hidden;
        }

        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, var(--text-primary), var(--accent));
            transition: width 0.3s ease;
        }

        .progress-fill.warning {
            background: linear-gradient(90deg, var(--warning), #ff9900);
        }

        .progress-fill.danger {
            background: linear-gradient(90deg, var(--danger), #ff0000);
        }

        .progress-text {
            position: absolute;
            right: 10px;
            top: 50%;
            transform: translateY(-50%);
            color: var(--bg-primary);
            font-weight: bold;
            text-shadow: 1px 1px 0 var(--text-primary);
        }

        .cpu-cores {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 5px;
            margin-top: 10px;
        }

        .cpu-core {
            background: var(--bg-secondary);
            padding: 5px;
            text-align: center;
            border: 1px solid var(--border);
            font-size: 0.8em;
        }

        .temp-display {
            font-size: 2.5em;
            text-align: center;
            padding: 20px;
            color: var(--text-primary);
            text-shadow: 0 0 20px var(--text-primary);
        }

        .temp-display.hot {
            color: var(--warning);
            text-shadow: 0 0 20px var(--warning);
        }

        .temp-display.critical {
            color: var(--danger);
            text-shadow: 0 0 20px var(--danger);
            animation: pulse 1s infinite;
        }

        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }

        .process-list {
            font-size: 0.85em;
        }

        .process-row {
            display: grid;
            grid-template-columns: 60px 1fr 60px 60px;
            padding: 5px 0;
            border-bottom: 1px solid var(--border);
        }

        .process-header {
            color: var(--accent);
            font-weight: bold;
        }

        .throttle-status {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
        }

        .throttle-item {
            padding: 10px;
            background: var(--bg-secondary);
            border: 1px solid var(--border);
            text-align: center;
            font-size: 0.85em;
        }

        .throttle-item.active {
            border-color: var(--danger);
            color: var(--danger);
        }

        .throttle-item.ok {
            border-color: var(--text-primary);
            color: var(--text-primary);
        }

        .network-speeds {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            text-align: center;
            margin: 15px 0;
        }

        .speed-box {
            padding: 15px;
            background: var(--bg-secondary);
            border: 1px solid var(--border);
        }

        .speed-label {
            color: var(--text-dim);
            font-size: 0.9em;
        }

        .speed-value {
            font-size: 1.3em;
            color: var(--accent);
            margin-top: 5px;
        }

        canvas {
            width: 100%;
            height: 100px;
            background: var(--bg-secondary);
            border: 1px solid var(--border);
            margin-top: 10px;
        }

        .footer {
            text-align: center;
            padding: 20px;
            color: var(--text-dim);
            border-top: 1px solid var(--border);
            margin-top: 20px;
        }

        .blink {
            animation: blink 1s infinite;
        }

        @keyframes blink {
            0%, 50% { opacity: 1; }
            51%, 100% { opacity: 0; }
        }

        .interfaces {
            margin-top: 10px;
            font-size: 0.85em;
        }

        .interface-row {
            display: flex;
            justify-content: space-between;
            padding: 3px 0;
        }

        .uptime-display {
            font-size: 1.5em;
            text-align: center;
            padding: 15px;
            color: var(--accent);
        }

        .load-avg {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 10px;
            margin-top: 15px;
        }

        .load-item {
            text-align: center;
            padding: 10px;
            background: var(--bg-secondary);
            border: 1px solid var(--border);
        }

        .load-label {
            color: var(--text-dim);
            font-size: 0.8em;
        }

        .load-value {
            font-size: 1.2em;
            margin-top: 5px;
        }
    </style>
</head>
<body>
    <div class="header">
        <pre class="ascii-art">
    ____  ___   _____ ____  ____  __________  ______  __   ____  ____
   / __ \\/   | / ___// __ )/ __ )/ ____/ __ \\/ __ \\ \\/ /  / __ \\/  _/
  / /_/ / /| | \\__ \\/ __  / __  / __/ / /_/ / /_/ /\\  /  / /_/ // /
 / _, _/ ___ |___/ / /_/ / /_/ / /___/ _, _/ _, _/ / /  / ____// /
/_/ |_/_/  |_/____/_____/_____/_____/_/ |_/_/ |_| /_/  /_/   /___/
        </pre>
        <h1>[ SYSTEM MONITOR ]</h1>
        <div class="subtitle">
            Claude's Raspberry Pi 5 Dashboard |
            <span id="current-time"></span>
            <span class="blink">_</span>
        </div>
    </div>

    <div class="grid">
        <!-- CPU Card -->
        <div class="card">
            <div class="card-title">CPU</div>
            <div class="stat-row">
                <span class="stat-label">Usage</span>
                <span class="stat-value" id="cpu-percent">---%</span>
            </div>
            <div class="progress-bar">
                <div class="progress-fill" id="cpu-bar" style="width: 0%"></div>
                <span class="progress-text" id="cpu-bar-text">0%</span>
            </div>
            <div class="stat-row">
                <span class="stat-label">Frequency</span>
                <span class="stat-value" id="cpu-freq">--- MHz</span>
            </div>
            <div class="stat-row">
                <span class="stat-label">Cores</span>
                <span class="stat-value" id="cpu-count">--</span>
            </div>
            <div class="cpu-cores" id="cpu-cores"></div>
            <canvas id="cpu-chart"></canvas>
        </div>

        <!-- Memory Card -->
        <div class="card">
            <div class="card-title">MEMORY</div>
            <div class="stat-row">
                <span class="stat-label">Used / Total</span>
                <span class="stat-value" id="mem-used">-- / --</span>
            </div>
            <div class="progress-bar">
                <div class="progress-fill" id="mem-bar" style="width: 0%"></div>
                <span class="progress-text" id="mem-bar-text">0%</span>
            </div>
            <div class="stat-row">
                <span class="stat-label">Available</span>
                <span class="stat-value" id="mem-available">--</span>
            </div>
            <div class="stat-row">
                <span class="stat-label">Swap Used</span>
                <span class="stat-value" id="swap-percent">---%</span>
            </div>
            <canvas id="mem-chart"></canvas>
        </div>

        <!-- Temperature Card -->
        <div class="card">
            <div class="card-title">TEMPERATURE</div>
            <div class="temp-display" id="temp-display">--°C</div>
            <div class="throttle-status" id="throttle-status">
                <div class="throttle-item" id="throttle-voltage">Under Voltage: --</div>
                <div class="throttle-item" id="throttle-freq">Freq Capped: --</div>
                <div class="throttle-item" id="throttle-throttled">Throttled: --</div>
                <div class="throttle-item" id="throttle-temp">Temp Limit: --</div>
            </div>
            <canvas id="temp-chart"></canvas>
        </div>

        <!-- Disk Card -->
        <div class="card">
            <div class="card-title">STORAGE</div>
            <div class="stat-row">
                <span class="stat-label">Used / Total</span>
                <span class="stat-value" id="disk-used">-- / --</span>
            </div>
            <div class="progress-bar">
                <div class="progress-fill" id="disk-bar" style="width: 0%"></div>
                <span class="progress-text" id="disk-bar-text">0%</span>
            </div>
            <div class="stat-row">
                <span class="stat-label">Free</span>
                <span class="stat-value" id="disk-free">--</span>
            </div>
        </div>

        <!-- Network Card -->
        <div class="card">
            <div class="card-title">NETWORK</div>
            <div class="network-speeds">
                <div class="speed-box">
                    <div class="speed-label">Download</div>
                    <div class="speed-value" id="net-rx">-- /s</div>
                </div>
                <div class="speed-box">
                    <div class="speed-label">Upload</div>
                    <div class="speed-value" id="net-tx">-- /s</div>
                </div>
            </div>
            <div class="stat-row">
                <span class="stat-label">Total Received</span>
                <span class="stat-value" id="net-total-rx">--</span>
            </div>
            <div class="stat-row">
                <span class="stat-label">Total Sent</span>
                <span class="stat-value" id="net-total-tx">--</span>
            </div>
            <div class="interfaces" id="net-interfaces"></div>
        </div>

        <!-- Uptime Card -->
        <div class="card">
            <div class="card-title">SYSTEM</div>
            <div class="uptime-display" id="uptime">--:--:--</div>
            <div class="stat-row">
                <span class="stat-label">Uptime</span>
                <span class="stat-value">Since Boot</span>
            </div>
            <div class="load-avg">
                <div class="load-item">
                    <div class="load-label">1 min</div>
                    <div class="load-value" id="load-1">--</div>
                </div>
                <div class="load-item">
                    <div class="load-label">5 min</div>
                    <div class="load-value" id="load-5">--</div>
                </div>
                <div class="load-item">
                    <div class="load-label">15 min</div>
                    <div class="load-value" id="load-15">--</div>
                </div>
            </div>
        </div>
    </div>

    <!-- Processes Card (Full Width) -->
    <div class="card">
        <div class="card-title">TOP PROCESSES</div>
        <div class="process-list">
            <div class="process-row process-header">
                <span>PID</span>
                <span>NAME</span>
                <span>CPU%</span>
                <span>MEM%</span>
            </div>
            <div id="process-list"></div>
        </div>
    </div>

    <div class="footer">
        <p>Built with care by Claude on Raspberry Pi 5</p>
        <p>Auto-refreshing every second | Press Ctrl+C in terminal to stop</p>
    </div>

    <script>
        // Chart data storage
        const chartData = {
            cpu: [],
            mem: [],
            temp: []
        };
        const maxDataPoints = 60;

        // Simple chart drawing
        function drawChart(canvasId, data, color, maxVal = 100) {
            const canvas = document.getElementById(canvasId);
            if (!canvas) return;
            const ctx = canvas.getContext('2d');
            const width = canvas.width = canvas.offsetWidth;
            const height = canvas.height = canvas.offsetHeight;

            ctx.fillStyle = '#111111';
            ctx.fillRect(0, 0, width, height);

            if (data.length < 2) return;

            ctx.strokeStyle = color;
            ctx.lineWidth = 2;
            ctx.beginPath();

            const xStep = width / (maxDataPoints - 1);
            const startX = width - (data.length - 1) * xStep;

            data.forEach((val, i) => {
                const x = startX + i * xStep;
                const y = height - (val / maxVal) * height;
                if (i === 0) ctx.moveTo(x, y);
                else ctx.lineTo(x, y);
            });

            ctx.stroke();

            // Fill under the line
            ctx.lineTo(startX + (data.length - 1) * xStep, height);
            ctx.lineTo(startX, height);
            ctx.closePath();
            ctx.fillStyle = color + '20';
            ctx.fill();
        }

        function updateDashboard(stats) {
            // Update time
            document.getElementById('current-time').textContent =
                new Date().toLocaleTimeString();

            // CPU
            document.getElementById('cpu-percent').textContent =
                stats.cpu.percent.toFixed(1) + '%';
            document.getElementById('cpu-freq').textContent =
                stats.cpu.frequency.toFixed(0) + ' MHz';
            document.getElementById('cpu-count').textContent = stats.cpu.count;

            const cpuBar = document.getElementById('cpu-bar');
            cpuBar.style.width = stats.cpu.percent + '%';
            cpuBar.className = 'progress-fill' +
                (stats.cpu.percent > 90 ? ' danger' : stats.cpu.percent > 70 ? ' warning' : '');
            document.getElementById('cpu-bar-text').textContent =
                stats.cpu.percent.toFixed(0) + '%';

            // CPU Cores
            const coresDiv = document.getElementById('cpu-cores');
            coresDiv.innerHTML = stats.cpu.per_cpu.map((p, i) =>
                `<div class="cpu-core">C${i}: ${p.toFixed(0)}%</div>`
            ).join('');

            // Memory
            document.getElementById('mem-used').textContent =
                `${stats.memory.used_human} / ${stats.memory.total_human}`;
            document.getElementById('mem-available').textContent =
                stats.memory.total_human;
            document.getElementById('swap-percent').textContent =
                stats.swap.percent.toFixed(1) + '%';

            const memBar = document.getElementById('mem-bar');
            memBar.style.width = stats.memory.percent + '%';
            memBar.className = 'progress-fill' +
                (stats.memory.percent > 90 ? ' danger' : stats.memory.percent > 70 ? ' warning' : '');
            document.getElementById('mem-bar-text').textContent =
                stats.memory.percent.toFixed(0) + '%';

            // Temperature
            const tempDisplay = document.getElementById('temp-display');
            if (stats.temperature !== null) {
                tempDisplay.textContent = stats.temperature.toFixed(1) + '°C';
                tempDisplay.className = 'temp-display' +
                    (stats.temperature > 80 ? ' critical' : stats.temperature > 70 ? ' hot' : '');
            }

            // Throttle status
            if (stats.throttle) {
                updateThrottle('throttle-voltage', 'Under Voltage', stats.throttle.under_voltage);
                updateThrottle('throttle-freq', 'Freq Capped', stats.throttle.arm_freq_capped);
                updateThrottle('throttle-throttled', 'Throttled', stats.throttle.currently_throttled);
                updateThrottle('throttle-temp', 'Temp Limit', stats.throttle.soft_temp_limit);
            }

            // Disk
            document.getElementById('disk-used').textContent =
                `${stats.disk.used_human} / ${stats.disk.total_human}`;
            document.getElementById('disk-free').textContent = stats.disk.free_human;

            const diskBar = document.getElementById('disk-bar');
            diskBar.style.width = stats.disk.percent + '%';
            diskBar.className = 'progress-fill' +
                (stats.disk.percent > 90 ? ' danger' : stats.disk.percent > 80 ? ' warning' : '');
            document.getElementById('disk-bar-text').textContent =
                stats.disk.percent.toFixed(0) + '%';

            // Network
            document.getElementById('net-rx').textContent = stats.network.rx_speed_human;
            document.getElementById('net-tx').textContent = stats.network.tx_speed_human;
            document.getElementById('net-total-rx').textContent = stats.network.bytes_recv_human;
            document.getElementById('net-total-tx').textContent = stats.network.bytes_sent_human;

            // Network interfaces
            const ifDiv = document.getElementById('net-interfaces');
            ifDiv.innerHTML = Object.entries(stats.network.interfaces).map(([iface, ip]) =>
                `<div class="interface-row">
                    <span class="stat-label">${iface}</span>
                    <span class="stat-value">${ip}</span>
                </div>`
            ).join('');

            // Uptime
            document.getElementById('uptime').textContent = stats.uptime;

            // Load average
            document.getElementById('load-1').textContent = stats.load_avg[0].toFixed(2);
            document.getElementById('load-5').textContent = stats.load_avg[1].toFixed(2);
            document.getElementById('load-15').textContent = stats.load_avg[2].toFixed(2);

            // Processes
            const procDiv = document.getElementById('process-list');
            procDiv.innerHTML = stats.processes.map(p =>
                `<div class="process-row">
                    <span>${p.pid}</span>
                    <span>${p.name}</span>
                    <span>${p.cpu.toFixed(1)}%</span>
                    <span>${p.mem.toFixed(1)}%</span>
                </div>`
            ).join('');

            // Update charts
            chartData.cpu.push(stats.cpu.percent);
            chartData.mem.push(stats.memory.percent);
            if (stats.temperature) chartData.temp.push(stats.temperature);

            if (chartData.cpu.length > maxDataPoints) chartData.cpu.shift();
            if (chartData.mem.length > maxDataPoints) chartData.mem.shift();
            if (chartData.temp.length > maxDataPoints) chartData.temp.shift();

            drawChart('cpu-chart', chartData.cpu, '#00ff88');
            drawChart('mem-chart', chartData.mem, '#00ccff');
            drawChart('temp-chart', chartData.temp, '#ffcc00', 100);
        }

        function updateThrottle(id, label, active) {
            const el = document.getElementById(id);
            el.textContent = `${label}: ${active ? 'YES!' : 'OK'}`;
            el.className = 'throttle-item ' + (active ? 'active' : 'ok');
        }

        // Fetch and update
        async function refresh() {
            try {
                const response = await fetch('/api/stats');
                const stats = await response.json();
                updateDashboard(stats);
            } catch (e) {
                console.error('Failed to fetch stats:', e);
            }
        }

        // Initial load and start refresh loop
        refresh();
        setInterval(refresh, 1000);
    </script>
</body>
</html>
'''


@app.route('/')
def dashboard():
    """Serve the dashboard HTML"""
    return render_template_string(DASHBOARD_HTML)


@app.route('/api/stats')
def api_stats():
    """API endpoint for system stats"""
    return jsonify(get_system_stats())


@app.route('/api/history')
def api_history():
    """API endpoint for historical data"""
    with history_lock:
        return jsonify({
            'cpu': list(cpu_history),
            'memory': list(memory_history),
            'temperature': list(temp_history),
            'network': list(network_history),
        })


if __name__ == '__main__':
    print("""
    ╔═══════════════════════════════════════════════════════════════╗
    ║                                                               ║
    ║   🍓 Raspberry Pi System Monitor Dashboard                    ║
    ║   Built by Claude on your Raspberry Pi 5                      ║
    ║                                                               ║
    ║   Dashboard: http://localhost:5000                            ║
    ║   API:       http://localhost:5000/api/stats                  ║
    ║                                                               ║
    ║   Press Ctrl+C to stop the server                             ║
    ║                                                               ║
    ╚═══════════════════════════════════════════════════════════════╝
    """)

    # Run on all interfaces so it's accessible on the network
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
