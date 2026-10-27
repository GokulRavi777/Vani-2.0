import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import (
    health_router,
    skills_router,
    assessments_router,
    stt_router,
    tts_router
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("vani_poc")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Vani 2.0 POC Backend started successfully on environment: %s", settings.ENVIRONMENT)
    logger.info("Supported skills: %s", ", ".join(settings.SUPPORTED_SKILLS))
    logger.info("Default STT mode configured: %s", settings.DEFAULT_STT_MODE)
    yield


app = FastAPI(
    title="Vani 2.0 POC — Assessment Engine",
    description="Stage 1: Application Skeleton and Assessment Generation",
    version="0.1.0",
    lifespan=lifespan
)

# CORS middleware for frontend communication (supports local dev + deployed Vercel domains)
cors_origins = settings.CORS_ORIGINS
allow_all = cors_origins == "*" or (isinstance(cors_origins, list) and "*" in cors_origins)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if allow_all else cors_origins,
    allow_origin_regex=r"^https:\/\/.*\.vercel\.app$" if not allow_all else None,
    allow_credentials=False if allow_all else True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Register routers
app.include_router(health_router)
app.include_router(skills_router)
app.include_router(assessments_router)
app.include_router(stt_router)
app.include_router(tts_router)
