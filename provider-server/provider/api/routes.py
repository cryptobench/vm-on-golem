from fastapi import APIRouter

from . import (
    admin_routes,
    live_routes,
    monitoring_routes,
    payments_routes,
    provider_routes,
    settings_routes,
    summary_routes,
    vm_routes,
)

router = APIRouter()
router.include_router(vm_routes.router)
router.include_router(provider_routes.router)
router.include_router(settings_routes.router)
router.include_router(payments_routes.router)
router.include_router(summary_routes.router)
router.include_router(monitoring_routes.router)
router.include_router(admin_routes.router)
router.include_router(live_routes.router)
