import asyncio
import logging
import os
import sys
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.types import BotCommand

from config import BOT_TOKEN, SHOP_NAME
from database import init_db
from handlers import main_router

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("OptimusGangBot")

async def health_check(request):
    """Заглушка для Render и UptimeRobot."""
    return web.Response(text="Optimus Gang Bot is alive and running!")

async def start_dummy_server():
    """Запуск мини-вебсервера на порту, который выдает Render."""
    app = web.Application()
    app.router.add_get("/", health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    
    # Render автоматически передает нужный порт в переменную окружения PORT
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"🌐 Веб-сервер для Render запущен на порту {port}")

async def set_bot_commands(bot: Bot):
    """Установка подсказок команд в меню Telegram."""
    commands = [
        BotCommand(command="start", description="🏠 Главное меню"),
        BotCommand(command="duel", description="⚔️ Создать дуэль на ставку"),
        BotCommand(command="roulette", description="🎰 Запустить рулетку/игру"),
        BotCommand(command="list_game", description="📋 Запустить игру по списку"),
        BotCommand(command="profile", description="👤 Мой профиль и баланс"),
        BotCommand(command="shop", description="🛍 Магазин Optimus Gang"),
        BotCommand(command="bonus", description="🎁 Забрать ежедневный бонус"),
        BotCommand(command="top", description="🏆 Зал славы игроков"),
        BotCommand(command="admin", description="👑 Панель управления"),
        BotCommand(command="help", description="📖 Правила и справка")
    ]
    await bot.set_my_commands(commands)

async def main():
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN не указан в переменных окружения! Пожалуйста, добавьте токен бота.")
        return

    logger.info(f"🚀 Запуск бота для клуба и магазина «{SHOP_NAME}»...")

    # Запуск фонового веб-сервера для Render
    await start_dummy_server()

    # Инициализация базы данных SQLite
    await init_db()
    logger.info("📦 База данных SQLite успешно инициализирована.")

    # Создание экземпляра бота
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )

    dp = Dispatcher()
    dp.include_router(main_router)

    # Установка меню команд
    try:
        await set_bot_commands(bot)
    except Exception as e:
        logger.warning(f"Не удалось установить команды бота: {e}")

    # Удаление вебхука перед запуском поллинга
    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("✅ Бот успешно подключен к Telegram API и готов к игре!")

    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен.")
