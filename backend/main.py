<<<<<<< HEAD
from web_search import enhance_with_real_time_data, RealTimeDataProvider
=======
>>>>>>> 3520f8c8a820e9822841d33c9bb59a09576e92cf
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from config.settings import settings
from config.database import init_db
from routes import (
    auth_router,
    chat_router,
    code_router,
    explain_router,
    image_router,
    document_router,
    learning_router,
    voice_router,
    compat_router,
    search_router,
    share_router,
)

# Initialize FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AI-powered chatbot platform with code generation, document analysis, and learning assistance",
    redirect_slashes=False
)

# Paths
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

if (FRONTEND_DIST / "assets").exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(code_router)
app.include_router(explain_router)
app.include_router(image_router)
app.include_router(document_router)
app.include_router(learning_router)
app.include_router(voice_router)
app.include_router(compat_router)
app.include_router(search_router, prefix="/api")
app.include_router(share_router, prefix="/api")


@app.on_event("startup")
async def startup_event():
    """Initialize database on startup"""
    init_db()
    print(f"✅ {settings.APP_NAME} v{settings.APP_VERSION} started successfully!")
    print(f"📊 Database connected: {settings.DATABASE_URL.split('@')[-1]}")
    print(f"🔒 CORS enabled for: {settings.CORS_ORIGINS}")


@app.get("/", include_in_schema=False)
async def root():
    """Serve the NOVA AI UI"""
    if FRONTEND_INDEX.exists():
        return FileResponse(FRONTEND_INDEX, media_type="text/html")
    return HTMLResponse(content=DEV_INDEX_HTML)


@app.get("/api/status")
async def api_status():
    """API status endpoint (JSON)"""
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "message": "Welcome to NOVA AI - Your intelligent assistant platform"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION
    }


@app.get("/{full_path:path}", include_in_schema=False)
async def catch_all(full_path: str):
    """Serve the NOVA AI UI for all non-API routes"""
    if full_path.startswith("api"):
        return JSONResponse(status_code=404, content={"detail": "Not found"})
    if FRONTEND_INDEX.exists():
        return FileResponse(FRONTEND_INDEX, media_type="text/html")
    return HTMLResponse(content=DEV_INDEX_HTML)


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler"""
    return JSONResponse(
        status_code=500,
        content={
            "detail": "An internal server error occurred",
            "error": str(exc) if settings.DEBUG else "Internal server error"
        }
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG
    )
