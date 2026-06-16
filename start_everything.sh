#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

if [[ ! -x "/opt/homebrew/bin/brew" ]]; then
  echo "Homebrew not found at /opt/homebrew/bin/brew"
  exit 1
fi

# Load Homebrew environment in this shell.
eval "$(/opt/homebrew/bin/brew shellenv)"

export JAVA_HOME="/opt/homebrew/opt/openjdk/libexec/openjdk.jdk/Contents/Home"
export PATH="/opt/homebrew/opt/openjdk/bin:$PATH"

PYTHON_BIN="$ROOT_DIR/.venv/bin/python"
if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "Python virtual environment missing at $PYTHON_BIN"
  echo "Create it first: /opt/homebrew/bin/python3.11 -m venv .venv && .venv/bin/python -m pip install -r requirements.txt"
  exit 1
fi

TIKA_JAR="$ROOT_DIR/tika/tika-server-2.9.2.jar"
if [[ ! -f "$TIKA_JAR" ]]; then
  echo "Tika JAR not found: $TIKA_JAR"
  exit 1
fi

mkdir -p runtime/logs runtime/pids runtime/temp/tika1 runtime/temp/tika2 runtime/temp/tika3 runtime/temp/tika4

echo "Starting Redis and OpenSearch services..."
brew services start redis >/dev/null || true
brew services start opensearch >/dev/null || true

start_tika() {
  local port="$1"
  local xms="$2"
  local xmx="$3"
  local temp_subdir="$4"

  if lsof -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
    echo "Tika already running on port $port"
    return
  fi

  nohup java \
    -Xms"$xms" \
    -Xmx"$xmx" \
    -Djava.io.tmpdir="$ROOT_DIR/runtime/temp/$temp_subdir" \
    -jar "$TIKA_JAR" \
    --port "$port" \
    > "$ROOT_DIR/runtime/logs/tika-$port.log" 2>&1 &

  echo $! > "$ROOT_DIR/runtime/pids/tika-$port.pid"
  echo "Started Tika on port $port"
}

echo "Starting Tika instances..."
start_tika 9998 768m 768m tika1
start_tika 9999 768m 768m tika2
start_tika 10000 1g 1g tika3
start_tika 10001 1g 1g tika4

echo "Running health check..."
"$PYTHON_BIN" src/main.py check

echo "Initializing system..."
"$PYTHON_BIN" src/main.py init

if pgrep -f "src/main.py start" >/dev/null 2>&1; then
  echo "Orchestrator already running"
else
  echo "Starting orchestrator..."
  nohup "$PYTHON_BIN" src/main.py start > "$ROOT_DIR/runtime/logs/orchestrator_run.log" 2>&1 &
  echo $! > "$ROOT_DIR/runtime/pids/orchestrator.pid"
fi

if pgrep -f "streamlit run src/ui/dashboard.py" >/dev/null 2>&1; then
  echo "Dashboard already running"
else
  echo "Starting dashboard..."
  nohup "$PYTHON_BIN" -m streamlit run src/ui/dashboard.py --server.headless true --server.port 8501 > "$ROOT_DIR/runtime/logs/dashboard.log" 2>&1 &
  echo $! > "$ROOT_DIR/runtime/pids/dashboard.pid"
fi

echo
echo "System startup complete."
echo "Dashboard: http://localhost:8501"
echo "OpenSearch: http://localhost:9200"
echo "Logs: $ROOT_DIR/runtime/logs"
