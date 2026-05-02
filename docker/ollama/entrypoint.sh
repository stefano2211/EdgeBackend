#!/bin/sh
# Ollama entrypoint: pull model on first start if it doesn't exist

set -e

# Start ollama serve in background
ollama serve &
PID=$!

# Wait for ollama to be ready
sleep 5

# Pull the model if not present
MODEL_NAME=${OLLAMA_MODEL:-qwen3.5:9b}
echo "Pulling model: $MODEL_NAME"
ollama pull "$MODEL_NAME" || true

# Wait for the serve process
wait $PID
