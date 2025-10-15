import logging
import traceback

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .core.config import get_settings
from .routers import sessions


def _configure_logging(level_name: str) -> None:
    level = getattr(logging, level_name.upper(), logging.INFO)
    logging.getLogger().setLevel(level)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", __name__):
        logging.getLogger(name).setLevel(level)


def create_application() -> FastAPI:
    settings = get_settings()
    _configure_logging(settings.log_level)
    app = FastAPI(title="Voice Chess API")

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logging.error(f"Unhandled exception: {exc}")
        logging.error(traceback.format_exc())
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error"}
        )

    origins = []
    if settings.frontend_origin:
        origins.append(settings.frontend_origin)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins or ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(sessions.router)

    @app.get("/")
    async def health_check():
        return {"status": "healthy"}

    return app


app = create_application()
