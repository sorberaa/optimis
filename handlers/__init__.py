from aiogram import Router
from .common import router as common_router
from .games import router as games_router
from .profile import router as profile_router
from .shop import router as shop_router
from .admin import router as admin_router
from .roulette import router as roulette_router

main_router = Router()
main_router.include_router(common_router)
main_router.include_router(games_router)
main_router.include_router(profile_router)
main_router.include_router(shop_router)
main_router.include_router(admin_router)
main_router.include_router(roulette_router)

__all__ = ["main_router"]
