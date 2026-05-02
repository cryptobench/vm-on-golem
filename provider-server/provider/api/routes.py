from fastapi import APIRouter

from . import admin_routes, payments_routes, provider_routes, summary_routes, vm_routes

router = APIRouter()
router.include_router(vm_routes.router)
router.include_router(provider_routes.router)
router.include_router(payments_routes.router)
router.include_router(summary_routes.router)
router.include_router(admin_routes.router)
