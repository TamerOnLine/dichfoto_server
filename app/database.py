# app/database.py
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base
from .config import settings

DATABASE_URL = settings.DATABASE_URL

# Detect if SQLite is being used and set appropriate connection arguments
is_sqlite = DATABASE_URL.startswith("sqlite")
connect_args = {"check_same_thread": False} if is_sqlite else {}

# Create the database engine
engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,  # Verify connection before using
    future=True,
)


# Apply SQLite-specific PRAGMAs when a new connection is established
if is_sqlite:

    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_con, con_record):
        """
        Apply SQLite PRAGMAs to optimize performance and stability.

        Args:
            dbapi_con: The DB-API connection object.
            con_record: The SQLAlchemy connection record.
        """
        cur = dbapi_con.cursor()
        cur.execute("PRAGMA journal_mode=WAL;")     # Enable Write-Ahead Logging
        cur.execute("PRAGMA synchronous=NORMAL;")   # Balance between safety and performance
        cur.execute("PRAGMA busy_timeout=5000;")    # Wait 5s before 'database is locked' error
        cur.execute("PRAGMA cache_size=-20000;")    # ~20MB cache (negative means KB units)
        cur.close()


# Session factory for database interactions
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    future=True,
)

# Base class for ORM models
Base = declarative_base()
