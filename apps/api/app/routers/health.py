from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.config import Settings, get_settings

router = APIRouter(tags=["system"])
SettingsDep = Annotated[Settings, Depends(get_settings)]


@router.get("/health")
def healthcheck(settings: SettingsDep) -> dict[str, str]:
    return {
        "status": "ok",
        "service": settings.app_name,
        "environment": settings.environment,
    }
