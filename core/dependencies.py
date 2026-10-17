from typing import Generator

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from core.config import settings
from core.database import SessionLocal


# ── Database session dependency ───────────────────────────────────────────────
def get_db() -> Generator[Session, None, None]:
    """Yield a SQLAlchemy session and guarantee cleanup."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── API-Key guard (mock — swap for OAuth2 / JWT in production) ────────────────
def verify_api_key(x_api_key: str = Header(default="")) -> str:
    """Simple header-based API key check. Returns the key if valid."""
    if settings.REQUIRE_PASSWORD and x_api_key != settings.MOCK_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-API-Key header.",
        )
    return x_api_key


# ── Common typed dependencies ─────────────────────────────────────────────────
DBSession = Depends(get_db)
APIKey = Depends(verify_api_key)
