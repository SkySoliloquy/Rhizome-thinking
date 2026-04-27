#!/bin/bash
set -e

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SERVICE_FILE="/etc/systemd/system/rhizome.service"

sed "s|/opt/rhizome-thinking|${PROJECT_DIR}|g" \
    "$PROJECT_DIR/scripts/rhizome.service" | sudo tee "$SERVICE_FILE"

sudo systemctl daemon-reload
sudo systemctl enable rhizome
sudo systemctl start rhizome

echo "done: systemctl status rhizome"
