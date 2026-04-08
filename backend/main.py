import logging
import os
import platform
import sys
import warnings
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from config.database import check_database_connection, get_database_status, init_db
from config.settings import settings
from routes import (
    auth_router,
    chat_router,
    code_router,
    compat_router,
    document_router,
    explain_router,
    image_router,
    learning_router,
    search_router,
    share_router,
    voice_router,
)
from services.ai_service import ai_service
from services.email_service import email_service
from services.rate_limit_service import rate_limit_service
from utils.warning_filters import configure_warning_filters


logger = logging.getLogger(__name__)
BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIST = BASE_DIR / "frontend" / "dist"
FRONTEND_INDEX = FRONTEND_DIST / "index.html"
DEV_SERVER_URL = "http://localhost:3000"
DEV_INDEX_HTML = f"""
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>NOVA AI</title>
    <script type="module" src="{DEV_SERVER_URL}/@vite/client"></script>
    <script type="module" src="{DEV_SERVER_URL}/src/main.jsx"></script>
  </head>
  <body>
    <div id="root"></div>
  </body>
</html>
"""
DEPLOYMENT_INDEX_HTML = """
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>NOVA AI API</title>
  </head>
  <body>
    <main style="font-family: Arial, sans-serif; max-width: 720px; margin: 4rem auto; padding: 0 1rem; line-height: 1.6;">
      <h1>NOVA AI backend is running</h1>
      <p>This deployment does not include a built frontend bundle.</p>
      <p>Use the API endpoints directly or deploy the React frontend separately.</p>
    </main>
  </body>
</html>
"""


def _configure_logging() -> None:
    root_logger = logging.getLogger()
    if not root_logger.handlers:
        logging.basicConfig(
            level=logging.DEBUG if settings.DEBUG else logging.INFO,
            format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        )
    else:
        root_logger.setLevel(logging.DEBUG if settings.DEBUG else logging.INFO)

    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("pymongo").setLevel(logging.WARNING)
    logging.getLogger("pymongo.serverSelection").setLevel(logging.WARNING)
    logging.getLogger("pymongo.topology").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(
        logging.INFO if settings.UVICORN_ACCESS_LOG else logging.WARNING
    )


def _configure_warnings() -> None:
    configure_warning_filters()


def _should_enable_reload() -> bool:
    if not settings.DEBUG:
        return False

    if sys.platform == "win32" and platform.architecture()[0] == "32bit":
        warnings.warn(
            (
                "Uvicorn reload is disabled on 32-bit Windows Python because the "
                "reload worker is unreliable in this environment. Use a 64-bit "
                "interpreter to restore hot reload."
            ),
            RuntimeWarning,
            stacklevel=2,
        )
        return False

    return True


def _should_serve_dev_frontend() -> bool:
    return settings.DEBUG and not os.getenv("RENDER")


@asynccontextmanager
async def lifespan(app: FastAPI):
    _configure_warnings()
    _configure_logging()
    logger.info("%s v%s starting", settings.APP_NAME, settings.APP_VERSION)
    db_ready = init_db()
    if db_ready:
        logger.info("Database connected: %s", settings.DATABASE_URL)
    else:
        logger.warning("Database unavailable during startup: %s", get_database_status())
    logger.info("CORS enabled for: %s", settings.cors_origins_list)
    yield
    await rate_limit_service.close()
    logger.info("%s shutting down", settings.APP_NAME)


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AI-powered chatbot platform with code generation, search, image, and learning assistance",
    redirect_slashes=False,
    lifespan=lifespan,
)

if (FRONTEND_DIST / "assets").exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(code_router)
app.include_router(document_router)
app.include_router(explain_router)
app.include_router(image_router)
app.include_router(learning_router)
app.include_router(voice_router)
app.include_router(compat_router)
app.include_router(search_router, prefix="/api")
app.include_router(share_router, prefix="/api")


@app.get("/", include_in_schema=False)
async def root():
    """Serve the NOVA AI UI."""
    if FRONTEND_INDEX.exists():
        return FileResponse(FRONTEND_INDEX, media_type="text/html")
    if _should_serve_dev_frontend():
        return HTMLResponse(content=DEV_INDEX_HTML)
    return HTMLResponse(content=DEPLOYMENT_INDEX_HTML)


@app.get("/api/status")
async def api_status():
    """API status endpoint."""
    ai_capabilities = ai_service.get_runtime_capabilities()
    email_capabilities = email_service.get_delivery_status()
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "message": "Welcome to NOVA AI - Your intelligent assistant platform",
        "capabilities": {
            "ai": ai_capabilities,
            "auth": {
                "email": email_capabilities,
                "email_ready": bool(email_capabilities.get("ready")),
            },
        },
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    db_status = get_database_status()
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "database": db_status,
    }


@app.get("/health/db")
async def health_db():
    """Database readiness endpoint."""
    check_database_connection(log_errors=False)
    db_status = get_database_status()
    status_code = 200 if db_status.get("available") else 503
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "healthy" if db_status.get("available") else "degraded",
            "database": db_status,
        },
    )


@app.get("/{full_path:path}", include_in_schema=False)
async def catch_all(full_path: str):
    """Serve the NOVA AI UI for all non-API routes."""
    if full_path.startswith("api"):
        return JSONResponse(status_code=404, content={"detail": "Not found"})
    if FRONTEND_INDEX.exists():
        return FileResponse(FRONTEND_INDEX, media_type="text/html")
    if _should_serve_dev_frontend():
        return HTMLResponse(content=DEV_INDEX_HTML)
    return JSONResponse(
        status_code=404,
        content={"detail": "Frontend build not found for this deployment."},
    )


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler."""
    logger.exception("Unhandled exception for path=%s", request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Something interrupted that request. Please try again.",
        },
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=_should_enable_reload(),
        access_log=settings.UVICORN_ACCESS_LOG,
    )
