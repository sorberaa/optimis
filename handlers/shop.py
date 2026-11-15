from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from config import SHOP_NAME
from database import get_or_create_user, get_shop_items, get_shop_item, buy_item, get_user_badge
from keyboards.inline import shop_keyboard, back_to_menu_keyboard

router = Router()

@router.message(Command("shop"))
async def cmd_shop(message: Message):
    user = await get_or_create_user(message.from_user.id, message.from_user.username, message.from_user.full_name)
    badge = await get_user_badge(message.from_user.id)
    badge_str = f" | Ник: <b>{badge}</b>" if badge else ""

    items = await get_shop_items()
    text = (
        f"🛍 <b>Магазин стикеров и титулов {SHOP_NAME}</b>\n\n"
        f"💰 Баланс: <code>{user['balance']}</code> 🪙{badge_str}\n"
        f"Купленный статус отображается рядом с вашим ником во всех играх и рулетках!"
    )
    await message.answer(text, reply_markup=shop_keyboard(items), parse_mode="HTML")

@router.callback_query(F.data == "shop")
async def cb_shop(callback: CallbackQuery):
    user = await get_or_create_user(callback.from_user.id, callback.from_user.username, callback.from_user.full_name)
    badge = await get_user_badge(callback.from_user.id)
    badge_str = f" | Ник: <b>{badge}</b>" if badge else ""

    items = await get_shop_items()
    text = (
        f"🛍 <b>Магазин стикеров и титулов {SHOP_NAME}</b>\n\n"
        f"💰 Баланс: <code>{user['balance']}</code> 🪙{badge_str}\n"
        f"Купленный статус отображается рядом с вашим ником во всех играх и рулетках!"
    )
    await callback.message.edit_text(text, reply_markup=shop_keyboard(items), parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data.startswith("shop_buy:"))
async def cb_shop_buy(callback: CallbackQuery):
    item_id = int(callback.data.split(":")[1])
    item = await get_shop_item(item_id)

    if not item:
        await callback.answer("❌ Товар не найден!", show_alert=True)
        return

    success, msg, purchased_item = await buy_item(callback.from_user.id, item_id)
    if not success:
        await callback.answer(msg, show_alert=True)
        return

    text = (
        f"🎉 <b>Статус успешно установлен!</b>\n\n"
        f"🏷 Ваш новый титул: <b>{purchased_item['content']}</b>\n"
        f"💸 Списано: <code>{purchased_item['price']}</code> 🪙\n\n"
        f"Теперь он красуется возле вашего ника во всех турнирах и рулетках чата!"
    )
    await callback.message.edit_text(text, reply_markup=back_to_menu_keyboard(), parse_mode="HTML")
    await callback.answer("Титул установлен!")

@router.callback_query(F.data == "my_purchases")
async def cb_my_purchases(callback: CallbackQuery):
    badge = await get_user_badge(callback.from_user.id)
    status_text = f"Текущий титул в играх: <b>{badge}</b>" if badge else "У вас пока нет активного титула."

    text = (
        f"🎒 <b>Ваш статус {SHOP_NAME}:</b>\n\n"
        f"{status_text}\n\n"
        f"Купите новые приколы к нику в магазине за монеты!"
    )
    await callback.message.edit_text(text, reply_markup=back_to_menu_keyboard(), parse_mode="HTML")
    await callback.answer()
