from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from config import SHOP_NAME, DB_PATH
from database import (
    is_admin,
    is_superadmin,
    add_admin,
    remove_admin,
    get_all_admins,
    update_balance,
    add_shop_item
)
import aiosqlite

router = Router()

def admin_panel_keyboard(is_super: bool = False) -> InlineKeyboardMarkup:
    """Инлайн-кнопки панели администратора."""
    buttons = [
        [
            InlineKeyboardButton(text="👥 Список админов", callback_data="admin_list"),
            InlineKeyboardButton(text="📊 Статистика клуба", callback_data="admin_stats")
        ]
    ]
    if is_super:
        buttons.append([
            InlineKeyboardButton(text="➕ Назначить админа", callback_data="admin_add_info"),
            InlineKeyboardButton(text="➖ Снять админа", callback_data="admin_remove_info")
        ])
    buttons.append([
        InlineKeyboardButton(text="💰 Выдача / Списание", callback_data="admin_economy_info"),
        InlineKeyboardButton(text="🏷 Добавить титул", callback_data="admin_item_info")
    ])
    buttons.append([
        InlineKeyboardButton(text="🎰 Как запустить рулетку", callback_data="admin_roulette_info"),
        InlineKeyboardButton(text="🚀 Премиум запуск", callback_data="admin_quick_roulette")
    ])
    buttons.append([
        InlineKeyboardButton(text="❌ Закрыть панель", callback_data="admin_close")
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

@router.message(Command("admin"))
async def cmd_admin(message: Message):
    user_id = message.from_user.id
    if not await is_admin(user_id):
        return

    super_status = await is_superadmin(user_id)
    badge = "👑 Главный Администратор" if super_status else "⭐ Администратор клуба"

    text = (
        f"═══════════════════════════\n"
        f"   🔥 <b>ПАНЕЛЬ УПРАВЛЕНИЯ {SHOP_NAME}</b> 🔥\n"
        f"═══════════════════════════\n\n"
        f"👤 <b>Вы вошли как:</b> {message.from_user.mention_html()}\n"
        f"🎖 <b>Статус:</b> <code>{badge}</code>\n\n"
        f"<b>Быстрые команды:</b>\n"
        f"• <code>/admins</code> — список всех админов\n"
        f"• <code>/add_admin [id/ответ]</code> — назначить нового админа\n"
        f"• <code>/remove_admin [id/ответ]</code> — снять админа\n"
        f"• <code>/give [id/ответ] [сумма]</code> — начислить монеты игроку\n"
        f"• <code>/take [id/ответ] [сумма]</code> — списать монеты\n"
        f"• <code>/add_item Название | Описание | Цена | Промокод</code>\n"
        f"• <code>/broadcast [текст]</code> — объявление по всем чатам/игрокам\n"
        f"• <code>/stats_admin</code> — общая статистика\n\n"
        f"<i>Используйте кнопки меню ниже для быстрого доступа:</i>"
    )
    await message.answer(text, reply_markup=admin_panel_keyboard(super_status), parse_mode="HTML")

# ==========================================
# УПРАВЛЕНИЕ АДМИНИСТРАТОРАМИ
# ==========================================

@router.message(Command("admins"))
async def cmd_admins(message: Message):
    if not await is_admin(message.from_user.id):
        return

    admins = await get_all_admins()
    if not admins:
        await message.reply("Список администраторов пуст.")
        return

    lines = []
    for a in admins:
        badge = "👑 Владелец/Главный" if a["is_superadmin"] else "⭐ Админ"
        date_str = a["created_at"][:10] if a.get("created_at") else ""
        lines.append(f"• <b>{a['username']}</b> (ID: <code>{a['user_id']}</code>) — <i>{badge}</i> [{date_str}]")

    text = (
        f"👥 <b>АДМИНИСТРАЦИЯ КЛУБА {SHOP_NAME}:</b>\n\n"
        + "\n".join(lines)
    )
    await message.reply(text, parse_mode="HTML")

@router.message(Command("add_admin"))
async def cmd_add_admin(message: Message):
    sender_id = message.from_user.id
    if not await is_superadmin(sender_id):
        await message.reply("❌ Только главный администратор (владелец) может назначать новых админов.")
        return

    target_id = None
    target_username = "Admin"

    if message.reply_to_message:
        target_id = message.reply_to_message.from_user.id
        target_username = message.reply_to_message.from_user.username or message.reply_to_message.from_user.full_name
    else:
        args = message.text.split()[1:]
        if args and args[0].isdigit():
            target_id = int(args[0])
            if len(args) > 1:
                target_username = args[1]

    if not target_id:
        await message.reply(
            "ℹ️ <b>Как назначить админа:</b>\n\n"
            "1. Ответьте на сообщение пользователя командой <code>/add_admin</code>\n"
            "2. Или введите: <code>/add_admin [user_id] [username]</code>",
            parse_mode="HTML"
        )
        return

    await add_admin(target_id, target_username, added_by=sender_id)
    await message.reply(
        f"✅ <b>Пользователь успешно назначен администратором!</b>\n\n"
        f"👤 ID: <code>{target_id}</code>\n"
        f"🏷 Имя: <b>{target_username}</b>\n"
        f"Назначил: {message.from_user.mention_html()}",
        parse_mode="HTML"
    )

@router.message(Command("remove_admin"))
async def cmd_remove_admin(message: Message):
    sender_id = message.from_user.id
    if not await is_superadmin(sender_id):
        await message.reply("❌ Только главный администратор может снимать админов.")
        return

    target_id = None
    if message.reply_to_message:
        target_id = message.reply_to_message.from_user.id
    else:
        args = message.text.split()[1:]
        if args and args[0].isdigit():
            target_id = int(args[0])

    if not target_id:
        await message.reply("Использование: <code>/remove_admin [user_id]</code> или ответом на сообщение.", parse_mode="HTML")
        return

    success = await remove_admin(target_id)
    if success:
        await message.reply(f"✅ Пользователь <code>{target_id}</code> снят с поста администратора.", parse_mode="HTML")
    else:
        await message.reply("❌ Не удалось снять права (пользователь не найден или является несменяемым владельцем).")

# ==========================================
# ИНЛАЙН-ОБРАБОТЧИКИ АДМИНКИ
# ==========================================

@router.callback_query(F.data == "admin_list")
async def cb_admin_list(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен.", show_alert=True)
        return

    admins = await get_all_admins()
    lines = []
    for a in admins:
        badge = "👑 Главный" if a["is_superadmin"] else "⭐ Админ"
        lines.append(f"• <b>{a['username']}</b> (ID: <code>{a['user_id']}</code>) — {badge}")

    content = "\n".join(lines) if lines else "Список пуст."
    text = f"👥 <b>Список администраторов {SHOP_NAME}:</b>\n\n{content}"

    super_status = await is_superadmin(callback.from_user.id)
    await callback.message.edit_text(text, reply_markup=admin_panel_keyboard(super_status), parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data == "admin_add_info")
async def cb_admin_add_info(callback: CallbackQuery):
    text = (
        "➕ <b>Как назначить нового администратора:</b>\n\n"
        "1. Ответьте на сообщение нужного игрока командой:\n"
        "<code>/add_admin</code>\n\n"
        "2. Либо отправьте команду с его ID:\n"
        "<code>/add_admin 123456789 Nickname</code>"
    )
    super_status = await is_superadmin(callback.from_user.id)
    await callback.message.edit_text(text, reply_markup=admin_panel_keyboard(super_status), parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data == "admin_remove_info")
async def cb_admin_remove_info(callback: CallbackQuery):
    text = (
        "➖ <b>Как снять администратора:</b>\n\n"
        "1. Ответьте на сообщение админа командой:\n"
        "<code>/remove_admin</code>\n\n"
        "2. Либо укажите его ID:\n"
        "<code>/remove_admin 123456789</code>"
    )
    super_status = await is_superadmin(callback.from_user.id)
    await callback.message.edit_text(text, reply_markup=admin_panel_keyboard(super_status), parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data == "admin_economy_info")
async def cb_admin_economy_info(callback: CallbackQuery):
    text = (
        "💰 <b>Управление балансами игроков:</b>\n\n"
        "• <b>Выдать монеты:</b>\n"
        "<code>/give [сумма]</code> (ответом на сообщение)\n"
        "<code>/give [user_id] [сумма]</code>\n\n"
        "• <b>Списать монеты:</b>\n"
        "<code>/take [сумма]</code> (ответом на сообщение)\n"
        "<code>/take [user_id] [сумма]</code>"
    )
    super_status = await is_superadmin(callback.from_user.id)
    await callback.message.edit_text(text, reply_markup=admin_panel_keyboard(super_status), parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data == "admin_roulette_info")
async def cb_admin_roulette_info(callback: CallbackQuery):
    text = (
        "🎰 <b>ПРОВЕДЕНИЕ РУЛЕТОК И ТУРНИРОВ В ЧАТЕ:</b>\n\n"
        "<b>1. Игра по готовому списку от шефа:</b>\n"
        "Отправьте команду <code>/list_game</code> со списком участников:\n"
        "<code>/list_game\n"
        "1. @ivan\n"
        "2. @sergey\n"
        "3. @dmitry</code>\n"
        "<i>Или ответьте командой /list_game на сообщение со списком!</i>\n\n"
        "<b>2. Интерактивная рулетка с самозаписью:</b>\n"
        "Команда <code>/roulette</code> создаёт интерактивный пост, куда участники записываются по кнопкам.\n\n"
        "⏱ <b>Правило 2 минут:</b>\n"
        "В живом режиме на каждый ход дается ровно 2 минуты. Если человек не явился — <b>автоматическая дисквалификация (DQ)</b>!"
    )
    super_status = await is_superadmin(callback.from_user.id)
    await callback.message.edit_text(text, reply_markup=admin_panel_keyboard(super_status), parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data == "admin_item_info")
async def cb_admin_item_info(callback: CallbackQuery):
    text = (
        "🏷 <b>Добавление статуса в магазин:</b>\n\n"
        "Формат:\n"
        "<code>/add_item Название | Описание | Цена | Значок_к_нику</code>\n\n"
        "Пример:\n"
        "<code>/add_item 🔥 [Опасный] | Статус бойца | 500 | 🔥 [Опасный]</code>"
    )
    super_status = await is_superadmin(callback.from_user.id)
    await callback.message.edit_text(text, reply_markup=admin_panel_keyboard(super_status), parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data == "admin_stats")
async def cb_admin_stats(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен.", show_alert=True)
        return

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*), SUM(balance), SUM(total_games) FROM users") as cursor:
            users_count, total_balance, total_games = await cursor.fetchone()

        async with db.execute("SELECT COUNT(*) FROM duels WHERE status = 'finished'") as cursor:
            finished_duels = (await cursor.fetchone())[0]

        async with db.execute("SELECT COUNT(*) FROM purchases") as cursor:
            purchases_count = (await cursor.fetchone())[0]

        async with db.execute("SELECT COUNT(*) FROM admins") as cursor:
            admins_count = (await cursor.fetchone())[0]

    text = (
        f"📊 <b>СТАТИСТИКА КЛУБА {SHOP_NAME}:</b>\n\n"
        f"• Игроков в базе: <b>{users_count or 0}</b>\n"
        f"• Монет в обороте: <b>{total_balance or 0}</b> 🪙\n"
        f"• Проведено дуэлей: <b>{finished_duels or 0}</b>\n"
        f"• Куплено товаров/купонов: <b>{purchases_count or 0}</b>\n"
        f"• Действующих админов: <b>{admins_count or 0}</b>"
    )
    super_status = await is_superadmin(callback.from_user.id)
    await callback.message.edit_text(text, reply_markup=admin_panel_keyboard(super_status), parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data == "admin_close")
async def cb_admin_close(callback: CallbackQuery):
    await callback.message.delete()

# ==========================================
# ВЫДАЧА И СПИСАНИЕ БАЛАНСА
# ==========================================

@router.message(Command("give"))
async def cmd_give(message: Message):
    if not await is_admin(message.from_user.id):
        return

    args = message.text.split()[1:]
    target_id = None
    amount = 0

    if message.reply_to_message:
        target_id = message.reply_to_message.from_user.id
        if args and args[0].isdigit():
            amount = int(args[0])
    elif len(args) >= 2 and args[0].isdigit() and args[1].isdigit():
        target_id = int(args[0])
        amount = int(args[1])

    if not target_id or amount <= 0:
        await message.reply("Использование: <code>/give [user_id] [сумма]</code> или ответом на сообщение с <code>/give [сумма]</code>", parse_mode="HTML")
        return

    new_bal = await update_balance(target_id, amount)
    await message.reply(f"✅ Игроку <code>{target_id}</code> начислено <b>+{amount}</b> 🪙.\nНовый баланс: <code>{new_bal}</code> 🪙.", parse_mode="HTML")

@router.message(Command("take"))
async def cmd_take(message: Message):
    if not await is_admin(message.from_user.id):
        return

    args = message.text.split()[1:]
    target_id = None
    amount = 0

    if message.reply_to_message:
        target_id = message.reply_to_message.from_user.id
        if args and args[0].isdigit():
            amount = int(args[0])
    elif len(args) >= 2 and args[0].isdigit() and args[1].isdigit():
        target_id = int(args[0])
        amount = int(args[1])

    if not target_id or amount <= 0:
        await message.reply("Использование: <code>/take [user_id] [сумма]</code> или ответом на сообщение с <code>/take [сумма]</code>", parse_mode="HTML")
        return

    new_bal = await update_balance(target_id, -amount)
    await message.reply(f"⚠️ У игрока <code>{target_id}</code> списано <b>-{amount}</b> 🪙.\nНовый баланс: <code>{new_bal}</code> 🪙.", parse_mode="HTML")

@router.message(Command("add_item"))
async def cmd_add_item(message: Message):
    if not await is_admin(message.from_user.id):
        return

    raw = message.text[len("/add_item "):].strip()
    parts = [p.strip() for p in raw.split("|")]

    if len(parts) < 4:
        await message.reply(
            "Формат: <code>/add_item Название | Описание | Цена | Значок_к_нику</code>\n"
            "Пример: <code>/add_item 🔥 [Опасный] | Статус бойца | 500 | 🔥 [Опасный]</code>",
            parse_mode="HTML"
        )
        return

    title, desc, price_str, content = parts[0], parts[1], parts[2], parts[3]
    if not price_str.isdigit():
        await message.reply("Цена должна быть числом!")
        return

    item_id = await add_shop_item(title, desc, int(price_str), "badge", content)
    await message.reply(f"✅ Статус #{item_id} <b>«{title}»</b> добавлен в магазин за <code>{price_str}</code> 🪙!", parse_mode="HTML")

@router.message(Command("broadcast"))
async def cmd_broadcast(message: Message, bot: Bot):
    if not await is_admin(message.from_user.id):
        return

    text = message.text[len("/broadcast "):].strip()
    if not text:
        await message.reply("Введите текст для рассылки: <code>/broadcast Внимание, турнир!</code>", parse_mode="HTML")
        return

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id FROM users") as cursor:
            rows = await cursor.fetchall()

    count = 0
    for (uid,) in rows:
        try:
            await bot.send_message(uid, f"📢 <b>Объявление от {SHOP_NAME}:</b>\n\n{text}", parse_mode="HTML")
            count += 1
        except Exception:
            pass

    await message.reply(f"✅ Рассылка завершена! Доставлено игрокам: <b>{count}</b>.", parse_mode="HTML")

@router.message(Command("stats_admin"))
async def cmd_stats_admin(message: Message):
    if not await is_admin(message.from_user.id):
        return

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*), SUM(balance), SUM(total_games) FROM users") as cursor:
            users_count, total_balance, total_games = await cursor.fetchone()

        async with db.execute("SELECT COUNT(*) FROM duels WHERE status = 'finished'") as cursor:
            finished_duels = (await cursor.fetchone())[0]

        async with db.execute("SELECT COUNT(*) FROM purchases") as cursor:
            purchases_count = (await cursor.fetchone())[0]

        async with db.execute("SELECT COUNT(*) FROM admins") as cursor:
            admins_count = (await cursor.fetchone())[0]

    text = (
        f"📊 <b>Общая статистика бота {SHOP_NAME}:</b>\n\n"
        f"• Всего пользователей в БД: <b>{users_count or 0}</b>\n"
        f"• Всего монет на балансах: <b>{total_balance or 0}</b> 🪙\n"
        f"• Всего сыграно дуэлей: <b>{finished_duels or 0}</b>\n"
        f"• Куплено товаров в магазине: <b>{purchases_count or 0}</b>\n"
        f"• Администраторов: <b>{admins_count or 0}</b>"
    )
    await message.answer(text, parse_mode="HTML")
