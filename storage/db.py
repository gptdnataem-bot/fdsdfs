from sqlalchemy import create_engine, Column, Integer, String, DateTime, UniqueConstraint
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime

engine = create_engine('sqlite:///storage/nxt.db', echo=False, future=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, future=True)
Base = declarative_base()

class Item(Base):
    __tablename__ = 'items'
    id = Column(Integer, primary_key=True)
    url = Column(String, nullable=False)
    title = Column(String, nullable=False)
    summary = Column(String, nullable=True)
    source = Column(String, nullable=True)
    image_url = Column(String, nullable=True)  # NEW
    status = Column(String, default="new")  # new, approved, posted, skipped
    scheduled_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint('url', name='uix_url'),)

def init_db():
    # naive migration to add new columns if needed
    from sqlalchemy import text
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE IF NOT EXISTS items (id INTEGER PRIMARY KEY, url VARCHAR NOT NULL, title VARCHAR NOT NULL, summary VARCHAR, source VARCHAR, image_url VARCHAR, status VARCHAR, scheduled_at DATETIME, created_at DATETIME);"))
        try:
            conn.execute(text("ALTER TABLE items ADD COLUMN image_url VARCHAR;"))
        except Exception:
            pass
        try:
            conn.execute(text("ALTER TABLE items ADD COLUMN status VARCHAR;"))
        except Exception:
            pass
        try:
            conn.execute(text("ALTER TABLE items ADD COLUMN scheduled_at DATETIME;"))
        except Exception:
            pass
        try:
            conn.execute(text("ALTER TABLE items ADD COLUMN created_at DATETIME;"))
        except Exception:
            pass
    Base.metadata.create_all(bind=engine)
