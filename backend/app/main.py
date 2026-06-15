from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import expert, kb, parse, report, review
from app.config import get_settings


def create_app() -> FastAPI:
    """Create the FastAPI application."""

    settings = get_settings()
    app = FastAPI(title=settings.app_name, version="0.1.0", debug=settings.debug)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(parse.router, prefix=f"{settings.api_v1_prefix}/parse", tags=["parse"])
    app.include_router(review.router, prefix=f"{settings.api_v1_prefix}/review", tags=["review"])
    app.include_router(kb.router, prefix=f"{settings.api_v1_prefix}/kb", tags=["knowledge-base"])
    app.include_router(expert.router, prefix=f"{settings.api_v1_prefix}/expert", tags=["expert"])
    app.include_router(report.router, prefix=f"{settings.api_v1_prefix}/report", tags=["report"])

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": "smart-review-backend"}

    return app


app = create_app()
