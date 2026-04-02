"""
Application configuration — loaded from environment variables or .env file.
"""
import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Neo4j
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "password"

    # Qwen Colab endpoint (set after launching Colab notebook)
    QWEN_API_URL: str = ""

    # Flag to enable loading Qwen locally in the backend process
    ENABLE_LOCAL_QWEN: bool = True

    # Qwen model to load — Qwen2.5 real sizes: 0.5B, 1.5B, 3B, 7B, 32B (no 4B exists)
    # Use 7B for best quality on Colab T4 GPU, switch to 3B if you hit out-of-memory
    QWEN_MODEL_NAME: str = "Qwen/Qwen2.5-7B-Instruct"

    # Upload directory
    UPLOAD_DIR: str = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")

    # CORS origins
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()

# Ensure upload directory exists
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
