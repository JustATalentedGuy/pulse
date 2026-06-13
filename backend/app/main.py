import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import engine
from app.routers.bookmarks import router as bookmarks_router
from app.routers.digest import router as digest_router
from app.routers.feed import router as feed_router
from app.routers.jobs import router as jobs_router
from app.routers.quiz import router as quiz_router
from app.routers.phase8 import router as phase8_router
from app.routers.search import router as search_router
from app.routers.system import router as system_router
from app.scheduler.jobs import scheduler
from app.services.preferences import ensure_preference_row
from app.services.settings import ensure_user_settings_row


settings = get_settings()
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await ensure_preference_row()
    await ensure_user_settings_row()
    if settings.scheduler_enabled and not scheduler.running:
        scheduler.start()
    yield
    if scheduler.running:
        scheduler.shutdown(wait=False)
    await engine.dispose()


app = FastAPI(title="Pulse API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=(
        r"^https?://(localhost|127\.0\.0\.1|192\.168\.\d+\.\d+)(:\d+)?$"
    ),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(feed_router)
app.include_router(search_router)
app.include_router(bookmarks_router)
app.include_router(digest_router)
app.include_router(quiz_router)
app.include_router(phase8_router)
app.include_router(system_router)
app.include_router(jobs_router)
