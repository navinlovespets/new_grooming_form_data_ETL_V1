import os
import logging
from logging.handlers import RotatingFileHandler
from sqlalchemy import create_engine
from urllib.parse import quote_plus

# -------------------------------
# Load .env file (if present) and Environment variables (read at import-time)
# -------------------------------

def _load_dotenv_file(dotenv_path=None):
    """Lightweight .env loader that sets variables only when not already set.

    This avoids adding a dependency on python-dotenv while allowing local
    development to work from a .env file placed next to this module.
    """
    dotenv_path = dotenv_path or os.path.join(os.path.dirname(__file__), ".env")
    if not os.path.exists(dotenv_path):
        return

    try:
        with open(dotenv_path, "r", encoding="utf-8") as fh:
            for raw in fh:
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                # Only set if not already present in environment
                os.environ.setdefault(key, val)
    except Exception:
        # Don't crash import if .env is malformed; callers will see meaningful errors later
        return


_load_dotenv_file()

ANALYTICS_DB_USER = os.getenv("ANALYTICS_DB_USER")
ANALYTICS_DB_PASSWORD = os.getenv("ANALYTICS_DB_PASSWORD")
ANALYTICS_DB_HOST = os.getenv("ANALYTICS_DB_HOST")
ANALYTICS_DB_PORT = os.getenv("ANALYTICS_DB_PORT")
ANALYTICS_DB_NAME = os.getenv("ANALYTICS_DB_NAME")

ST_DB_USER = os.getenv("ST_DB_USER")
ST_DB_PASSWORD = os.getenv("ST_DB_PASSWORD")
ST_DB_HOST = os.getenv("ST_DB_HOST")
ST_DB_PORT = os.getenv("ST_DB_PORT")
ST_DB_NAME = os.getenv("ST_DB_NAME")

# -------------------------------
# Google Sheets Configuration
# -------------------------------
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
WORKSHEET_NAME = os.getenv("WORKSHEET_NAME")
# Prefer explicit env var, but fall back to bundled service_account.json if available
SERVICE_ACCOUNT_FILE = os.getenv("SERVICE_ACCOUNT_FILE") or os.path.join(os.path.dirname(__file__), "service_account.json")
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# -------------------------------
# Lazy database engine creation
# -------------------------------
_analytics_engine = None
_st_engine = None


def get_analytics_engine():
    """Create and return the analytics SQLAlchemy engine.

    This function defers engine creation until it's actually needed, and
    provides a clear error when required configuration is missing.
    """
    global _analytics_engine
    if _analytics_engine is not None:
        return _analytics_engine

    required = [ANALYTICS_DB_USER, ANALYTICS_DB_PASSWORD, ANALYTICS_DB_HOST, ANALYTICS_DB_PORT, ANALYTICS_DB_NAME]
    if not all(required):
        raise RuntimeError(
            "Analytics DB configuration incomplete. Please set ANALYTICS_DB_USER, ANALYTICS_DB_PASSWORD, ANALYTICS_DB_HOST, ANALYTICS_DB_PORT, ANALYTICS_DB_NAME environment variables."
        )

    try:
        _analytics_engine = create_engine(
            f"mysql+pymysql://{ANALYTICS_DB_USER}:{quote_plus(ANALYTICS_DB_PASSWORD)}@{ANALYTICS_DB_HOST}:{int(ANALYTICS_DB_PORT)}/{ANALYTICS_DB_NAME}",
            pool_pre_ping=True,
            echo=False,
        )
        return _analytics_engine
    except Exception:
        # Re-raise so callers see the original error/traceback
        raise


def get_st_engine():
    """Create and return the staging SQLAlchemy engine.

    Defers engine creation and validates configuration first.
    """
    global _st_engine
    if _st_engine is not None:
        return _st_engine

    required = [ST_DB_USER, ST_DB_PASSWORD, ST_DB_HOST, ST_DB_PORT, ST_DB_NAME]
    if not all(required):
        raise RuntimeError(
            "Staging DB configuration incomplete. Please set ST_DB_USER, ST_DB_PASSWORD, ST_DB_HOST, ST_DB_PORT, ST_DB_NAME environment variables."
        )

    try:
        _st_engine = create_engine(
            f"mysql+pymysql://{ST_DB_USER}:{quote_plus(ST_DB_PASSWORD)}@{ST_DB_HOST}:{int(ST_DB_PORT)}/{ST_DB_NAME}",
            pool_pre_ping=True,
            echo=False,
        )
        return _st_engine
    except Exception:
        raise

# -------------------------------
# Logging Setup
# -------------------------------

def setup_logging(log_dir="logs", log_file="app.log", level=logging.INFO):
    """Configure logging to console and rotating file."""
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, log_file)

    logger = logging.getLogger()
    logger.setLevel(level)

    # Remove existing handlers to avoid duplicates
    if logger.hasHandlers():
        logger.handlers.clear()

    # Console handler
    console = logging.StreamHandler()
    console.setLevel(level)
    console_format = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    console.setFormatter(console_format)
    logger.addHandler(console)

    # File handler (rotating)
    file_handler = RotatingFileHandler(log_path, maxBytes=10*1024*1024, backupCount=5)
    file_handler.setLevel(level)
    file_handler.setFormatter(console_format)
    logger.addHandler(file_handler)

    # Optionally add Google Sheets handler (appends individual log records to 'logs').
    # Disabled by default — set SHEETS_LOGS_VERBOSE=true to enable per-record logging to Sheets.
    try:
        if os.getenv("SHEETS_LOGS_VERBOSE", "false").lower() in ("1", "true", "yes"):
            # Import lazily to avoid circular imports at module import time
            from gsheets_logger import GoogleSheetHandler

            gs_handler = GoogleSheetHandler(spreadsheet_id=SPREADSHEET_ID, service_account_file=SERVICE_ACCOUNT_FILE, scopes=SCOPES, worksheet_name="logs")
            if gs_handler.enabled:
                gs_handler.setLevel(level)
                # Use same formatter but keep message compact
                gs_handler.setFormatter(console_format)
                logger.addHandler(gs_handler)
    except Exception:
        # If anything fails, continue without Google Sheets logging
        pass

    return logger