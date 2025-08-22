from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from .config import settings


# Determine if SQLite is being used, then configure connection arguments accordingly
connect_args = (
    {"check_same_thread": False}
    if settings.DATABASE_URL.startswith("sqlite")
    else {}
)

# Create the SQLAlchemy engine with the provided database URL
engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    future=True,
)

# Configure the session factory
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    future=True,
)

# Base class for all ORM models
Base = declarative_base()
