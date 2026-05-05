"""
Configuration - reads settings from environment variables or .env file.

This file loads database URL, secret key, and media folder path. Create a .env
file in the backend folder with DB_HOST, DB_USER, DB_PASSWORD, DB_NAME, etc.
"""
import os
from dotenv import load_dotenv

load_dotenv()

def get_media_folder() -> str:
    """
    Return the folder where uploaded files (profile photos, documents) are stored.

    Uses MEDIA_FOLDER env var if set, otherwise defaults to frontend/src/media
    so the Angular app can serve them as static assets.
    """
    path = os.environ.get("MEDIA_FOLDER")
    if path and os.path.isdir(path):
        return os.path.abspath(path)
    # Anchor from this file: backend/config.py -> backend/ -> project root
    backend_root = _backend_root()
    project_root = os.path.dirname(backend_root)
    default = os.path.join(project_root, "frontend", "src", "media")
    return default


def _backend_root() -> str:
    return os.path.dirname(os.path.abspath(__file__))


def get_rag_chroma_path() -> str:
    """Persistent ChromaDB directory for the chatbot RAG index."""
    custom = (os.environ.get("RAG_CHROMA_PATH") or "").strip()
    if custom:
        return os.path.abspath(custom)
    return os.path.join(_backend_root(), "data", "chroma")


def get_rag_corpus_path() -> str:
    """Markdown corpus files to ingest into RAG (see rag_ingest)."""
    custom = (os.environ.get("RAG_CORPUS_PATH") or "").strip()
    if custom:
        return os.path.abspath(custom)
    return os.path.join(_backend_root(), "rag_corpus")


def get_db_url() -> str:
    """
    Build the MySQL connection URL from environment variables.

    Required in .env: DB_HOST, DB_USER, DB_PASSWORD, DB_NAME.
    Optional: DB_PORT (default 3306).
    """
    db_host = os.environ.get("DB_HOST", "localhost")
    db_user = os.environ.get("DB_USER", "root")
    db_password = os.environ.get("DB_PASSWORD", "")
    db_name = os.environ.get("DB_NAME", "csr_db")
    db_port = os.environ.get("DB_PORT", "3306")
    return f"mysql+mysqlconnector://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}?charset=utf8mb4"


class Config:
    """Flask app configuration - used by app.config.from_object(Config)."""
    # Secret key for signing sessions/tokens - must be changed in production
    SECRET_KEY = os.environ.get("SECRET_KEY", "change-me")
    # Database connection string (MySQL)
    SQLALCHEMY_DATABASE_URI = get_db_url()
    # Disable SQLAlchemy change tracking (not needed, saves memory)
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # Local Ollama (chatbot) — only localhost/private IPs are allowed in chatbot_routes
    OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434").strip().rstrip("/")
    OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "phi3:mini").strip()
    # Optional /api/generate options (smaller = less RAM; omit OLLAMA_NUM_CTX to use Ollama default)
    # Lower default = shorter, less chatty replies (raise in .env for long explanations)
    OLLAMA_NUM_PREDICT = int(os.environ.get("OLLAMA_NUM_PREDICT", "280"))
    _nc = os.environ.get("OLLAMA_NUM_CTX", "").strip()
    OLLAMA_NUM_CTX = int(_nc) if _nc.isdigit() else None
    _ot = os.environ.get("OLLAMA_TEMPERATURE", "0.2").strip()
    try:
        OLLAMA_TEMPERATURE = float(_ot)
    except ValueError:
        OLLAMA_TEMPERATURE = 0.2
    # Local RAG (ChromaDB) — no model training; retrieve doc chunks into the system prompt
    _rag = (os.environ.get("RAG_ENABLED") or "true").strip().lower()
    RAG_ENABLED = _rag in ("1", "true", "yes", "on")
    RAG_TOP_K = int(os.environ.get("RAG_TOP_K", "4"))
    RAG_CHROMA_PATH = get_rag_chroma_path()
    RAG_CORPUS_PATH = get_rag_corpus_path()
