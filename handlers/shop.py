from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from config import SHOP_NAME
from database import (
    get_or_create_user,
    get_shop_items,
    buy_item,
    get_user_decorations,
    get_user_inventory,
)
from keyboards.inline import shop_keyboard, back_to_menu_keyboard

router = Router()

@router.message(Command("shop"))
async def cmd_shop(message: Message):
    user = await get_or_create_user(message.from_user.id, message.from_user.username, message.from_user.full_name)
    badge = user.get("badge") or ""
    badge_str = f" | Ник: <b>{badge}</b>" if badge else ""

    items = await get_shop_items()
    text = (
        f"🛍 <b>Магазин игровых приколов {SHOP_NAME}</b>\n\n"
        f"💰 Баланс: <code>{user['balance']}</code> 🪙{badge_str}\n"
        "Цифровые штуки внутри бота: титулы, ауры, победные фразы и улучшения коноплянки. "
        "Никаких физических товаров."
    )
    await message.answer(text, reply_markup=shop_keyboard(items), parse_mode="HTML")

@router.callback_query(F.data == "shop")
async def cb_shop(callback: CallbackQuery):
    user = await get_or_create_user(callback.from_user.id, callback.from_user.username, callback.from_user.full_name)
    badge = user.get("badge") or ""
    badge_str = f" | Ник: <b>{badge}</b>" if badge else ""

    items = await get_shop_items()
    text = (
        f"🛍 <b>Магазин игровых приколов {SHOP_NAME}</b>\n\n"
        f"💰 Баланс: <code>{user['balance']}</code> 🪙{badge_str}\n"
        "Цифровые штуки внутри бота: титулы, ауры, победные фразы и улучшения коноплянки. "
        "Никаких физических товаров."
    )
    await callback.message.edit_text(text, reply_markup=shop_keyboard(items), parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data.startswith("shop_buy:"))
async def cb_shop_buy(callback: CallbackQuery):
    item_id = int(callback.data.split(":")[1])
    success, msg, purchased_item = await buy_item(callback.from_user.id, item_id)
    if not success or purchased_item is None:
        await callback.answer(msg, show_alert=True)
        return

    item_type = purchased_item["item_type"]
    if item_type == "badge":
        effect = f"🏷 Титул <b>{purchased_item['content']}</b> теперь отображается в играх."
    elif item_type == "aura":
        effect = f"✨ Эффект <b>{purchased_item['title']}</b> установлен в профиле."
    elif item_type == "taunt":
        effect = "🗣 Победная фраза будет появляться после ваших побед."
    elif item_type in {"dragon_item", "hemp_item"}:
        effect = f"🌿 <b>{purchased_item['title']}</b> активирован в ферме."
    else:
        effect = "Покупка активирована."

    text = (
        f"🎉 <b>Покупка активирована!</b>\n\n"
        f"{effect}\n"
        f"💸 Списано: <code>{purchased_item['price']}</code> 🪙"
    )
    await callback.message.edit_text(text, reply_markup=back_to_menu_keyboard(), parse_mode="HTML")
    await callback.answer("Титул установлен!")

@router.callback_query(F.data == "my_purchases")
async def cb_my_purchases(callback: CallbackQuery):
    decorations = await get_user_decorations(callback.from_user.id)
    inventory = await get_user_inventory(callback.from_user.id)
    inventory_text = ", ".join(
        "{} ×{}".format(item["title"], item["quantity"]) for item in inventory
    ) or "пусто"
    status_text = (
        f"🏷 Титул: {decorations['badge'] or 'не установлен'}\n"
        f"✨ Аура: {decorations['aura'] or 'не установлена'}\n"
        f"🗣 Победная фраза: {decorations['taunt'] or 'не установлена'}\n"
        f"🌿 Улучшения коноплянки: {inventory_text}"
    )

    text = (
        f"🎒 <b>Ваши игровые эффекты {SHOP_NAME}:</b>\n\n"
        f"{status_text}\n\n"
        "Купите новые приколы в магазине за монеты!"
    )
    await callback.message.edit_text(text, reply_markup=back_to_menu_keyboard(), parse_mode="HTML")
    await callback.answer()
