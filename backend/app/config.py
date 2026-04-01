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
