#!/bin/bash
# Run this script to authenticate with WhatsApp (displays QR code in terminal)
# Only needed for first-time setup or re-authentication

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLIST_DST="$HOME/Library/LaunchAgents/com.whatsapp.bridge.plist"

echo "WhatsApp Bridge Authentication"
echo "=============================="
echo ""

# Stop daemon if running (so it doesn't interfere)
if launchctl list | grep -q "com.whatsapp.bridge"; then
    echo "Stopping daemon for authentication..."
    launchctl unload "$PLIST_DST" 2>/dev/null || true
fi

echo "Starting bridge interactively..."
echo "Scan the QR code with WhatsApp on your phone."
echo "Press Ctrl+C when done."
echo ""

cd "$SCRIPT_DIR"

# Build if needed
if [ ! -f "./whatsapp-bridge" ]; then
    echo "Building..."
    go build -o whatsapp-bridge main.go
fi

./whatsapp-bridge

echo ""
echo "Authentication complete. Restart the daemon with:"
echo "  launchctl load $PLIST_DST"
