# db/session.py
from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

def get_database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set")
    return url

# For a simple bot, a synchronous engine is fine.
engine = create_engine(
    get_database_url(),
    pool_pre_ping=True,  # helps avoid stale connections
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
