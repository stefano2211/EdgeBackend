#!/bin/sh
set -e

# Strip SQLAlchemy driver prefix so asyncpg can parse the URL
CLEAN_URL=$(echo "$DATABASE_URL" | sed 's|postgresql+asyncpg://|postgresql://|')

echo "Waiting for database..."
for i in $(seq 1 30); do
    if python -c "import asyncpg, asyncio; asyncio.run(asyncpg.connect('$CLEAN_URL'))" 2>/dev/null; then
        echo "Database is ready"
        break
    fi
    echo "Database not ready yet, waiting... ($i/30)"
    sleep 2
done

echo "Pre-downloading embedding and reranker models..."
python -m backend.pre_download

echo "Creating database tables..."
python -m backend.init_db

echo "Starting application..."
exec uvicorn backend.main:app --host 0.0.0.0 --port 8000 --workers ${UVICORN_WORKERS:-1} --loop uvloop --http httptools
