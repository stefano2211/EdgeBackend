FROM python:3.13-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY src/integrations/docker/gmail-mcp/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy Gmail MCP server code
COPY src/integrations/custom_mcp_servers/gmail /app/gmail
COPY src/integrations/docker/gmail-mcp/entrypoint.py /app/entrypoint.py

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

EXPOSE 8080

CMD ["python", "/app/entrypoint.py"]
