from collections.abc import Generator

from sqlalchemy.orm import Session

from app.utils.db import get_db_session


def get_db() -> Generator[Session, None, None]:
    """Yield a database session for FastAPI request handlers."""
    db = get_db_session()
    try:
        yield db
    finally:
        db.close()
