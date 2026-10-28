"""
Database connection and session management using SQLModel and SQLite.
"""
from __future__ import annotations

import os
from typing import Generator
from sqlmodel import Session, SQLModel, create_engine

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../sovereign.db"))
SQLITE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    SQLITE_URL,
    connect_args={"check_same_thread": False},
    echo=False,
)


def init_db() -> None:
    """Initializes tables in SQLite database and enables WAL mode for high performance."""
    with engine.connect() as conn:
        conn.exec_driver_sql("PRAGMA journal_mode=WAL;")
        conn.exec_driver_sql("PRAGMA synchronous=NORMAL;")
    SQLModel.metadata.create_all(engine)
    with engine.connect() as conn:
        try:
            conn.exec_driver_sql("ALTER TABLE elections ADD COLUMN delivered_messages INTEGER DEFAULT 0;")
        except Exception:
            pass
        try:
            conn.exec_driver_sql("ALTER TABLE elections ADD COLUMN failed_to_dead_node INTEGER DEFAULT 0;")
        except Exception:
            pass


def get_session() -> Generator[Session, None, None]:
    """FastAPI dependency for database sessions."""
    with Session(engine) as session:
        yield session
