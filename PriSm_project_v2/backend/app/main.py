from fastapi import FastAPI
from app.api.routes import router
from app.core.config import settings
from app.core.logging_config import setup_logging

setup_logging(settings.LOG_LEVEL)

app = FastAPI(title=settings.APP_NAME)
app.include_router(router)
