from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.routers.ai import router as ai_router
from app.routers.artifacts import router as artifacts_router
from app.routers.assumptions import router as assumptions_router
from app.routers.competitors import router as competitors_router
from app.routers.decisions import router as decisions_router
from app.routers.demo import router as demo_router
from app.routers.evals import router as evals_router
from app.routers.evidence import router as evidence_router
from app.routers.experiments import router as experiments_router
from app.routers.health import router as health_router
from app.routers.intake import router as intake_router
from app.routers.me import router as me_router
from app.routers.projects import router as projects_router
from app.routers.workflows import router as workflows_router


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        docs_url="/docs" if settings.environment != "production" else None,
        redoc_url="/redoc" if settings.environment != "production" else None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router)
    app.include_router(me_router)
    app.include_router(projects_router)
    app.include_router(intake_router)
    app.include_router(evidence_router)
    app.include_router(artifacts_router)
    app.include_router(competitors_router)
    app.include_router(assumptions_router)
    app.include_router(experiments_router)
    app.include_router(decisions_router)
    app.include_router(workflows_router)
    app.include_router(evals_router)
    app.include_router(demo_router)
    app.include_router(ai_router)

    return app


app = create_app()
