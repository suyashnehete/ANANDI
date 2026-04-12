#!/bin/bash

echo "🚀 Starting ANANDI..."
echo ""

# Navigate to script directory so relative imports work
cd "$(dirname "$0")"

# Check if Ollama is installed
if ! command -v ollama &> /dev/null; then
    echo "❌ Ollama is not installed!"
    echo "📥 Install it with: brew install ollama"
    echo "Or visit: https://ollama.ai"
    exit 1
fi

# Check if Ollama is running
if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "⚠️  Ollama is not running. Starting it now..."
    ollama serve &
    sleep 3
fi

# Check if model is installed
if ! ollama list | grep -q "llama3.2:3b"; then
    echo "📦 Model not found. Pulling llama3.2:3b..."
    ollama pull llama3.2:3b
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
