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
    from sqlalchemy import text
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE inventory ADD COLUMN is_confirmed BOOLEAN DEFAULT 0"))
            conn.commit()
        except Exception:
            pass
        try:
            conn.execute(text("ALTER TABLE purchase_logs ADD COLUMN bill_id INTEGER"))
            conn.commit()
        except Exception:
            pass
        try:
            conn.execute(text("ALTER TABLE items ADD COLUMN is_grocery BOOLEAN DEFAULT 1"))
            conn.commit()
        except Exception:
            pass
        try:
            conn.execute(text("ALTER TABLE items ADD COLUMN default_unit_price FLOAT"))
            conn.commit()
        except Exception:
            pass
        try:
            conn.execute(text("ALTER TABLE grocery_list_entries ADD COLUMN is_dismissed BOOLEAN DEFAULT 0"))
            conn.commit()
        except Exception:
            pass
        try:
            conn.execute(text("ALTER TABLE inventory ADD COLUMN store_name VARCHAR(200)"))
            conn.commit()
        except Exception:
            pass
        try:
            conn.execute(text("ALTER TABLE inventory ADD COLUMN price FLOAT"))
            conn.commit()
        except Exception:
            pass


    session = SessionLocal()
    try:
        reconcile_repurchased_inventory(session, 1)
    except Exception:
        pass
    finally:
        session.close()
