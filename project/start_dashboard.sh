#!/bin/bash
# Start the Raspberry Pi Dashboard
# Built by Claude

cd "$(dirname "$0")"

echo "Starting Raspberry Pi Dashboard..."
echo "Open http://$(hostname -I | awk '{print $1}'):5000 in your browser"
echo ""

python3 pi_dashboard.py
