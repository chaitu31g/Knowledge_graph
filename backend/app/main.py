"""
FastAPI Application Entry Point

Knowledge Graph Datasheet System — Backend API
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import upload, query
from app.services.graph_builder import graph_builder

# ── Logging ─────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ── Lifespan ────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    logger.info("Starting Knowledge Graph Datasheet System")
    graph_builder.connect()
    graph_builder.create_constraints()
    logger.info("Neo4j connected and constraints created")
    yield
    graph_builder.close()
    logger.info("Neo4j connection closed")


# ── App ─────────────────────────────────────────────────────────────

app = FastAPI(
    title="Knowledge Graph Datasheet API",
    description="AI-powered semiconductor datasheet query system using Neo4j Knowledge Graph",
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS ────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ─────────────────────────────────────────────────────────

app.include_router(upload.router)
app.include_router(query.router)


# ── Health Check ────────────────────────────────────────────────────

@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "service": "Knowledge Graph Datasheet API",
        "neo4j_uri": settings.NEO4J_URI,
        "qwen_configured": bool(settings.QWEN_API_URL),
    }
