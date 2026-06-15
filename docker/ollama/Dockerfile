FROM ollama/ollama:latest

# Expose Ollama port during build
ENV OLLAMA_HOST=0.0.0.0
ENV OLLAMA_PORT=11434

# Start ollama serve in the background, wait for it to be ready, pull the models, and stop the server
RUN ollama serve & \
    PID=$! && \
    sleep 5 && \
    echo "--- Pre-downloading Ollama models ---" && \
    ollama pull qwen3.5:9b && \
    ollama pull llama3.1:8b && \
    echo "--- Ollama models pre-download completed ---" && \
    kill $PID && \
    wait $PID || true
