from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine, AsyncSession, async_sessionmaker
from sqlalchemy import pool, event
from sqlmodel import SQLModel

from ogi.config import settings

# Import all models so SQLModel.metadata knows about them for create_all
import ogi.models.project  # noqa: F401
import ogi.models.entity  # noqa: F401
import ogi.models.edge  # noqa: F401
import ogi.models.auth  # noqa: F401
import ogi.models.transform  # noqa: F401
import ogi.models.api_key  # noqa: F401
import ogi.models.plugin  # noqa: F401
import ogi.models.user_plugin_preference  # noqa: F401
import ogi.models.transform_settings  # noqa: F401
import ogi.models.billing  # noqa: F401
import ogi.models.eventing  # noqa: F401
import ogi.models.telemetry  # noqa: F401
import ogi.agent.models  # noqa: F401
import ogi.agent.settings_models  # noqa: F401

engine: AsyncEngine | None = None
async_session_maker: async_sessionmaker[AsyncSession] | None = None

async def init_db() -> None:
    global engine, async_session_maker

    if settings.use_sqlite:
        if settings.database_path == ":memory:":
            db_url = "sqlite+aiosqlite:///:memory:"
        else:
            db_url = f"sqlite+aiosqlite:///{settings.abs_database_path}"
        engine = create_async_engine(db_url, echo=False)        
        
        @event.listens_for(engine.sync_engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
    else:
        db_url = settings.database_url
        if db_url and db_url.startswith("postgresql://"):
            db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
            
            # asyncpg does not support all the connection pooling query arguments
            # that Supabase provides by default (like ?pgbouncer=true)
            if "?" in db_url:
                base, query = db_url.split("?", 1)
                params = [p for p in query.split("&") if not p.startswith("pgbouncer=")]
                if params:
                    db_url = f"{base}?{'&'.join(params)}"
                else:
                    db_url = base

        import uuid
        engine = create_async_engine(
            db_url,
            echo=False,
            poolclass=pool.NullPool,
            connect_args={
                "prepared_statement_name_func": lambda: f"__asyncpg_{uuid.uuid4()}__",
                "prepared_statement_cache_size": 0,  # Required for PgBouncer/Supabase pooler
                "statement_cache_size": 0
            }
        )

    # SQLite remains lightweight and self-bootstrapping for tests/local mode.
    # PostgreSQL schema evolution is handled by Alembic during startup/deploy.
    if settings.use_sqlite:
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)

    async_session_maker = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    # In local/no-auth mode, ensure the anonymous profile exists in the DB so FK constraints are not violated.
    if not settings.supabase_url or not settings.supabase_anon_key:
        from ogi.models.auth import UserProfile
        import uuid
        async with async_session_maker() as session:
            anon_id = uuid.UUID("00000000-0000-0000-0000-000000000000")
            profile = await session.get(UserProfile, anon_id)
            if not profile:
                profile = UserProfile(id=anon_id, email="local@localhost")
                session.add(profile)
                try:
                    await session.commit()
                except Exception:
                    await session.rollback()


async def close_db() -> None:
    global engine
    if engine is not None:
        await engine.dispose()
        engine = None


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    if async_session_maker is None:
        raise RuntimeError("Database not initialized")
    async with async_session_maker() as session:
        yield session
