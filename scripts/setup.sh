#!/bin/bash
set -e

echo "🚀 Starting ZeroDay PS2 Setup..."

# 1. Environment Variables
echo "📝 Setting up environment..."
cat <<EOF > .env
NEXT_TELEMETRY_DISABLED=1
LANGCHAIN_TRACING_V2=false
OLLAMA_MODEL=gemma:e4b
OLLAMA_BASE_URL=http://127.0.0.1:11434
EOF

# 2. Ollama Model Pull
if command -v ollama &> /dev/null; then
    echo "📦 Pulling Ollama model..."
    ollama pull gemma:e4b
else
    echo "❌ Ollama not found. Please install it from ollama.com"
    exit 1
fi

# 3. Backend Setup (Python 3.11+)
echo "🐍 Setting up Python environment..."
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install fastapi uvicorn langgraph langchain-community ollama pydantic PyPDF2 chromadb

# 4. Frontend Setup (Next.js)
echo "🌐 Setting up Next.js project..."
cd apps/web
npx create-next-app@latest . --ts --tailwind --eslint --app --src-dir=false --import-alias="@/*" --use-npm
cd ../..

echo "✅ Setup complete! Run 'source venv/bin/activate' and start developing."
