#!/bin/bash
#
# Xiaozhi Voice Assistant - One-Shot Setup Script for Mac Mini
# ============================================================
# Installs a complete local voice AI: Wake Word -> STT -> LLM -> TTS
# No cloud API keys needed. Runs entirely on your Mac Mini.
#
# Models stored on external disk: /Volumes/Sambawy/untitled folder/ollama-models
#
# Usage:
#   chmod +x setup-xiaozhi.sh
#   ./setup-xiaozhi.sh
#

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${GREEN}"
echo "  ============================================================"
echo "  |   Xiaozhi Voice Assistant - Mac Mini Setup              |"
echo "  |   Local AI: Wake Word -> STT -> LLM -> TTS              |"
echo "  |   Models on: /Volumes/Sambawy/untitled folder            |"
echo "  ============================================================"
echo -e "${NC}"

INSTALL_DIR="$HOME/xiaozhi-voice-assistant"
SERVER_DIR="$INSTALL_DIR/xiaozhi-esp32-server"
CLIENT_DIR="$INSTALL_DIR/py-xiaozhi"

# External disk for Ollama models (~5GB)
EXT_DISK="/Volumes/Sambawy/untitled folder"
OLLAMA_MODELS_DIR="$EXT_DISK/ollama-models"

# ─────────────────────────────────────────────────────────
# STEP 1: Check prerequisites
# ─────────────────────────────────────────────────────────
echo -e "${BLUE}[1/8] Checking prerequisites...${NC}"

if [ "$(uname)" != "Darwin" ]; then
    echo -e "${RED}This script is for macOS only.${NC}"
    exit 1
fi

echo -e "  Installing Python 3.11 via Homebrew..."
brew install python@3.11 2>/dev/null || true
PYTHON311="/opt/homebrew/bin/python3.11"
if [ ! -f "$PYTHON311" ]; then
    PYTHON311="$(brew --prefix python@3.11)/bin/python3.11"
fi
if [ ! -f "$PYTHON311" ]; then
    echo -e "${RED}Python 3.11 install failed.${NC}"
    exit 1
fi
echo -e "  Python 3.11: $($PYTHON311 --version)"

if ! command -v brew >/dev/null 2>&1; then
    echo -e "${YELLOW}  Installing Homebrew...${NC}"
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    eval "$(/opt/homebrew/bin/brew shellenv)"
fi
echo -e "  Homebrew: OK"

# Check external disk is mounted
if [ ! -d "$EXT_DISK" ]; then
    echo -e "${RED}External disk not found at: $EXT_DISK${NC}"
    echo -e "${YELLOW}Make sure the drive is mounted, then re-run this script.${NC}"
    exit 1
fi
echo -e "  External disk: $EXT_DISK"

echo -e "${GREEN}  Prerequisites OK${NC}"

# ─────────────────────────────────────────────────────────
# STEP 2: Install system dependencies
# ─────────────────────────────────────────────────────────
echo -e "${BLUE}[2/8] Installing system dependencies...${NC}"
brew install ffmpeg opus portaudio git 2>/dev/null || true
echo -e "${GREEN}  System dependencies OK${NC}"

# ─────────────────────────────────────────────────────────
# STEP 3: Install Ollama + store models on external disk
# ─────────────────────────────────────────────────────────
echo -e "${BLUE}[3/8] Setting up Ollama on external disk...${NC}"

if ! command -v ollama >/dev/null 2>&1; then
    echo -e "  Installing Ollama..."
    curl -fsSL https://ollama.com/install.sh | sh
fi

# Create model directory on external disk
mkdir -p "$OLLAMA_MODELS_DIR"
export OLLAMA_MODELS="$OLLAMA_MODELS_DIR"

# Persist for future sessions
if ! grep -q "OLLAMA_MODELS=" "$HOME/.zprofile" 2>/dev/null; then
    echo "export OLLAMA_MODELS=\"$OLLAMA_MODELS_DIR\"" >> "$HOME/.zprofile"
    echo -e "  Saved OLLAMA_MODELS to ~/.zprofile"
fi
echo -e "  Models will be stored at: $OLLAMA_MODELS_DIR"

# Start Ollama
if ! pgrep -x ollama >/dev/null 2>&1; then
    echo -e "  Starting Ollama service..."
    OLLAMA_MODELS="$OLLAMA_MODELS_DIR" nohup ollama serve > /dev/null 2>&1 &
    sleep 3
fi

# Pull qwen2.5 model (~4.7GB) to external disk
echo -e "  Pulling qwen2.5 model to external disk (~4.7GB)..."
echo -e "  This takes a few minutes depending on disk speed..."
OLLAMA_MODELS="$OLLAMA_MODELS_DIR" ollama pull qwen2.5

echo -e "${GREEN}  Ollama OK - models on external disk${NC}"

# ─────────────────────────────────────────────────────────
# STEP 4: Clone repositories
# ─────────────────────────────────────────────────────────
echo -e "${BLUE}[4/8] Cloning repositories...${NC}"

mkdir -p "$INSTALL_DIR"
cd "$INSTALL_DIR"

if [ ! -d "$SERVER_DIR" ]; then
    echo -e "  Cloning xiaozhi-esp32-server..."
    git clone https://github.com/xinnan-tech/xiaozhi-esp32-server.git "$SERVER_DIR"
else
    echo -e "  Server repo exists, skipping"
fi

if [ ! -d "$CLIENT_DIR" ]; then
    echo -e "  Cloning py-xiaozhi..."
    git clone https://github.com/huangjunsen0406/py-xiaozhi.git "$CLIENT_DIR"
else
    echo -e "  Client repo exists, skipping"
fi

echo -e "${GREEN}  Repositories OK${NC}"

# ─────────────────────────────────────────────────────────
# STEP 5: Set up the server
# ─────────────────────────────────────────────────────────
echo -e "${BLUE}[5/8] Setting up xiaozhi-esp32-server...${NC}"

cd "$SERVER_DIR/main/xiaozhi-server"

if [ ! -d ".venv" ]; then
    $PYTHON311 -m venv .venv
fi

source .venv/bin/activate
pip install --upgrade pip
echo -e "  Installing server dependencies, please wait..."
pip install -r requirements.txt

mkdir -p data
mkdir -p models

# Write server config
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
  Keep responses short and natural for voice interaction, max 2-3 sentences.
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
# STEP 6: Set up the client
# ─────────────────────────────────────────────────────────
echo -e "${BLUE}[6/8] Setting up py-xiaozhi client...${NC}"

cd "$CLIENT_DIR"

if [ ! -d ".venv" ]; then
    $PYTHON311 -m venv .venv
fi

source .venv/bin/activate
pip install --upgrade pip
echo -e "  Installing client dependencies, please wait..."
pip install -e .

echo -e "${GREEN}  Client setup OK${NC}"

# ─────────────────────────────────────────────────────────
# STEP 7: Create launch scripts
# ─────────────────────────────────────────────────────────
echo -e "${BLUE}[7/8] Creating launch scripts...${NC}"

# Server launcher
cat > "$INSTALL_DIR/start-server.sh" << 'SRVEOF'
#!/bin/bash
cd "$(dirname "$0")/xiaozhi-esp32-server/main/xiaozhi-server"
source .venv/bin/activate
echo "Starting Xiaozhi Server..."
echo "  WebSocket: ws://127.0.0.1:8000/xiaozhi/v1/"
echo "  OTA:       http://127.0.0.1:8003/xiaozhi/ota/"
echo ""
python app.py
SRVEOF
chmod +x "$INSTALL_DIR/start-server.sh"

# Client CLI launcher
cat > "$INSTALL_DIR/start-client.sh" << 'CLIEOF'
#!/bin/bash
cd "$(dirname "$0")/py-xiaozhi"
source .venv/bin/activate
echo "Starting Xiaozhi Voice Client..."
echo "  Say 'hey xiaozhi' to wake it up"
echo ""
python main.py --mode cli --protocol websocket
CLIEOF
chmod +x "$INSTALL_DIR/start-client.sh"

# Client GUI launcher
cat > "$INSTALL_DIR/start-client-gui.sh" << 'GUIEOF'
#!/bin/bash
cd "$(dirname "$0")/py-xiaozhi"
source .venv/bin/activate
echo "Starting Xiaozhi Voice Client GUI..."
python main.py --mode gui --protocol websocket
GUIEOF
chmod +x "$INSTALL_DIR/start-client-gui.sh"

# Stop all
cat > "$INSTALL_DIR/stop-all.sh" << 'STOPEOF'
#!/bin/bash
echo "Stopping Xiaozhi services..."
pkill -f "python app.py" 2>/dev/null && echo "  Server stopped" || echo "  Server was not running"
pkill -f "python main.py" 2>/dev/null && echo "  Client stopped" || echo "  Client was not running"
pkill -x ollama 2>/dev/null && echo "  Ollama stopped" || echo "  Ollama was not running"
STOPEOF
chmod +x "$INSTALL_DIR/stop-all.sh"

echo -e "${GREEN}  Launch scripts OK${NC}"

# ─────────────────────────────────────────────────────────
# STEP 8: Configure client
# ─────────────────────────────────────────────────────────
echo -e "${BLUE}[8/8] Configuring client...${NC}"

CLIENT_CFG="$HOME/Library/Application Support/py-xiaozhi/config"
mkdir -p "$CLIENT_CFG"

cat > "$CLIENT_CFG/config.json" << 'CONFJSON'
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
echo -e "${GREEN}============================================================${NC}"
echo -e "${GREEN}  INSTALLATION COMPLETE${NC}"
echo -e "${GREEN}============================================================${NC}"
echo ""
echo -e "  Install dir: ${BLUE}$INSTALL_DIR${NC}"
echo -e "  Ollama models: ${BLUE}$OLLAMA_MODELS_DIR${NC}"
echo ""
echo -e "${YELLOW}  HOW TO START:${NC}"
echo ""
echo -e "  Terminal 1 - Start server:"
echo -e "    ${BLUE}$INSTALL_DIR/start-server.sh${NC}"
echo ""
echo -e "  Terminal 2 - Start voice client:"
echo -e "    ${BLUE}$INSTALL_DIR/start-client.sh${NC}"
echo ""
echo -e "  Then say: ${YELLOW}hey xiaozhi${NC} and speak"
echo ""
echo -e "${YELLOW}  TO STOP:${NC}"
echo -e "    ${BLUE}$INSTALL_DIR/stop-all.sh${NC}"
echo ""
echo -e "${YELLOW}  NOTES:${NC}"
echo -e "  - First server start downloads ASR model ~900MB automatically"
echo -e "  - Ollama qwen2.5 uses ~6GB RAM, stored on external disk"
echo -e "  - EdgeTTS needs internet, everything else is local"
echo -e "  - Edit personality: $INSTALL_DIR/xiaozhi-esp32-server/main/xiaozhi-server/data/.config.yaml"
echo ""