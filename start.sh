#!/bin/bash

echo "🚀 Starting ANANDI..."
echo ""

# Navigate to script directory so relative imports work
cd "$(dirname "$0")"

# ── Docker mode ──────────────────────────────────────────────────────────────
if [ "$1" = "--docker" ]; then
    echo "🐳 Starting infrastructure via Docker Compose..."
    docker compose up -d ollama chromadb
    echo ""
    echo "⏳ Waiting for Ollama to be healthy..."
    until curl -sf http://localhost:11434/api/tags > /dev/null 2>&1; do sleep 2; done
    echo "✅ Ollama is ready"

    # Pull models if needed
    if ! docker compose exec -T ollama ollama list 2>/dev/null | grep -q "llama3.2:3b"; then
        echo "📦 Pulling llama3.2:3b..."
        docker compose exec -T ollama ollama pull llama3.2:3b
    fi
    if ! docker compose exec -T ollama ollama list 2>/dev/null | grep -q "nomic-embed-text"; then
        echo "📦 Pulling nomic-embed-text..."
        docker compose exec -T ollama ollama pull nomic-embed-text
    fi

    export OLLAMA_BASE_URL=http://localhost:11434
    export CHROMA_SERVER_URL=http://localhost:8000
    echo "✅ Docker services ready"
    echo ""
    shift  # remove --docker from args
fi

# ── Native Ollama check (skip if Docker mode set the env) ────────────────────
if [ -z "$OLLAMA_BASE_URL" ]; then
    # Check if Ollama is installed
    if ! command -v ollama &> /dev/null; then
        echo "❌ Ollama is not installed!"
        echo "📥 Install it with: brew install ollama"
        echo "Or visit: https://ollama.ai"
        echo "Or use: ./start.sh --docker"
        exit 1
    fi

    # Check if Ollama is running
    if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
        echo "⚠️  Ollama is not running. Starting it now..."
        ollama serve &
        sleep 3
    fi

    # Check if models are installed
    if ! ollama list | grep -q "llama3.2:3b"; then
        echo "📦 Model not found. Pulling llama3.2:3b..."
        ollama pull llama3.2:3b
    fi
    if ! ollama list | grep -q "nomic-embed-text"; then
        echo "📦 Embedding model not found. Pulling nomic-embed-text..."
        ollama pull nomic-embed-text
    fi
fi

# Check if Python 3 is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed!"
    echo "📥 Install it from: https://www.python.org"
    exit 1
fi

# Create venv if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "📦 Creating Python virtual environment..."
    python3 -m venv .venv
fi

# Activate venv
source .venv/bin/activate

# Install dependencies if needed
if ! python3 -c "import webview" &> /dev/null 2>&1; then
    echo "📦 Installing Python dependencies..."
    pip install --upgrade pip -q
    pip install -r requirements.txt
fi

echo "✅ Everything ready!"
echo "🎉 Launching ANANDI..."
echo ""

python3 app.py "$@"
