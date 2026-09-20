import os
import pytest

@pytest.fixture(scope="session", autouse=True)
def configure_test_environment():
    """Ensure automated tests never call live external Gemini API
    and strictly run in 'test' database mode.
    """
    orig_key = os.environ.get("GEMINI_API_KEY")
    orig_env = os.environ.get("APP_ENV")
    os.environ["GEMINI_API_KEY"] = ""
    os.environ["DISABLE_LLM"] = "true"
    os.environ["APP_ENV"] = "test"
    from app.database import set_active_db_mode, clear_database
    set_active_db_mode("test")
    yield
    try:
        clear_database("test")
    except Exception:
        pass
    if orig_key is not None:
        os.environ["GEMINI_API_KEY"] = orig_key
    else:
        os.environ.pop("GEMINI_API_KEY", None)
    if orig_env is not None:
        os.environ["APP_ENV"] = orig_env
    else:
        os.environ.pop("APP_ENV", None)
    os.environ.pop("DISABLE_LLM", None)


