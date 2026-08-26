#!/bin/bash
#
# Create launchd services for Xiaozhi auto-start on boot
# Server and client both run as background daemons
#

INSTALL_DIR="$HOME/xiaozhi-voice-assistant"
SERVER_APP="$INSTALL_DIR/xiaozhi-esp32-server/main/xiaozhi-server"
CLIENT_APP="$INSTALL_DIR/py-xiaozhi"
LAUNCH_DIR="$HOME/Library/LaunchAgents"

mkdir -p "$LAUNCH_DIR"

# --- Server launchd plist ---
cat > "$LAUNCH_DIR/com.sambawy.xiaozhi-server.plist" << PLISTEOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.sambawy.xiaozhi-server</string>
    <key>ProgramArguments</key>
    <array>
        <string>${SERVER_APP}/.venv/bin/python</string>
        <string>app.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>${SERVER_APP}</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>${INSTALL_DIR}/server.log</string>
    <key>StandardErrorPath</key>
    <string>${INSTALL_DIR}/server.err.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>OLLAMA_MODELS</key>
        <string>/Volumes/Sambawy/untitled folder/ollama-models</string>
        <key>PATH</key>
        <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
    </dict>
</dict>
</plist>
PLISTEOF

# --- Ollama launchd plist (must start before server) ---
cat > "$LAUNCH_DIR/com.sambawy.ollama.plist" << PLISTEOF2
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.sambawy.ollama</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/ollama</string>
        <string>serve</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>${INSTALL_DIR}/ollama.log</string>
    <key>StandardErrorPath</key>
    <string>${INSTALL_DIR}/ollama.err.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>OLLAMA_MODELS</key>
        <string>/Volumes/Sambawy/untitled folder/ollama-models</string>
    </dict>
</dict>
</plist>
PLISTEOF2

# --- Client launchd plist ---
cat > "$LAUNCH_DIR/com.sambawy.xiaozhi-client.plist" << PLISTEOF3
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.sambawy.xiaozhi-client</string>
    <key>ProgramArguments</key>
    <array>
        <string>${CLIENT_APP}/.venv/bin/python</string>
        <string>main.py</string>
        <string>--mode</string>
        <string>cli</string>
        <string>--protocol</string>
        <string>websocket</string>
    </array>
    <key>WorkingDirectory</key>
    <string>${CLIENT_APP}</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>${INSTALL_DIR}/client.log</string>
    <key>StandardErrorPath</key>
    <string>${INSTALL_DIR}/client.err.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
    </dict>
</dict>
</plist>
PLISTEOF3

echo "Created 3 launchd services:"
echo "  com.sambawy.ollama"
echo "  com.sambawy.xiaozhi-server"
echo "  com.sambawy.xiaozhi-client"
echo ""

# Check if ollama is at /usr/local/bin or /opt/homebrew/bin
OLLAMA_PATH=""
for p in /usr/local/bin/ollama /opt/homebrew/bin/ollama "$HOME/.ollama/ollama"; do
    if [ -f "$p" ]; then
        OLLAMA_PATH="$p"
        break
    fi
done
if [ -n "$OLLAMA_PATH" ] && [ "$OLLAMA_PATH" != "/usr/local/bin/ollama" ]; then
    echo "Fixing ollama path in plist: $OLLAMA_PATH"
    sed -i '' "s|/usr/local/bin/ollama|$OLLAMA_PATH|g" "$LAUNCH_DIR/com.sambawy.ollama.plist"
fi

echo "Loading services now..."
launchctl unload "$LAUNCH_DIR/com.sambawy.ollama.plist" 2>/dev/null || true
launchctl unload "$LAUNCH_DIR/com.sambawy.xiaozhi-server.plist" 2>/dev/null || true
launchctl unload "$LAUNCH_DIR/com.sambawy.xiaozhi-client.plist" 2>/dev/null || true

launchctl load "$LAUNCH_DIR/com.sambawy.ollama.plist"
sleep 2
launchctl load "$LAUNCH_DIR/com.sambawy.xiaozhi-server.plist"
sleep 3
launchctl load "$LAUNCH_DIR/com.sambawy.xiaozhi-client.plist"

echo ""
echo "DONE! Services are running."
echo ""
echo "  Check status:  launchctl list | grep sambawy"
echo "  Server logs:    tail -f $INSTALL_DIR/server.log"
echo "  Client logs:    tail -f $INSTALL_DIR/client.log"
echo "  Ollama logs:    tail -f $INSTALL_DIR/ollama.log"
echo ""
echo "  Stop all:       ~/xiaozhi-voice-assistant/stop-services.sh"
echo "  Start all:      ~/xiaozhi-voice-assistant/start-services.sh"
echo ""
echo "  Services auto-start on boot. Make sure your external disk"
echo "  '/Volumes/Sambawy/untitled folder' is mounted before boot."
echo ""

# Create start/stop service scripts
cat > "$INSTALL_DIR/stop-services.sh" << 'STOPEOF'
#!/bin/bash
launchctl unload "$HOME/Library/LaunchAgents/com.sambawy.xiaozhi-client.plist" 2>/dev/null
launchctl unload "$HOME/Library/LaunchAgents/com.sambawy.xiaozhi-server.plist" 2>/dev/null
launchctl unload "$HOME/Library/LaunchAgents/com.sambawy.ollama.plist" 2>/dev/null
echo "All Xiaozhi services stopped"
STOPEOF
chmod +x "$INSTALL_DIR/stop-services.sh"

cat > "$INSTALL_DIR/start-services.sh" << 'STARTEOF'
#!/bin/bash
launchctl load "$HOME/Library/LaunchAgents/com.sambawy.ollama.plist" 2>/dev/null
sleep 2
launchctl load "$HOME/Library/LaunchAgents/com.sambawy.xiaozhi-server.plist" 2>/dev/null
sleep 3
launchctl load "$HOME/Library/LaunchAgents/com.sambawy.xiaozhi-client.plist" 2>/dev/null
echo "All Xiaozhi services started"
echo "  Check: launchctl list | grep sambawy"
STARTEOF
chmod +x "$INSTALL_DIR/start-services.sh"

echo "Created start-services.sh and stop-services.sh"