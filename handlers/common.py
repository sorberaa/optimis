from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command
from database import get_or_create_user
from keyboards.inline import main_menu_keyboard
from config import SHOP_NAME

router = Router()

@router.message(CommandStart())
async def cmd_start(message: Message):
    user = await get_or_create_user(
        user_id=message.from_user.id,
        username=message.from_user.username,
        full_name=message.from_user.full_name
    )

    text = (
        f"🔥 <b>Клуб {SHOP_NAME}</b>\n\n"
        f"👤 {message.from_user.mention_html()} | 💰 Баланс: <code>{user['balance']}</code> 🪙\n\n"
        f"Игровой аккаунт автоматически привязан к Telegram ID <code>{message.from_user.id}</code>.\n"
        f"Чат-игры, цифровой магазин и собственная коноплянка!\n"
        f"Выбирай действие ниже 👇"
    )
    await message.answer(text, reply_markup=main_menu_keyboard(), parse_mode="HTML")

@router.message(Command("help"))
async def cmd_help(message: Message):
    text = (
        f"📖 <b>Команды {SHOP_NAME}:</b>\n\n"
        f"• <code>/game</code> или <code>/roulette</code> — рулетка; после заполнения мест стартует админ\n"
        f"• <code>/list_game</code> — запустить игру по готовому списку\n"
        f"• <code>/duel</code> — дуэль 1 на 1\n"
        f"• <code>/hemp</code> — карточка коноплянки\n"
        f"• <code>/collect</code> — собрать листья\n"
        f"• <code>/plant</code> — посадить семя\n"
        f"• <code>/sell</code> — продать урожай\n"
        f"• <code>/shop</code> — магазин цифровых приколов\n"
        f"• <code>/profile</code> — профиль и баланс\n"
        f"• <code>/bonus</code> — забрать бонус дня\n"
        f"• <code>/top</code> — топ игроков"
    )
    await message.answer(text, parse_mode="HTML")

@router.callback_query(F.data == "help")
async def cb_help(callback: CallbackQuery):
    text = (
        f"📖 <b>Команды {SHOP_NAME}:</b>\n\n"
        f"• <code>/game</code> или <code>/roulette</code> — рулетка; после заполнения мест стартует админ\n"
        f"• <code>/list_game</code> — провести игру по готовому списку\n"
        f"• <code>/duel</code> — дуэль 1 на 1 в чате\n"
        f"• <code>/hemp</code> — карточка коноплянки\n"
        f"• <code>/shop</code> — магазин цифровых приколов\n"
        f"• <code>/bonus</code> — ежедневный бонус"
    )
    await callback.message.edit_text(text, reply_markup=main_menu_keyboard(), parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data == "back_main")
async def cb_back_main(callback: CallbackQuery):
    user = await get_or_create_user(
        user_id=callback.from_user.id,
        username=callback.from_user.username,
        full_name=callback.from_user.full_name
    )

    text = (
        f"🔥 <b>Клуб {SHOP_NAME}</b>\n\n"
        f"👤 {callback.from_user.mention_html()} | 💰 Баланс: <code>{user['balance']}</code> 🪙"
    )
    await callback.message.edit_text(text, reply_markup=main_menu_keyboard(), parse_mode="HTML")
    await callback.answer()
