import html

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from database import (
    collect_hemp,
    craft_joint,
    get_or_create_hemp,
    get_or_create_user,
    harvest_hemp,
    plant_hemp,
    sell_hemp,
    smoke_bong,
    smoke_joint,
)

router = Router()


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
            InlineKeyboardButton(text="🌿 Скрутить", callback_data="hemp:craft"),
            InlineKeyboardButton(text="💨 Дунуть", callback_data="hemp:smoke"),
            InlineKeyboardButton(text="💧 Бонг", callback_data="hemp:bong")
        ]
    ])


def hemp_status(hemp: dict) -> str:
    active = hemp["active_plots"]
    plots = hemp["plots"]
    return (
        f"🌿 У тебя: <b>{hemp['leaves']}</b>\n"
        f"🌱 Семян: <b>{hemp['seed_stock']}</b>\n"
        f"🚬 Косяков: <b>{hemp['joints']}</b>\n"
        f"Грядки: <b>{active}/{plots}</b>"
    )


async def show_hemp(message: Message, user_id: int, username: str | None, full_name: str):
    await get_or_create_user(user_id, username, full_name)
    hemp = await get_or_create_hemp(user_id)
    await message.answer(
        hemp_status(hemp),
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
            f"🌿 Собрал коноплю\n+{amount} 🌿\nУ тебя: <b>{hemp['leaves']}</b>",
            reply_markup=hemp_keyboard(),
            parse_mode="HTML"
        )
    else:
        await message.answer(f"⏳ {html.escape(notice)}", reply_markup=hemp_keyboard(), parse_mode="HTML")


@router.message(Command("plant"))
async def cmd_plant_hemp(message: Message):
    await get_or_create_user(message.from_user.id, message.from_user.username, message.from_user.full_name)
    success, notice, hemp = await plant_hemp(message.from_user.id)
    await message.answer(
        "🌱 Посадил коноплю" if success else f"⏳ {html.escape(notice)}",
        reply_markup=hemp_keyboard(),
        parse_mode="HTML"
    )


@router.message(Command("sell"))
async def cmd_sell_hemp(message: Message):
    await get_or_create_user(message.from_user.id, message.from_user.username, message.from_user.full_name)
    success, leaves, coins, hemp = await sell_hemp(message.from_user.id)
    if success:
        await message.answer(
            f"💵 Продал {leaves} 🌿 за {coins} 🪙",
            reply_markup=hemp_keyboard(),
            parse_mode="HTML"
        )
    else:
        await message.answer("🌿 В амбаре пока нет листьев для продажи.", reply_markup=hemp_keyboard(), parse_mode="HTML")


@router.message(Command("craft", "joint", "скрутить", "скрутить_косяк"))
async def cmd_craft_joint(message: Message):
    await get_or_create_user(message.from_user.id, message.from_user.username, message.from_user.full_name)
    success, notice, hemp = await craft_joint(message.from_user.id)
    if success:
        await message.answer(
            f"🚬 <b>{html.escape(notice)}</b>\nУ тебя косяков: <b>{hemp['joints']}</b>",
            reply_markup=hemp_keyboard(),
            parse_mode="HTML"
        )
    else:
        await message.answer(f"🌿 {html.escape(notice)}", reply_markup=hemp_keyboard(), parse_mode="HTML")


@router.message(Command("smoke", "smoke_joint", "дунуть"))
async def cmd_smoke_joint(message: Message):
    await get_or_create_user(message.from_user.id, message.from_user.username, message.from_user.full_name)
    success, notice, hemp = await smoke_joint(message.from_user.id)
    await message.answer(
        f"💨 {html.escape(notice)}" if success else f"⏳ {html.escape(notice)}",
        reply_markup=hemp_keyboard(),
        parse_mode="HTML"
    )


@router.message(Command("bong", "smoke_bong", "покурить", "покурить_из_бонга"))
async def cmd_smoke_bong(message: Message):
    await get_or_create_user(message.from_user.id, message.from_user.username, message.from_user.full_name)
    success, notice, hemp = await smoke_bong(message.from_user.id)
    await message.answer(
        f"💧 {html.escape(notice)}" if success else f"🌿 {html.escape(notice)}",
        reply_markup=hemp_keyboard(),
        parse_mode="HTML"
    )


@router.message(Command("harvest"))
async def cmd_harvest_hemp(message: Message):
    await get_or_create_user(message.from_user.id, message.from_user.username, message.from_user.full_name)
    success, amount, notice, hemp = await harvest_hemp(message.from_user.id)
    if success:
        await message.answer(
            f"🧺 Собрал урожай\n+{amount} 🌿\nУ тебя: <b>{hemp['leaves']}</b>",
            reply_markup=hemp_keyboard(),
            parse_mode="HTML"
        )
    else:
        await message.answer(f"⏳ <b>{html.escape(notice)}</b>", reply_markup=hemp_keyboard(), parse_mode="HTML")


@router.callback_query(F.data == "hemp")
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
        f"🌿 Собрал коноплю\n+{amount} 🌿\nУ тебя: <b>{hemp['leaves']}</b>"
        if success else f"⏳ <b>{html.escape(notice)}</b>"
    )
    await callback.message.edit_text(text, reply_markup=hemp_keyboard(), parse_mode="HTML")
    await callback.answer("Собрали!" if success else "Подожди немного.", show_alert=not success)


@router.callback_query(F.data == "hemp:plant")
async def cb_hemp_plant(callback: CallbackQuery):
    success, notice, hemp = await plant_hemp(callback.from_user.id)
    text = (
        "🌱 Посадил коноплю" if success else f"⏳ <b>{html.escape(notice)}</b>"
    )
    await callback.message.edit_text(text, reply_markup=hemp_keyboard(), parse_mode="HTML")
    await callback.answer("Посажено!" if success else "Сделать не получилось.", show_alert=not success)


@router.callback_query(F.data == "hemp:harvest")
async def cb_hemp_harvest(callback: CallbackQuery):
    success, amount, notice, hemp = await harvest_hemp(callback.from_user.id)
    text = (
        f"🧺 Собрал урожай\n+{amount} 🌿\nУ тебя: <b>{hemp['leaves']}</b>"
        if success else f"⏳ <b>{html.escape(notice)}</b>"
    )
    await callback.message.edit_text(text, reply_markup=hemp_keyboard(), parse_mode="HTML")
    await callback.answer("Урожай собран!" if success else "Пока рано.", show_alert=not success)


@router.callback_query(F.data == "hemp:sell")
async def cb_hemp_sell(callback: CallbackQuery):
    success, leaves, coins, hemp = await sell_hemp(callback.from_user.id)
    if success:
        text = f"💵 Продал {leaves} 🌿 за {coins} 🪙"
    else:
        text = "🌿 В амбаре пока нет листьев."
    await callback.message.edit_text(text, reply_markup=hemp_keyboard(), parse_mode="HTML")
    await callback.answer("Продано!" if success else "Нечего продавать.", show_alert=not success)


@router.callback_query(F.data == "hemp:craft")
async def cb_hemp_craft(callback: CallbackQuery):
    success, notice, hemp = await craft_joint(callback.from_user.id)
    text = f"🚬 {notice}" if success else f"🌿 {notice}"
    await callback.message.edit_text(text, reply_markup=hemp_keyboard(), parse_mode="HTML")
    await callback.answer("Косяк готов!" if success else "Не получилось.", show_alert=not success)


@router.callback_query(F.data == "hemp:smoke")
async def cb_hemp_smoke(callback: CallbackQuery):
    success, notice, hemp = await smoke_joint(callback.from_user.id)
    text = f"💨 {notice}" if success else f"⏳ {notice}"
    await callback.message.edit_text(text, reply_markup=hemp_keyboard(), parse_mode="HTML")
    await callback.answer("Дунул!" if success else "Нельзя дунуть.", show_alert=not success)


@router.callback_query(F.data == "hemp:bong")
async def cb_hemp_bong(callback: CallbackQuery):
    success, notice, hemp = await smoke_bong(callback.from_user.id)
    text = f"💧 {notice}" if success else f"🌿 {notice}"
    await callback.message.edit_text(text, reply_markup=hemp_keyboard(), parse_mode="HTML")
    await callback.answer("Дунул из бонга!" if success else "Нет бонга.", show_alert=not success)


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
