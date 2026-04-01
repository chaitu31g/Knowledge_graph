"""
Backend entry point for uvicorn.

Usage (from Knowledge_graph/ directory):
    uvicorn backend.main:app --host 0.0.0.0 --port 8000

This file adds the backend/ directory to sys.path so that
internal imports like 'from app.config import settings' work correctly.
"""
import sys
import os

# Add this file's directory (backend/) to sys.path
# so that 'from app.xxx import yyy' works
_backend_dir = os.path.dirname(os.path.abspath(__file__))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

# Re-export the FastAPI app instance
from app.main import app  # noqa: E402, F401
