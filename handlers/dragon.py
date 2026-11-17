import html
from typing import Any, Dict, List, Optional

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from database import (
    DRAGON_STAGES,
    claim_dragon_income,
    feed_dragon,
    get_or_create_dragon,
    get_or_create_user,
    get_top_dragons,
    get_user_inventory,
    rename_dragon,
    send_dragon_expedition,
    set_dragon_element,
    train_dragon,
    xp_for_next_level,
)

router = Router()

ELEMENTS = {
    "fire": "🔥 Огонь",
    "ice": "❄️ Лёд",
    "shadow": "🌑 Тень",
    "gold": "✨ Золото",
}

STAGE_STORY = {
    1: "На островах Optimus найдено древнее яйцо. Оно ждёт тепла и заботы.",
    2: "Яйцо раскололось! Дракончик впервые вдохнул воздух затерянного архипелага.",
    3: "Юный дракон освоил полёт и заметил следы чудовищ у старых руин.",
    4: "Воин-дракон готов исследовать опасные земли и охранять гнездо.",
    5: "Дракон-Титан пробудил сердце островов. Впереди — легенда Optimus!",
}

ITEMS = {
    "steak": "🥩 Стейк из виверны",
    "potion": "🧪 Зелье бодрости",
    "crystal": "✨ Кристалл эволюции",
}


def dragon_keyboard(dragon: Dict[str, Any], inventory: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="🍖 Покормить бесплатно", callback_data="dragon:feed")]
    ]
    quantities = {item["item_key"]: item["quantity"] for item in inventory}
    for item_key, title in ITEMS.items():
        if quantities.get(item_key, 0) > 0:
            buttons.append([
                InlineKeyboardButton(
                    text=f"{title} ×{quantities[item_key]}",
                    callback_data=f"dragon:feed:{item_key}"
                )
            ])

    buttons.append([
        InlineKeyboardButton(text="🥊 Тренировка", callback_data="dragon:train"),
        InlineKeyboardButton(text="💰 Собрать дань", callback_data="dragon:income")
    ])
    buttons.append([
        InlineKeyboardButton(text="🌲 Лес", callback_data="dragon:exp:forest"),
        InlineKeyboardButton(text="⛰️ Пещера", callback_data="dragon:exp:cave"),
        InlineKeyboardButton(text="🌋 Вулкан", callback_data="dragon:exp:volcano")
    ])
    if dragon["level"] < 2:
        buttons.append([
            InlineKeyboardButton(text="🎨 Выбрать стихию", callback_data="dragon:elements")
        ])
    buttons.append([
        InlineKeyboardButton(text="🏆 Топ драконов", callback_data="dragon:top")
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def dragon_status(dragon: Dict[str, Any], inventory: List[Dict[str, Any]]) -> str:
    stage = DRAGON_STAGES[dragon["stage"]]
    required_xp = xp_for_next_level(dragon["level"])
    story = STAGE_STORY.get(dragon["stage"], STAGE_STORY[1])
    inventory_text = ", ".join(
        f"{item['title']} ×{item['quantity']}" for item in inventory if item["quantity"] > 0
    ) or "пусто"
    return (
        f"🐉 <b>ДРАКОНОВОД Optimus</b>\n\n"
        f"<i>{story}</i>\n\n"
        f"🏷 Имя: <b>{html.escape(dragon['name'])}</b>\n"
        f"🌈 Стихия: <b>{html.escape(dragon['element'])}</b>\n"
        f"🐲 Стадия: <b>{stage['name']}</b>\n"
        f"⭐ Уровень: <b>{dragon['level']}</b> | Опыт: <code>{dragon['xp']}/{required_xp}</code>\n"
        f"⚡ Энергия: <code>{dragon['energy']}/{dragon['max_energy']}</code>\n"
        f"💪 Сила: <b>{dragon['power']}</b>\n"
        f"🧭 Экспедиции: {dragon['expeditions_count']} | Успехи: {dragon['wins_count']}\n"
        f"🎒 Игровые припасы: {html.escape(inventory_text)}\n\n"
        "<b>Как растить:</b> бесплатное кормление раз в час; тренировка тратит 25 энергии "
        "и даёт опыт/силу; экспедиции приносят монеты и опыт, но расходуют энергию. "
        "Дань из логова доступна раз в 12 часов.\n"
        "Все покупки — только виртуальные эффекты и припасы внутри игры."
    )


async def show_dragon(message: Message, user_id: int, username: Optional[str], full_name: str):
    await get_or_create_user(user_id, username, full_name)
    dragon = await get_or_create_dragon(user_id)
    inventory = await get_user_inventory(user_id)
    await message.answer(
        dragon_status(dragon, inventory),
        reply_markup=dragon_keyboard(dragon, inventory),
        parse_mode="HTML"
    )


@router.message(Command("dragon"))
async def cmd_dragon(message: Message):
    if message.chat.type != "private":
        await message.reply("🐉 Напиши /dragon в личке с ботом — там будет твоя драконья карточка.")
        return
    await show_dragon(message, message.from_user.id, message.from_user.username, message.from_user.full_name)


@router.callback_query(F.data == "dragon")
async def cb_dragon(callback: CallbackQuery):
    if callback.message.chat.type != "private":
        await callback.answer("Открой личный чат с ботом для игры в драконов.", show_alert=True)
        return
    await show_dragon(
        callback.message,
        callback.from_user.id,
        callback.from_user.username,
        callback.from_user.full_name
    )
    await callback.answer()


async def refresh_dragon(callback: CallbackQuery, notice: str = ""):
    dragon = await get_or_create_dragon(callback.from_user.id)
    inventory = await get_user_inventory(callback.from_user.id)
    text = dragon_status(dragon, inventory)
    if notice:
        text = f"{notice}\n\n{text}"
    await callback.message.edit_text(
        text,
        reply_markup=dragon_keyboard(dragon, inventory),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "dragon:feed")
@router.callback_query(F.data.startswith("dragon:feed:"))
async def cb_dragon_feed(callback: CallbackQuery):
    item_key = callback.data.split(":", 2)[2] if callback.data.count(":") == 2 else None
    success, message, _ = await feed_dragon(callback.from_user.id, item_key)
    await refresh_dragon(callback, message)
    await callback.answer("Дракон накормлен!" if success else "Не удалось покормить.", show_alert=not success)


@router.callback_query(F.data == "dragon:train")
async def cb_dragon_train(callback: CallbackQuery):
    success, message, _ = await train_dragon(callback.from_user.id)
    await refresh_dragon(callback, message)
    await callback.answer("Тренировка завершена!" if success else "Пока не получилось.", show_alert=not success)


@router.callback_query(F.data.startswith("dragon:exp:"))
async def cb_dragon_expedition(callback: CallbackQuery):
    exp_type = callback.data.rsplit(":", 1)[1]
    success, message, _ = await send_dragon_expedition(callback.from_user.id, exp_type)
    await refresh_dragon(callback, message)
    await callback.answer("Экспедиция завершена!" if success else "Экспедиция не удалась.", show_alert=not success)


@router.callback_query(F.data == "dragon:income")
async def cb_dragon_income(callback: CallbackQuery):
    success, amount, message = await claim_dragon_income(callback.from_user.id)
    notice = f"🏦 Дань собрана: +{amount} 🪙." if success else f"⏳ {message or 'Дань пока недоступна.'}"
    await refresh_dragon(callback, notice)
    await callback.answer("Монеты начислены!" if success else "Пока нельзя собрать.", show_alert=not success)


@router.callback_query(F.data == "dragon:elements")
async def cb_dragon_elements(callback: CallbackQuery):
    dragon = await get_or_create_dragon(callback.from_user.id)
    if dragon["level"] >= 2:
        await callback.answer("Стихия закрепляется при вылуплении и больше не меняется.", show_alert=True)
        return

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=element, callback_data=f"dragon:element:{key}")]
        for key, element in ELEMENTS.items()
    ] + [[InlineKeyboardButton(text="⬅️ К дракону", callback_data="dragon")]])
    await callback.message.edit_text(
        "🎨 <b>Выбери стихию яйца.</b>\n\n"
        "Огонь повышает шанс успеха; Лёд экономит энергию; Тень увеличивает добычу; "
        "Золото усиливает пассивную дань. Выбор закрепится после вылупления.",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("dragon:element:"))
async def cb_dragon_element(callback: CallbackQuery):
    key = callback.data.rsplit(":", 1)[1]
    dragon = await get_or_create_dragon(callback.from_user.id)
    if key not in ELEMENTS or dragon["level"] >= 2:
        await callback.answer("Стихию уже нельзя поменять.", show_alert=True)
        return
    await set_dragon_element(callback.from_user.id, ELEMENTS[key])
    await refresh_dragon(callback, "✨ Стихия яйца изменена. После вылупления выбор станет постоянным.")
    await callback.answer("Стихия выбрана!")


@router.message(Command("dragon_name"))
async def cmd_rename_dragon(message: Message):
    if message.chat.type != "private":
        await message.reply("🐉 Переименовать дракона можно в личном чате с ботом.")
        return
    new_name = message.text.partition(" ")[2].strip()
    if not new_name:
        await message.reply("Использование: <code>/dragon_name Новое имя</code>", parse_mode="HTML")
        return
    dragon = await get_or_create_dragon(message.from_user.id)
    if not await rename_dragon(message.from_user.id, new_name):
        await message.reply("Имя должно содержать хотя бы один символ.")
        return
    await message.answer(
        f"🐉 Дракона теперь зовут <b>{html.escape(new_name[:25])}</b>.",
        parse_mode="HTML"
    )


@router.callback_query(F.data == "dragon:top")
async def cb_dragon_top(callback: CallbackQuery):
    dragons = await get_top_dragons()
    rows = []
    for rank, dragon in enumerate(dragons, 1):
        name = html.escape(dragon["full_name"] or dragon["username"] or str(dragon["user_id"]))
        dragon_name = html.escape(dragon["name"])
        rows.append(
            f"{rank}. <b>{name}</b> — {dragon['stage']} стадия, "
            f"{dragon['level']} ур., {dragon['power']} 💪 ({dragon_name})"
        )
    text = "🏆 <b>СИЛЬНЕЙШИЕ ДРАКОНЫ</b>\n\n" + ("\n".join(rows) or "Пока нет драконов.")
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ К моему дракону", callback_data="dragon")]
        ]),
        parse_mode="HTML"
    )
    await callback.answer()
