
import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from .config import settings

# Lazy initialization - engine создается только при первом использовании
_engine = None
_SessionLocal = None

SKIP_DB = os.getenv("SKIP_DB", "false").lower() == "true"

def get_engine():
    """Получить engine, создавая его при необходимости (lazy initialization)"""
    global _engine
    if _engine is None and not SKIP_DB:
        DATABASE_URL = f"postgresql+asyncpg://{settings.DB_USER}:{settings.DB_PASSWORD}@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"
        _engine = create_async_engine(DATABASE_URL, echo=False, pool_pre_ping=True)
    return _engine

def get_session_local():
    """Получить SessionLocal, создавая его при необходимости"""
    global _SessionLocal
    if _SessionLocal is None:
        engine = get_engine()
        if engine is not None:
            _SessionLocal = async_sessionmaker(engine, expire_on_commit=False)
    return _SessionLocal

# Для обратной совместимости
engine = None  # Будет создан при первом вызове get_engine()
SessionLocal = None  # Будет создан при первом вызове get_session_local()

class Base(DeclarativeBase):
    pass
