from fastapi import FastAPI

from app.presentation.routes.health import router as health_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="NASCORP Construction API",
        version="0.1.0",
    )
    app.include_router(health_router, prefix="/v1")
    return app


app = create_app()