import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import settings
from app.database.database import check_database_connection

from app.routers.users import router as users_router
from app.routers.auth import router as auth_router
from app.routers.payments import router as payments_router
from app.routers.webhooks import router as webhooks_router


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Payments API")

    # Startup: verify database connectivity
    check_database_connection()

    logger.info("Database connection successful")

    yield

    # Shutdown: reserved for cleanup operations
    # We will add resource cleanup here when needed.

    logger.info("Shutting down Payments API")

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)
app.include_router(users_router)
app.include_router(auth_router)
app.include_router(payments_router)
app.include_router(webhooks_router)

@app.get("/")
def root():
    return {
        "application": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy"
    }