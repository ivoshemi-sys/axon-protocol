#!/bin/bash
# Install OIXA Diffusion Agent as a permanent systemd service on the VPS
# Run as root: bash scripts/install_diffusion_agent.sh

set -e
REPO=/opt/oixa-protocol
VENV=$REPO/venv
SERVICE_SRC=$REPO/agents/diffusion_agent/oixa-diffusion.service
SERVICE_DST=/etc/systemd/system/oixa-diffusion.service

echo "=== OIXA Diffusion Agent — installer ==="

# 1. Install Python deps (httpx already in main requirements)
echo "[1/5] Installing Python dependencies..."
$VENV/bin/pip install httpx -q

# 2. Copy service file
echo "[2/5] Installing systemd service..."
cp "$SERVICE_SRC" "$SERVICE_DST"
chmod 644 "$SERVICE_DST"

# 3. Reload systemd and enable
echo "[3/5] Enabling service..."
systemctl daemon-reload
systemctl enable oixa-diffusion.service

# 4. Start the service
echo "[4/5] Starting service..."
systemctl start oixa-diffusion.service

# 5. Status
echo "[5/5] Status:"
sleep 2
systemctl status oixa-diffusion.service --no-pager -l | head -20

echo ""
echo "=== Installation complete ==="
echo "Logs:   journalctl -u oixa-diffusion -f"
echo "State:  cat /opt/oixa-protocol/diffusion_state.json | python3 -m json.tool"
echo "Status: systemctl status oixa-diffusion"
echo ""
echo "Optional env vars to add to /opt/oixa-protocol/.env:"
echo "  AGENTVERSE_API_KEY=<key from agentverse.ai/settings>"
echo "  GITHUB_TOKEN=<personal access token with repo scope>"
echo "  HUGGINGFACE_TOKEN=<token from huggingface.co/settings/tokens>"
