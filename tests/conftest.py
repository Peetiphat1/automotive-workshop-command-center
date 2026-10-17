"""
Shared pytest fixtures for the Automotive Workshop Command Center test suite.
Uses an in-memory SQLite database so tests never touch the real DB.
"""
from __future__ import annotations

import os

os.environ.setdefault("AUTO_BACKUP", "0")  # no background backups of the real database while testing

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.dependencies import get_db

# ── In-memory SQLite engine (isolated per test session) ──────────────────────
TEST_DB_URL = "sqlite:///:memory:"
engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session", autouse=True)
def create_tables():
    """Create all tables once for the test session."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def db():
    """Provide a fresh DB session per test, rolled back after each test."""
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture()
def client(db):
    """FastAPI TestClient with the DB session overridden."""
    # Import app here to avoid circular imports at collection time
    from main import app  # noqa: PLC0415

    def _override_get_db():
        try:
            yield db
        finally:
            pass

    from core.config import settings  # noqa: PLC0415

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app, raise_server_exceptions=True, headers={"X-API-Key": settings.MOCK_API_KEY}) as c:
        yield c
    app.dependency_overrides.clear()
