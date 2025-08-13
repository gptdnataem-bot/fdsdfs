from sqlalchemy import create_engine, Column, Integer, String, DateTime, UniqueConstraint
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime

engine = create_engine('sqlite:///storage/nxt.db', echo=False, future=True, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, future=True)
Base = declarative_base()

class Item(Base):
    __tablename__ = 'items'
    id = Column(Integer, primary_key=True)
    url = Column(String, nullable=False, unique=True)
    title = Column(String, nullable=False)
    summary = Column(String, nullable=True)
    source = Column(String, nullable=True)
    image_url = Column(String, nullable=True)
    status = Column(String, default="new")  # new, approved, posted, skipped
    scheduled_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

def init_db():
    Base.metadata.create_all(bind=engine)
