import html
from typing import Any, Dict

from aiogram import Router, F, Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
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
    add_shop_item,
    get_accounts_page,
    get_account_details,
    set_account_banned,
    set_account_balance,
    set_account_nickname,
    delete_account,
)
import aiosqlite

router = Router()
ACCOUNT_PAGE_SIZE = 8
account_action_states: Dict[int, Dict[str, Any]] = {}

def admin_panel_keyboard(is_super: bool = False) -> InlineKeyboardMarkup:
    """Инлайн-кнопки панели администратора."""
    buttons = [
        [
            InlineKeyboardButton(text="👥 Список админов", callback_data="admin_list"),
            InlineKeyboardButton(text="📊 Статистика клуба", callback_data="admin_stats")
        ]
    ]
    buttons.append([
        InlineKeyboardButton(text="👤 Игровые аккаунты", callback_data="admin_accounts")
    ])
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

def accounts_keyboard(accounts, page: int, total: int) -> InlineKeyboardMarkup:
    buttons = []
    for account in accounts:
        name = account.get("nickname") or account.get("username") or account.get("full_name") or "Игрок"
        status = "⛔ " if account["is_banned"] else ""
        buttons.append([
            InlineKeyboardButton(
                text=f"{status}{name[:28]} · {account['balance']} 🪙",
                callback_data=f"account_view:{account['user_id']}:{page}"
            )
        ])

    navigation = []
    if page > 0:
        navigation.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"accounts_page:{page - 1}"))
    if (page + 1) * ACCOUNT_PAGE_SIZE < total:
        navigation.append(InlineKeyboardButton(text="Вперёд ➡️", callback_data=f"accounts_page:{page + 1}"))
    if navigation:
        buttons.append(navigation)
    buttons.append([InlineKeyboardButton(text="⬅️ В админ-панель", callback_data="account_admin_back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def account_details_text(account: Dict[str, Any]) -> str:
    real_name = html.escape(account["full_name"] or "")
    username = f"@{html.escape(account['username'])}" if account.get("username") else "не задан"
    nickname = html.escape(account.get("nickname") or "не задан")
    status = "⛔ Заблокирован" if account["is_banned"] else "✅ Активен"
    return (
        f"👤 <b>Игровой аккаунт</b>\n\n"
        f"ID: <code>{account['user_id']}</code>\n"
        f"Статус: {status}\n"
        f"Игровой ник: <b>{nickname}</b>\n"
        f"Telegram: {username}\n"
        f"Имя Telegram: {real_name}\n"
        f"Баланс: <b>{account['balance']} 🪙</b>\n"
        f"Побед: {account['wins']} | Поражений: {account['losses']} | "
        f"Игр всего: {account['total_games']}\n"
        f"Дуэлей: {account['duel_count']} | Участий в рулетках: {account['roulette_count']}\n"
        f"Создан: {html.escape(str(account.get('created_at') or 'неизвестно'))}"
    )

def account_details_keyboard(account: Dict[str, Any], page: int) -> InlineKeyboardMarkup:
    ban_label = "✅ Разблокировать" if account["is_banned"] else "⛔ Заблокировать"
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=ban_label, callback_data=f"account_ban:{account['user_id']}:{page}")
        ],
        [
            InlineKeyboardButton(text="💰 Баланс", callback_data=f"account_balance:{account['user_id']}:{page}"),
            InlineKeyboardButton(text="🏷 Игровой ник", callback_data=f"account_rename:{account['user_id']}:{page}")
        ],
        [
            InlineKeyboardButton(text="📩 Написать в личку", callback_data=f"account_message:{account['user_id']}:{page}")
        ],
        [
            InlineKeyboardButton(text="🗑 Удалить аккаунт", callback_data=f"account_delete:{account['user_id']}:{page}")
        ],
        [
            InlineKeyboardButton(text="⬅️ К списку", callback_data=f"accounts_page:{page}")
        ]
    ])

async def show_accounts_page(message, page: int):
    accounts, total = await get_accounts_page(page, ACCOUNT_PAGE_SIZE)
    pages = max(1, (total + ACCOUNT_PAGE_SIZE - 1) // ACCOUNT_PAGE_SIZE)
    page = min(page, pages - 1)
    accounts, total = await get_accounts_page(page, ACCOUNT_PAGE_SIZE)
    await message.edit_text(
        f"👤 <b>Игровые аккаунты</b> — {total} аккаунтов, страница {page + 1}/{pages}.\n"
        "Выбери аккаунт для просмотра и управления.",
        reply_markup=accounts_keyboard(accounts, page, total),
        parse_mode="HTML"
    )

async def account_view(user_id: int, page: int):
    account = await get_account_details(user_id)
    if not account:
        accounts, total = await get_accounts_page(page, ACCOUNT_PAGE_SIZE)
        return "Аккаунт не найден.", accounts_keyboard(accounts, page, total)
    return account_details_text(account), account_details_keyboard(account, page)

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
        "3. @dmitry</code> (нужны @username для проверки бросков)\n"
        "<i>Или ответьте командой /list_game на сообщение со списком!</i>\n\n"
        "<b>2. Интерактивная рулетка с самозаписью:</b>\n"
        "Команда <code>/roulette</code> создаёт пост для записи. Когда все места заняты, бот объявит об этом; "
        "игра начнётся только после нажатия админом кнопки «Запустить».\n\n"
        "<b>Броски:</b> каждый участник сам отправляет в чат 3 анимированных броска нужного типа. "
        "Кнопка бота не делает бросок.\n\n"
        "⏱ <b>Правило 2 минут:</b>\n"
        "На три броска даётся 2 минуты. Если человек не явился — <b>автоматическая дисквалификация (DQ)</b>!"
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


# ==========================================
# УПРАВЛЕНИЕ ИГРОВЫМИ АККАУНТАМИ
# ==========================================

async def account_admin_allowed(callback: CallbackQuery) -> bool:
    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен.", show_alert=True)
        return False
    if callback.message.chat.type != "private":
        await callback.answer("Открой личный чат с ботом для управления аккаунтами.", show_alert=True)
        return False
    return True


@router.callback_query(F.data == "admin_accounts")
async def cb_admin_accounts(callback: CallbackQuery):
    if not await account_admin_allowed(callback):
        return
    await show_accounts_page(callback.message, 0)
    await callback.answer()


@router.callback_query(F.data.startswith("accounts_page:"))
async def cb_accounts_page(callback: CallbackQuery):
    if not await account_admin_allowed(callback):
        return
    page = max(0, int(callback.data.split(":")[1]))
    await show_accounts_page(callback.message, page)
    await callback.answer()


@router.callback_query(F.data.startswith("account_view:"))
async def cb_account_view(callback: CallbackQuery):
    if not await account_admin_allowed(callback):
        return
    _, raw_user_id, raw_page = callback.data.split(":")
    text, keyboard = await account_view(int(raw_user_id), int(raw_page))
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "account_admin_back")
async def cb_account_admin_back(callback: CallbackQuery):
    if not await account_admin_allowed(callback):
        return
    await callback.message.edit_text(
        "Панель администратора.",
        reply_markup=admin_panel_keyboard(await is_superadmin(callback.from_user.id)),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("account_ban:"))
async def cb_account_ban(callback: CallbackQuery):
    if not await account_admin_allowed(callback):
        return
    _, raw_user_id, raw_page = callback.data.split(":")
    user_id, page = int(raw_user_id), int(raw_page)
    account = await get_account_details(user_id)
    if not account:
        await callback.answer("Аккаунт не найден.", show_alert=True)
        return
    success = await set_account_banned(user_id, not bool(account["is_banned"]))
    if not success:
        await callback.answer("Нельзя блокировать аккаунт администратора.", show_alert=True)
        return
    text, keyboard = await account_view(user_id, page)
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer("Статус аккаунта изменён.")


async def request_account_action(callback: CallbackQuery, action: str):
    if not await account_admin_allowed(callback):
        return
    _, raw_user_id, raw_page = callback.data.split(":")
    user_id, page = int(raw_user_id), int(raw_page)
    if not await get_account_details(user_id):
        await callback.answer("Аккаунт не найден.", show_alert=True)
        return
    account_action_states[callback.from_user.id] = {
        "action": action,
        "user_id": user_id,
        "page": page,
    }
    prompts = {
        "balance": "Введи новый баланс монет (целое число от 0 до 2 147 483 647).",
        "nickname": "Введи новый игровой ник (до 32 символов).",
        "message": "Введи текст личного сообщения. Пользователь должен хотя бы раз открыть бота.",
    }
    await callback.message.answer(
        prompts[action],
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="❌ Отмена", callback_data="account_action_cancel")
        ]])
    )
    await callback.answer()


@router.callback_query(F.data.startswith("account_balance:"))
async def cb_account_balance(callback: CallbackQuery):
    await request_account_action(callback, "balance")


@router.callback_query(F.data.startswith("account_rename:"))
async def cb_account_rename(callback: CallbackQuery):
    await request_account_action(callback, "nickname")


@router.callback_query(F.data.startswith("account_message:"))
async def cb_account_message(callback: CallbackQuery):
    await request_account_action(callback, "message")


@router.callback_query(F.data.startswith("account_delete:"))
async def cb_account_delete(callback: CallbackQuery):
    if not await account_admin_allowed(callback):
        return
    _, raw_user_id, raw_page = callback.data.split(":")
    user_id, page = int(raw_user_id), int(raw_page)
    account = await get_account_details(user_id)
    if not account:
        await callback.answer("Аккаунт не найден.", show_alert=True)
        return
    await callback.message.edit_text(
        f"⚠️ <b>Удалить игровой аккаунт {html.escape(account.get('nickname') or account.get('full_name') or 'Игрок')}?</b>\n\n"
        "Будут удалены баланс, дракон, покупки и игровые записи. Отменить это действие нельзя.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🗑 Да, удалить", callback_data=f"account_delete_confirm:{user_id}:{page}")],
            [InlineKeyboardButton(text="↩️ Не удалять", callback_data=f"account_view:{user_id}:{page}")]
        ]),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("account_delete_confirm:"))
async def cb_account_delete_confirm(callback: CallbackQuery):
    if not await account_admin_allowed(callback):
        return
    _, raw_user_id, raw_page = callback.data.split(":")
    if not await delete_account(int(raw_user_id)):
        await callback.answer(
            "Аккаунт не найден, защищён или участвует в незавершённой игре.",
            show_alert=True
        )
        return
    page = int(raw_page)
    await show_accounts_page(callback.message, page)
    await callback.answer("Аккаунт и связанные игровые данные удалены.")


@router.callback_query(F.data == "account_action_cancel")
async def cb_account_action_cancel(callback: CallbackQuery):
    if not await account_admin_allowed(callback):
        return
    account_action_states.pop(callback.from_user.id, None)
    await callback.message.delete()
    await callback.answer("Действие отменено.")


async def account_action_input_filter(message: Message) -> bool:
    return bool(
        message.from_user
        and message.chat.type == "private"
        and message.from_user.id in account_action_states
    )


@router.message(account_action_input_filter)
async def handle_account_action_input(message: Message, bot: Bot):
    admin_id = message.from_user.id
    state = account_action_states.get(admin_id)
    if not state or not await is_admin(admin_id):
        account_action_states.pop(admin_id, None)
        return

    text = (message.text or "").strip()
    action = state["action"]
    user_id = state["user_id"]
    page = state["page"]

    if action == "balance":
        if not text.isdecimal() or int(text) > 2_147_483_647:
            await message.reply("Нужно целое число от 0 до 2 147 483 647. Попробуй ещё раз.")
            return
        changed = await set_account_balance(user_id, int(text))
        confirmation = "Баланс изменён." if changed else "Аккаунт не найден."
    elif action == "nickname":
        if not text or len(text) > 32:
            await message.reply("Ник должен содержать от 1 до 32 символов. Попробуй ещё раз.")
            return
        changed = await set_account_nickname(user_id, text)
        confirmation = "Игровой ник изменён." if changed else "Аккаунт не найден."
    else:
        if not text or len(text) > 4000:
            await message.reply("Сообщение должно содержать от 1 до 4000 символов.")
            return
        try:
            await bot.send_message(
                user_id,
                f"📩 <b>Сообщение от администрации:</b>\n\n{html.escape(text)}",
                parse_mode="HTML"
            )
            confirmation = "Личное сообщение доставлено."
        except (TelegramForbiddenError, TelegramBadRequest) as exc:
            confirmation = (
                "Не удалось доставить сообщение. Возможно, пользователь не запускал бота "
                f"или заблокировал его. Причина Telegram: {html.escape(str(exc))}"
            )

    account_action_states.pop(admin_id, None)
    await message.answer(confirmation)
    account = await get_account_details(user_id)
    if account:
        await message.answer(
            account_details_text(account),
            reply_markup=account_details_keyboard(account, page),
            parse_mode="HTML"
        )
