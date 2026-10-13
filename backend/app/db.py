from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from .config import settings
from .models import Base


def _engine_url(url: str) -> str:
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+asyncpg://" + url[len(prefix):]
    return url


DATABASE_URL = _engine_url(settings.database_url)
IS_POSTGRES = DATABASE_URL.startswith("postgresql+asyncpg://")

# Serverless + Supabase pooler: no client-side pool and no cached prepared statements.
engine = (create_async_engine(DATABASE_URL, poolclass=NullPool,
                              connect_args={"statement_cache_size": 0})
          if IS_POSTGRES else create_async_engine(DATABASE_URL))
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_add_missing_columns)
        if IS_POSTGRES:
            # Tables live in Supabase's exposed `public` schema: RLS with no policies
            # blocks the anon/authenticated Data API roles; the backend owns the tables.
            for table in Base.metadata.sorted_tables:
                await conn.execute(text(f"ALTER TABLE {table.name} ENABLE ROW LEVEL SECURITY"))


def _add_missing_columns(conn) -> None:
    insp = inspect(conn)
    for table in Base.metadata.sorted_tables:
        have = {c["name"] for c in insp.get_columns(table.name)}
        for col in table.columns:
            if col.name not in have:
                conn.execute(text(
                    f"ALTER TABLE {table.name} ADD COLUMN {col.name} {col.type.compile(conn.dialect)}"))


async def get_db():
    async with SessionLocal() as session:
        yield session
