"""FastAPI application entry point."""

import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import IntegrityError, OperationalError

from app.api.routes import (
    auth,
    catalog,
    compliance,
    defense,
    health,
    people,
    reports,
    review,
    theses,
    users,
)
from app.core.config import get_settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("thesis_management")
settings = get_settings()

app = FastAPI(
    title="Thesis Management API",
    description=(
        "Role-based platform for the undergraduate thesis and graduation process "
        "at Yachay Tech University."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

# Swagger UI loads its scripts from a CDN and runs inline code, so the strict policy is
# not applied to the documentation pages.
DOCS_PATHS = ("/docs", "/redoc", "/openapi.json")
CSP = (
    "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
    "frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    if not request.url.path.startswith(DOCS_PATHS):
        response.headers.setdefault("Content-Security-Policy", CSP)
    if settings.is_production:
        response.headers.setdefault(
            "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
        )
    if request.url.path.startswith("/api/"):
        response.headers.setdefault("Cache-Control", "no-store")
    return response


@app.exception_handler(IntegrityError)
def integrity_error_handler(_request: Request, exc: IntegrityError) -> JSONResponse:
    """A business rule enforced by the database (unique key, CHECK) was violated.
    The raw database message is logged, not returned, to avoid leaking schema details."""
    logger.warning("Integrity error: %s", exc.orig)
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": "The operation conflicts with existing data or a business rule"},
    )


@app.exception_handler(OperationalError)
def operational_error_handler(_request: Request, exc: OperationalError) -> JSONResponse:
    """MySQL error 1644 is raised by our own triggers (SIGNAL SQLSTATE '45000'), e.g.
    'A thesis cannot have more than 3 reviewers': that message is safe to show."""
    code = exc.orig.args[0] if exc.orig is not None and exc.orig.args else None
    if code == 1644:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT, content={"detail": exc.orig.args[1]}
        )
    logger.error("Database error: %s", exc.orig)
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": "The database is not available. Try again later."},
    )


@app.exception_handler(Exception)
def unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Log the details; never return a stack trace to the client."""
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


app.include_router(health.router)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(theses.router)
app.include_router(review.router)
app.include_router(compliance.router)
app.include_router(defense.router)
app.include_router(reports.router)
app.include_router(people.students)
app.include_router(people.professors)
app.include_router(catalog.router)


def mount_frontend(target: FastAPI, static_dir: Path) -> None:
    """Serve the built single-page app. Any non-API path returns index.html so that
    client-side routes (e.g. /theses/5) work on reload."""
    index = static_dir / "index.html"
    if (static_dir / "assets").is_dir():
        target.mount("/assets", StaticFiles(directory=static_dir / "assets"), name="assets")

    @target.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path.startswith("api/"):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
        candidate = (static_dir / path).resolve()
        # Real files at the root (favicon.svg); never outside static_dir.
        if path and candidate.is_file() and candidate.is_relative_to(static_dir.resolve()):
            return FileResponse(candidate)
        return FileResponse(index)


if settings.static_dir and (settings.static_dir / "index.html").is_file():
    mount_frontend(app, settings.static_dir)
