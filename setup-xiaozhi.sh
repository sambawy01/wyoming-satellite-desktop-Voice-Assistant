#!/bin/bash
#
# Xiaozhi Voice Assistant - One-Shot Setup Script for Mac Mini
# ============================================================
# This script installs:
#   1. Ollama + qwen2.5 model (local LLM brain)
#   2. xiaozhi-esp32-server (voice pipeline: STT -> LLM -> TTS)
#   3. py-xiaozhi client (mic + speaker + wake word detection)
#
# Everything runs locally on your Mac Mini. No cloud APIs needed.
# Works on macOS (Apple Silicon and Intel).
#
# Usage:
#   chmod +x setup-xiaozhi.sh
#   ./setup-xiaozhi.sh
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${GREEN}"
echo "  ╔══════════════════════════════════════════════════════════╗"
echo "  ║     Xiaozhi Voice Assistant - Mac Mini Setup             ║"
echo "  ║     Local AI: Wake Word -> STT -> LLM -> TTS             ║"
echo "  ╚══════════════════════════════════════════════════════════╝"
echo -e "${NC}"

INSTALL_DIR="$HOME/xiaozhi-voice-assistant"
SERVER_DIR="$INSTALL_DIR/xiaozhi-esp32-server"
CLIENT_DIR="$INSTALL_DIR/py-xiaozhi"

# ─────────────────────────────────────────────────────────
# STEP 1: Check prerequisites
# ─────────────────────────────────────────────────────────
echo -e "${BLUE}[1/8] Checking prerequisites...${NC}"

# Check macOS
if [[ "$(uname)" != "Darwin" ]]; then
    echo -e "${RED}This script is designed for macOS only.${NC}"
    exit 1
fi

# Check Python 3.10+
if ! command -v python3 &>/dev/null; then
    echo -e "${RED}Python 3 is not installed. Please install Python 3.10+ first.${NC}"
    echo -e "${YELLOW}  brew install python@3.11${NC}"
    exit 1
fi

PY_VERSION=$(python3 -c "import sys; print(float(str(sys.version_info[0])+'.'+str(sys.version_info[1])))")
if (( $(echo "$PY_VERSION < 3.10" | bc -l) )); then
    echo -e "${RED}Python 3.10+ required, found $(python3 --version).${NC}"
    exit 1
fi
echo -e "  Python: $(python3 --version) OK"

# Check brew
if ! command -v brew &>/dev/null; then
    echo -e "${YELLOW}  Homebrew not found. Installing...${NC}"
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> "$HOME/.zprofile"
    eval "$(/opt/homebrew/bin/brew shellenv)"
fi
echo -e "  Homebrew: OK"

echo -e "${GREEN}  Prerequisites OK${NC}"

# ─────────────────────────────────────────────────────────
# STEP 2: Install system dependencies
# ─────────────────────────────────────────────────────────
echo -e "${BLUE}[2/8] Installing system dependencies...${NC}"

brew install ffmpeg opus portaudio git curl 2>/dev/null || true
echo -e "${GREEN}  System dependencies OK${NC}"

# ─────────────────────────────────────────────────────────
# STEP 3: Install Ollama (local LLM)
# ─────────────────────────────────────────────────────────
echo -e "${BLUE}[3/8] Setting up Ollama (local LLM brain)...${NC}"

if ! command -v ollama &>/dev/null; then
    echo -e "  Installing Ollama..."
    curl -fsSL https://ollama.com/install.sh | sh
fi

# Start Ollama service
if ! pgrep -x "ollama" &>/dev/null; then
    echo -e "  Starting Ollama service..."
    ollama serve &
    sleep 3
fi

# Pull the qwen2.5 model (good balance of quality and speed)
echo -e "  Pulling qwen2.5 model (this may take a few minutes)..."
ollama pull qwen2.5

echo -e "${GREEN}  Ollama OK${NC}"

# ─────────────────────────────────────────────────────────
# STEP 4: Clone repositories
# ─────────────────────────────────────────────────────────
echo -e "${BLUE}[4/8] Cloning repositories...${NC}"

mkdir -p "$INSTALL_DIR"
cd "$INSTALL_DIR"

# Clone server
if [ ! -d "$SERVER_DIR" ]; then
    echo -e "  Cloning xiaozhi-esp32-server..."
    git clone https://github.com/xinnan-tech/xiaozhi-esp32-server.git "$SERVER_DIR"
else
    echo -e "  Server repo already exists, skipping clone"
fi

# Clone client
if [ ! -d "$CLIENT_DIR" ]; then
    echo -e "  Cloning py-xiaozhi..."
    git clone https://github.com/huangjunsen0406/py-xiaozhi.git "$CLIENT_DIR"
else
    echo -e "  Client repo already exists, skipping clone"
fi

echo -e "${GREEN}  Repositories cloned OK${NC}"

# ─────────────────────────────────────────────────────────
# STEP 5: Set up the server virtual environment
# ─────────────────────────────────────────────────────────
echo -e "${BLUE}[5/8] Setting up xiaozhi-esp32-server...${NC}"

cd "$SERVER_DIR/main/xiaozhi-server"

# Create virtual environment
if [ ! -d ".venv" ]; then
    echo -e "  Creating Python virtual environment..."
    python3 -m venv .venv
fi

# Activate and install dependencies
source .venv/bin/activate
echo -e "  Upgrading pip..."
pip install --upgrade pip
echo -e "  Installing server dependencies (this may take a few minutes)..."
pip install -r requirements.txt

# Create data directory and config
mkdir -p data
mkdir -p models

# Write the .config.yaml file
cat > data/.config.yaml << 'CONFIGEOF'
server:
  ip: 0.0.0.0
  port: 8000
  http_port: 8003
  websocket: ws://127.0.0.1:8000/xiaozhi/v1/
  vision_explain: http://127.0.0.1:8003/mcp/vision/explain
  timezone_offset: +2
  auth:
    enabled: false

log:
  log_level: INFO

close_connection_no_voice_time: 180

wakeup_words:
  - "hey xiaozhi"
  - "hello xiaozhi"
  - "hi xiaozhi"
  - "hey jarvis"
  - "hello jarvis"

prompt: |
  You are Xiaozhi, a helpful home AI assistant running on a Mac Mini.
  You are friendly, concise, and proactive. You can answer questions,
  control smart home devices, search the web, play music, and more.
  Keep responses short and natural for voice interaction (max 2-3 sentences).
  When the user asks you to do something, try your best to execute it.
  If you are not sure about something, ask for clarification.

system_error_response: "Sorry, I had a problem. Can you try again?"

exit_commands:
  - "exit"
  - "quit"
  - "goodbye"
  - "bye"

selected_module:
  VAD: SileroVAD
  ASR: SherpaASR
  LLM: OllamaLLM
  TTS: EdgeTTS
  VLLM: OllamaLLM
  Memory: mem_local_short
  Intent: function_call

Memory:
  mem_local_short:
    type: mem_local_short
    llm: OllamaLLM

ASR:
  SherpaASR:
    type: sherpa_onnx_local
    model_dir: models/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17
    output_dir: tmp/
    model_type: sense_voice

VAD:
  SileroVAD:
    type: silero
    threshold: 0.5
    threshold_low: 0.3
    model_dir: models/snakers4_silero-vad
    min_silence_duration_ms: 200

LLM:
  OllamaLLM:
    type: ollama
    model_name: qwen2.5
    base_url: http://127.0.0.1:11434

TTS:
  EdgeTTS:
    type: edge
    voice: en-US-AriaNeural
    output_dir: tmp/

Intent:
  function_call:
    type: function_call
    functions:
      - get_weather
      - get_news_from_newsnow
      - play_music
      - web_search
CONFIGEOF

echo -e "${GREEN}  Server setup OK${NC}"

# ─────────────────────────────────────────────────────────
# STEP 6: Set up the client virtual environment
# ─────────────────────────────────────────────────────────
echo -e "${BLUE}[6/8] Setting up py-xiaozhi client...${NC}"

cd "$CLIENT_DIR"

# Create virtual environment
if [ ! -d ".venv" ]; then
    echo -e "  Creating Python virtual environment..."
    python3 -m venv .venv
fi

source .venv/bin/activate
echo -e "  Upgrading pip..."
pip install --upgrade pip
echo -e "  Installing client dependencies (this may take a few minutes)..."
pip install -e .

echo -e "${GREEN}  Client setup OK${NC}"

# ─────────────────────────────────────────────────────────
# STEP 7: Create launch scripts
# ─────────────────────────────────────────────────────────
echo -e "${BLUE}[7/8] Creating launch scripts...${NC}"

# Server launch script
cat > "$INSTALL_DIR/start-server.sh" << 'SRVEOF'
#!/bin/bash
# Start the xiaozhi voice pipeline server
cd "$(dirname "$0")/xiaozhi-esp32-server/main/xiaozhi-server"
source .venv/bin/activate
echo "Starting Xiaozhi Server..."
echo "  WebSocket: ws://127.0.0.1:8000/xiaozhi/v1/"
echo "  OTA:       http://127.0.0.1:8003/xiaozhi/ota/"
echo ""
python app.py
SRVEOF
chmod +x "$INSTALL_DIR/start-server.sh"

# Client launch script (CLI mode - no GUI needed)
cat > "$INSTALL_DIR/start-client.sh" << 'CLIEOF'
#!/bin/bash
# Start the py-xiaozhi voice client (CLI mode)
cd "$(dirname "$0")/py-xiaozhi"
source .venv/bin/activate
echo "Starting Xiaozhi Voice Client..."
echo "  Say 'hey xiaozhi' to wake it up"
echo ""
python main.py --mode cli --protocol websocket
CLIEOF
chmod +x "$INSTALL_DIR/start-client.sh"

# Client launch script (GUI mode)
cat > "$INSTALL_DIR/start-client-gui.sh" << 'GUIEOF'
#!/bin/bash
# Start the py-xiaozhi voice client (GUI mode)
cd "$(dirname "$0")/py-xiaozhi"
source .venv/bin/activate
echo "Starting Xiaozhi Voice Client (GUI)..."
python main.py --mode gui --protocol websocket
GUIEOF
chmod +x "$INSTALL_DIR/start-client-gui.sh"

# Stop script
cat > "$INSTALL_DIR/stop-all.sh" << 'STOPEOF'
#!/bin/bash
# Stop all Xiaozhi services
echo "Stopping Xiaozhi services..."
pkill -f "python app.py" 2>/dev/null && echo "  Server stopped" || echo "  Server was not running"
pkill -f "python main.py" 2>/dev/null && echo "  Client stopped" || echo "  Client was not running"
pkill -x "ollama" 2>/dev/null && echo "  Ollama stopped" || echo "  Ollama was not running"
STOPEOF
chmod +x "$INSTALL_DIR/stop-all.sh"

echo -e "${GREEN}  Launch scripts created OK${NC}"

# ─────────────────────────────────────────────────────────
# STEP 8: Create client config
# ─────────────────────────────────────────────────────────
echo -e "${BLUE}[8/8] Configuring client...${NC}"

# py-xiaozhi config directory on macOS
CLIENT_CONFIG_DIR="$HOME/Library/Application Support/py-xiaozhi/config"
mkdir -p "$CLIENT_CONFIG_DIR"

# Create config.json pointing to local server
cat > "$CLIENT_CONFIG_DIR/config.json" << 'CONFJSON'
{
  "CONFIG_VERSION": 1,
  "SYSTEM_OPTIONS": {
    "CLIENT_ID": null,
    "DEVICE_ID": null,
    "WINDOW_SIZE_MODE": "default",
    "NETWORK": {
      "OTA_VERSION_URL": "http://127.0.0.1:8003/xiaozhi/ota/",
      "WEBSOCKET_URL": "ws://127.0.0.1:8000/xiaozhi/v1/",
      "WEBSOCKET_ACCESS_TOKEN": null,
      "MQTT_INFO": null,
      "ACTIVATION_VERSION": "v2",
      "AUTHORIZATION_URL": "http://127.0.0.1:8003/"
    }
  },
  "WAKE_WORD_OPTIONS": {
    "USE_WAKE_WORD": true,
    "MODEL_PATH": "models/en",
    "NUM_THREADS": 5,
    "PROVIDER": "cpu",
    "MAX_ACTIVE_PATHS": 2,
    "KEYWORDS_SCORE": 1.8,
    "KEYWORDS_THRESHOLD": 0.2,
    "NUM_TRAILING_BLANKS": 1,
    "WAKE_WORD": "hey xiaozhi",
    "WAKE_WORD_LANG": "en"
  }
}
CONFJSON

echo -e "${GREEN}  Client config OK${NC}"

# ─────────────────────────────────────────────────────────
# DONE
# ─────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  INSTALLATION COMPLETE!${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "  Install directory: ${BLUE}$INSTALL_DIR${NC}"
echo ""
echo -e "${YELLOW}  HOW TO START:${NC}"
echo ""
echo -e "  Terminal 1 - Start the server:"
echo -e "    ${BLUE}$INSTALL_DIR/start-server.sh${NC}"
echo ""
echo -e "  Terminal 2 - Start the voice client:"
echo -e "    ${BLUE}$INSTALL_DIR/start-client.sh${NC}"
echo ""
echo -e "  Then say: ${YELLOW}\"hey xiaozhi\"${NC} and speak your request"
echo ""
echo -e "${YELLOW}  TO STOP:${NC}"
echo -e "    ${BLUE}$INSTALL_DIR/stop-all.sh${NC}"
echo ""
echo -e "${YELLOW}  NOTES:${NC}"
echo -e "  - First server start will download the ASR model (~900MB) automatically"
echo -e "  - Ollama qwen2.5 model uses ~4.7GB of RAM"
echo -e "  - EdgeTTS requires internet (free Microsoft cloud TTS)"
echo -e "  - To use a different LLM, edit:"
echo -e "    $INSTALL_DIR/xiaozhi-esp32-server/main/xiaozhi-server/data/.config.yaml"
echo -e "  - To change the AI personality, edit the 'prompt:' section in the same file"
echo -e "  - To use a different wake word, edit the client config at:"
echo -e "    $HOME/Library/Application Support/py-xiaozhi/config/config.json"
echo ""