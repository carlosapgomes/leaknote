"""FastAPI application for the Leaknote admin UI."""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from bot.db import get_pool, close_pool
from leaknote.admin.dependencies import get_current_admin
from leaknote.admin import routes


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown."""
    # Startup
    await get_pool()
    yield
    # Shutdown
    await close_pool()


app = FastAPI(
    title="Leaknote Admin UI",
    description="Web-based admin interface for managing Leaknote records",
    version="1.0.0",
    lifespan=lifespan,
)

# Mount static files
app.mount("/static", StaticFiles(directory="leaknote/admin/static"), name="static")

# Configure templates
templates = Jinja2Templates(directory="leaknote/admin/templates")


# Include routes from routes.py
app.include_router(routes.router, dependencies=[Depends(get_current_admin)])


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def root_redirect(request: Request):
    """Redirect root to dashboard."""
    return RedirectResponse(url="/dashboard", status_code=307)
