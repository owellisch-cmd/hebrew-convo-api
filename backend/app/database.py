from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import settings


def _normalize(url: str) -> str:
    """Render (and Heroku) hand out `postgres://` URLs, which SQLAlchemy 2.x
    no longer recognizes as a dialect. Rewrite to the `postgresql://` form so
    the connection string can be pasted in exactly as the provider gives it."""
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql://", 1)
    return url


database_url = _normalize(settings.database_url)

connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}

# Free-tier Postgres closes idle connections; pre_ping discards dead ones
# instead of surfacing them as a 500 on the first request after a quiet spell.
engine_kwargs: dict = {"connect_args": connect_args}
if not database_url.startswith("sqlite"):
    engine_kwargs["pool_pre_ping"] = True
    engine_kwargs["pool_recycle"] = 300

engine = create_engine(database_url, **engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
