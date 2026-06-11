from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine

from backend.database_connector.models import DatabaseConnection
from backend.integrations.credential_vault import CredentialVault

DRIVERS = {
    "postgresql": "postgresql+asyncpg",
    "mysql": "mysql+aiomysql",
}

DEFAULT_PORTS = {
    "postgresql": 5432,
    "mysql": 3306,
}


class EngineFactory:
    _engines: dict[str, tuple[AsyncEngine, datetime]] = {}
    _ttl = timedelta(minutes=30)
    _vault = CredentialVault()

    @classmethod
    async def get_engine(cls, connection: DatabaseConnection) -> AsyncEngine:
        cache_key = connection.id
        now = datetime.now(timezone.utc).replace(tzinfo=None)

        if cache_key in cls._engines:
            engine, created = cls._engines[cache_key]
            if now - created < cls._ttl:
                return engine
            await engine.dispose()
            del cls._engines[cache_key]

        driver = DRIVERS[connection.db_type]
        creds = connection.credentials
        if not creds:
            raise ValueError("Connection has no credentials")

        username = cls._vault.decrypt(creds.encrypted_username)
        password = cls._vault.decrypt(creds.encrypted_password)

        # Build URL: dialect+driver://user:pass@host:port/dbname
        database_url = (
            f"{driver}://{username}:{password}"
            f"@{connection.host}:{connection.port}/{connection.database_name}"
        )

        engine = create_async_engine(
            database_url,
            pool_pre_ping=True,
            pool_recycle=1800,
            echo=False,
        )
        cls._engines[cache_key] = (engine, now)
        return engine

    @classmethod
    async def dispose_engine(cls, connection_id: str) -> None:
        if connection_id in cls._engines:
            engine, _ = cls._engines[connection_id]
            await engine.dispose()
            del cls._engines[connection_id]

    @classmethod
    async def test_connection(cls, connection: DatabaseConnection) -> bool:
        from sqlalchemy import text
        try:
            engine = await cls.get_engine(connection)
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return True
        except Exception:
            return False
