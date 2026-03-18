import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# make sure data folder exists
os.makedirs("data", exist_ok=True)

DATABASE_URL = "sqlite:///./data/nova_ai.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()    


def get_db():
    """Database dependency for FastAPI"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database tables"""
    Base.metadata.create_all(bind=engine)
