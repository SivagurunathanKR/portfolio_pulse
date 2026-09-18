import os
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase

# Resolve project root
BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BASE_DIR / ".env"
load_dotenv(dotenv_path=ENV_FILE, override=True)

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError(f"DATABASE_URL is not set. Looked for .env at: {ENV_FILE}")

# Ensure query parameters are cleanly stripped if any remain
if "?" in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.split("?")[0]

# Pass ssl='require' directly to the underlying asyncpg driver
engine = create_async_engine(
    DATABASE_URL,
    connect_args={"ssl": "require"},
    echo=True,
    pool_pre_ping=True
)

async_session_maker = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

class Base(DeclarativeBase):
    pass

async def get_db():
    async with async_session_maker() as session:
        yield session