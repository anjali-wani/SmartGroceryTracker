import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from dotenv import load_dotenv

# Base directory for SmartGroceryTracker
PROJECT_ROOT = Path(__file__).resolve().parent.parent

load_dotenv(PROJECT_ROOT / '.env')

DEFAULT_DB_PATH = (PROJECT_ROOT / 'grocery_tracker.db').resolve()
DATABASE_URL = os.getenv('DATABASE_URL', f'sqlite:///{DEFAULT_DB_PATH}')

# If it is a relative sqlite URL, resolve it against PROJECT_ROOT
if DATABASE_URL.startswith('sqlite:///') and not DATABASE_URL.startswith('sqlite:////'):
    relative_path = DATABASE_URL.replace('sqlite:///', '')
    if not os.path.isabs(relative_path):
        resolved = (PROJECT_ROOT / relative_path).resolve()
        DATABASE_URL = f'sqlite:///{resolved}'

connect_args = {}
if DATABASE_URL.startswith('sqlite'):
    connect_args = {'check_same_thread': False}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    echo=False
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    import app.models
    Base.metadata.create_all(bind=engine)
