#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLIST_NAME="com.whatsapp.bridge.plist"
PLIST_SRC="$SCRIPT_DIR/$PLIST_NAME"
PLIST_DST="$HOME/Library/LaunchAgents/$PLIST_NAME"

echo "WhatsApp Bridge Daemon Setup"
echo "============================"
echo ""

# Step 1: Build the Go binary
echo "[1/4] Building Go binary..."
cd "$SCRIPT_DIR"
go build -o whatsapp-bridge main.go
echo "      Built: $SCRIPT_DIR/whatsapp-bridge"

# Step 2: Create logs directory
echo "[2/4] Creating logs directory..."
mkdir -p "$SCRIPT_DIR/logs"
echo "      Created: $SCRIPT_DIR/logs/"

# Step 3: Unload existing daemon if present
if launchctl list | grep -q "com.whatsapp.bridge"; then
    echo "[3/4] Stopping existing daemon..."
    launchctl unload "$PLIST_DST" 2>/dev/null || true
else
    echo "[3/4] No existing daemon to stop"
fi

# Step 4: Install and load the daemon
echo "[4/4] Installing LaunchAgent..."
mkdir -p "$HOME/Library/LaunchAgents"
cp "$PLIST_SRC" "$PLIST_DST"
launchctl load "$PLIST_DST"

echo ""
echo "Done! WhatsApp Bridge daemon is now running."
echo ""
echo "Useful commands:"
echo "  Check status:  launchctl list | grep whatsapp"
echo "  View logs:     tail -f $SCRIPT_DIR/logs/bridge.log"
echo "  View errors:   tail -f $SCRIPT_DIR/logs/bridge.error.log"
echo "  Stop daemon:   launchctl unload $PLIST_DST"
echo "  Start daemon:  launchctl load $PLIST_DST"
echo "  Uninstall:     launchctl unload $PLIST_DST && rm $PLIST_DST"
echo ""
echo "NOTE: If this is the first run, check logs for QR code authentication."
