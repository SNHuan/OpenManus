"""Main FastAPI application for OpenManus project."""

import os
import sys
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

from app.logger import logger
from app.settings import settings
from app.database.init import setup_database, setup_event_system, cleanup
from app.api.routes import auth, users, conversations, events, websocket

# Windows兼容性设置 - 解决Playwright的asyncio问题
if sys.platform == "win32":
    try:
        # 在Windows下，使用SelectorEventLoopPolicy来兼容Playwright
        # 这避免了ProactorEventLoopPolicy的子进程限制
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        logger.info("Windows SelectorEventLoopPolicy已设置（兼容Playwright）")
    except Exception as e:
        logger.warning(f"设置Windows事件循环策略失败: {e}")
        # 如果SelectorEventLoopPolicy不可用，尝试使用默认策略
        try:
            asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())
            logger.info("使用默认事件循环策略作为备选")
        except Exception as e2:
            logger.warning(f"设置默认事件循环策略也失败: {e2}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting OpenManus API server...")

    try:
        # Initialize database
        await setup_database()

        # Initialize event system
        await setup_event_system()

        logger.info("OpenManus API server started successfully")

    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        raise

    yield

    # Shutdown
    logger.info("Shutting down OpenManus API server...")
    try:
        # Clean up browser resources
        from app.tool.browser_executor import cleanup_browser_executor
        await cleanup_browser_executor()

        # Clean up Crawl4AI resources
        try:
            from app.tool.crawl4ai_tool import get_crawl4ai_executor
            executor = get_crawl4ai_executor()
            executor.cleanup()
            logger.info("Crawl4AI executor cleaned up")
        except Exception as e:
            logger.warning(f"Crawl4AI cleanup warning: {e}")

        # Clean up other resources
        await cleanup()
        logger.info("OpenManus API server shutdown complete")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")


# Create FastAPI application
app = FastAPI(
    title="OpenManus API",
    description="Multi-user conversation system with event-driven architecture",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler for unhandled errors."""
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "Internal server error",
            "detail": "An unexpected error occurred"
        }
    )


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "OpenManus API",
        "version": "1.0.0"
    }


# API status endpoint
@app.get("/status")
async def api_status():
    """API status endpoint with system information."""
    from app.event.manager import event_manager

    try:
        # Get event system stats
        event_stats = event_manager.get_stats()

        return {
            "status": "operational",
            "service": "OpenManus API",
            "version": "1.0.0",
            "event_system": {
                "initialized": event_manager._initialized,
                "stats": event_stats
            }
        }
    except Exception as e:
        logger.error(f"Status check error: {e}")
        return {
            "status": "degraded",
            "service": "OpenManus API",
            "version": "1.0.0",
            "error": str(e)
        }


# Include routers
app.include_router(auth.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(conversations.router, prefix="/api/v1")
app.include_router(events.router, prefix="/api/v1")
app.include_router(websocket.router, prefix="/api/v1")


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Welcome to OpenManus API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
        "status": "/status"
    }


if __name__ == "__main__":
    import uvicorn

    # Get configuration from environment
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    debug = os.getenv("DEBUG", "false").lower() == "true"

    # Run the application
    uvicorn.run(
        "app.api.main:app",
        host=host,
        port=port,
        reload=debug,
        log_level="info"
    )
