#!/usr/bin/env bash
set -e

echo "[start] waiting for database to become reachable..."

python - <<'PY'
import asyncio, os, sys, time, re

async def wait():
    from app.core.config import settings
    url = settings.DATABASE_URL
    if url.startswith("postgresql+asyncpg://"):
        async_url = url
    elif url.startswith("postgresql://"):
        async_url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgres://"):
        async_url = url.replace("postgres://", "postgresql+asyncpg://", 1)
    else:
        async_url = url

    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy import text

    deadline = time.time() + 180  # 3 minutes
    delay = 1.0
    last_err = None
    while time.time() < deadline:
        engine = create_async_engine(async_url, pool_pre_ping=True)
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            await engine.dispose()
            print("[start] database is reachable", flush=True)
            return
        except Exception as e:
            last_err = e
            await engine.dispose()
            print(f"[start] db not ready ({e.__class__.__name__}); retrying in {delay:.1f}s", flush=True)
            await asyncio.sleep(delay)
            delay = min(delay * 1.5, 10.0)
    print(f"[start] gave up waiting for database: {last_err}", file=sys.stderr, flush=True)
    sys.exit(1)

asyncio.run(wait())
PY

echo "[start] running alembic migrations..."
alembic upgrade head

echo "[start] seeding community libraries (idempotent)..."
python scripts/seed.py           || echo "[start] seed.py failed (non-fatal)"
python scripts/seed_therapies.py || echo "[start] seed_therapies.py failed (non-fatal)"
python seed_pranayama.py         || echo "[start] seed_pranayama.py failed (non-fatal)"

echo "[start] launching uvicorn on port ${PORT:-8747}"
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8747}"
