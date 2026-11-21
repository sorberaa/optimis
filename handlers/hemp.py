import html

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from database import (
    collect_hemp,
    get_or_create_hemp,
    get_or_create_user,
    harvest_hemp,
    plant_hemp,
    sell_hemp,
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
        ]
    ])


def hemp_status(hemp: dict) -> str:
    active = hemp["active_plots"]
    plots = hemp["plots"]
    return (
        f"🌿 У тебя: <b>{hemp['leaves']}</b>\n"
        f"🌱 Семян: <b>{hemp['seed_stock']}</b>\n"
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
