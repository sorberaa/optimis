import html

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from database import (
    collect_hemp,
    get_or_create_hemp,
    get_or_create_user,
    get_top_hemp,
    get_user_inventory,
    harvest_hemp,
    plant_hemp,
    sell_hemp,
)

router = Router()


def progress_bar(value: int, maximum: int, width: int = 10) -> str:
    if maximum <= 0:
        return "⬜" * width
    filled = min(width, max(0, int(value * width / maximum)))
    return "🟩" * filled + "⬜" * (width - filled)


def hemp_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🌿 Собрать", callback_data="hemp:collect"),
            InlineKeyboardButton(text="🌱 Посадить", callback_data="hemp:plant")
        ],
        [
            InlineKeyboardButton(text="🧺 Собрать урожай", callback_data="hemp:harvest"),
            InlineKeyboardButton(text="💵 Продать всё", callback_data="hemp:sell")
        ],
        [
            InlineKeyboardButton(text="🛍 Магазин фермы", callback_data="shop"),
            InlineKeyboardButton(text="🏆 Топ фермеров", callback_data="hemp:top")
        ],
        [
            InlineKeyboardButton(text="⬅️ Главное меню", callback_data="back_main")
        ]
    ])


def hemp_status(hemp: dict, inventory: list) -> str:
    level = hemp["level"]
    xp_now = hemp["xp"]
    required = level * 100
    quality = hemp["quality"]
    active = hemp["active_plots"]
    plots = hemp["plots"]
    inventory_text = ", ".join(
        f"{item['title']} ×{item['quantity']}" for item in inventory if item["quantity"] > 0
    ) or "пусто"
    return (
        "╭━━━ 🌿 <b>КОНОПЛЯНКА</b> ━━━╮\n"
        f"│ Урожай: <b>{hemp['leaves']}</b> 🌿\n"
        f"│ Семена: <b>{hemp['seed_stock']}</b>  |  Качество: <b>{quality}/5</b>\n"
        f"│ Грядки: <b>{active}/{plots}</b>\n"
        "├━━━━━━━━━━━━━━━━━━━━\n"
        f"│ Уровень <b>{level}</b>\n"
        f"│ Опыт {progress_bar(xp_now, required)}  {xp_now}/{required}\n"
        "╰━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🎒 <b>Улучшения:</b> {html.escape(inventory_text)}\n"
        f"💰 Цена одной культуры: <b>{10 + (quality - 1) * 2}</b> 🪙\n\n"
        "<i>Собирай дикие листья, сажай семена на грядки и продавай урожай за монеты.</i>"
    )


async def show_hemp(message: Message, user_id: int, username: str | None, full_name: str):
    await get_or_create_user(user_id, username, full_name)
    hemp = await get_or_create_hemp(user_id)
    inventory = await get_user_inventory(user_id)
    await message.answer(
        hemp_status(hemp, inventory),
        reply_markup=hemp_keyboard(),
        parse_mode="HTML"
    )


@router.message(Command("hemp"))
async def cmd_hemp(message: Message):
    await show_hemp(
        message,
        message.from_user.id,
        message.from_user.username,
        message.from_user.full_name
    )


@router.message(Command("collect"))
async def cmd_collect_hemp(message: Message):
    await get_or_create_user(message.from_user.id, message.from_user.username, message.from_user.full_name)
    success, amount, notice, hemp = await collect_hemp(message.from_user.id)
    if success:
        await message.answer(
            f"🌿 <b>{html.escape(notice)}</b>\n"
            f"+{amount} 🌿 к запасам\n"
            f"Всего в амбаре: <b>{hemp['leaves']}</b>",
            reply_markup=hemp_keyboard(),
            parse_mode="HTML"
        )
    else:
        await message.answer(f"⏳ <b>{html.escape(notice)}</b>", reply_markup=hemp_keyboard(), parse_mode="HTML")


@router.message(Command("plant"))
async def cmd_plant_hemp(message: Message):
    await get_or_create_user(message.from_user.id, message.from_user.username, message.from_user.full_name)
    success, notice, hemp = await plant_hemp(message.from_user.id)
    await message.answer(
        f"{'🌱' if success else '⚠️'} <b>{html.escape(notice)}</b>\n"
        f"Семян осталось: <b>{hemp['seed_stock']}</b>",
        reply_markup=hemp_keyboard(),
        parse_mode="HTML"
    )


@router.message(Command("sell"))
async def cmd_sell_hemp(message: Message):
    await get_or_create_user(message.from_user.id, message.from_user.username, message.from_user.full_name)
    success, leaves, coins, hemp = await sell_hemp(message.from_user.id)
    if success:
        await message.answer(
            f"💵 <b>Продажа завершена</b>\n"
            f"Продано: <b>{leaves}</b> 🌿 за <b>{coins}</b> 🪙",
            reply_markup=hemp_keyboard(),
            parse_mode="HTML"
        )
    else:
        await message.answer("🌿 В амбаре пока нет листьев для продажи.", reply_markup=hemp_keyboard(), parse_mode="HTML")


@router.callback_query(F.data == "hemp")
@router.callback_query(F.data == "dragon")
async def cb_hemp(callback: CallbackQuery):
    await show_hemp(
        callback.message,
        callback.from_user.id,
        callback.from_user.username,
        callback.from_user.full_name
    )
    await callback.answer()


@router.callback_query(F.data == "hemp:collect")
async def cb_hemp_collect(callback: CallbackQuery):
    success, amount, notice, hemp = await collect_hemp(callback.from_user.id)
    text = (
        f"🌿 <b>{html.escape(notice)}</b>\n+{amount} 🌿\nВ амбаре: <b>{hemp['leaves']}</b>"
        if success else f"⏳ <b>{html.escape(notice)}</b>"
    )
    await callback.message.edit_text(text, reply_markup=hemp_keyboard(), parse_mode="HTML")
    await callback.answer("Собрали!" if success else "Подожди немного.", show_alert=not success)


@router.callback_query(F.data == "hemp:plant")
async def cb_hemp_plant(callback: CallbackQuery):
    success, notice, hemp = await plant_hemp(callback.from_user.id)
    text = (
        f"{'🌱' if success else '⚠️'} <b>{html.escape(notice)}</b>\n"
        f"Семян: <b>{hemp['seed_stock']}</b> | Грядки: <b>{hemp['active_plots']}/{hemp['plots']}</b>"
    )
    await callback.message.edit_text(text, reply_markup=hemp_keyboard(), parse_mode="HTML")
    await callback.answer("Посажено!" if success else "Сделать не получилось.", show_alert=not success)


@router.callback_query(F.data == "hemp:harvest")
async def cb_hemp_harvest(callback: CallbackQuery):
    success, amount, notice, hemp = await harvest_hemp(callback.from_user.id)
    text = (
        f"🧺 <b>{html.escape(notice)}</b>\n+{amount} 🌿\nВ амбаре: <b>{hemp['leaves']}</b>"
        if success else f"⏳ <b>{html.escape(notice)}</b>"
    )
    await callback.message.edit_text(text, reply_markup=hemp_keyboard(), parse_mode="HTML")
    await callback.answer("Урожай собран!" if success else "Пока рано.", show_alert=not success)


@router.callback_query(F.data == "hemp:sell")
async def cb_hemp_sell(callback: CallbackQuery):
    success, leaves, coins, hemp = await sell_hemp(callback.from_user.id)
    if success:
        text = f"💵 <b>Продано {leaves} 🌿 за {coins} 🪙!</b>"
    else:
        text = "🌿 В амбаре пока нет листьев."
    await callback.message.edit_text(text, reply_markup=hemp_keyboard(), parse_mode="HTML")
    await callback.answer("Продано!" if success else "Нечего продавать.", show_alert=not success)


@router.callback_query(F.data == "hemp:top")
async def cb_hemp_top(callback: CallbackQuery):
    rows = await get_top_hemp()
    lines = []
    medals = ["🥇", "🥈", "🥉"]
    for i, row in enumerate(rows, 1):
        name = row["nickname"] or row["username"] or row["full_name"] or str(row["user_id"])
        lines.append(
            f"{medals[i-1] if i <= 3 else f'{i}.'} <b>{html.escape(str(name))}</b> "
            f"— ур. {row['level']}, {row['leaves']} 🌿"
        )
    await callback.message.edit_text(
        "🏆 <b>ТОП ФЕРМЕРОВ</b>\n\n" + ("\n".join(lines) if lines else "Пока нет фермеров."),
        reply_markup=hemp_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()
