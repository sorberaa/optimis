import asyncio
import logging
import re
from typing import Dict, Any, List, Optional
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from config import SHOP_NAME
from database import (
    is_admin,
    add_admin,
    create_roulette,
    create_roulette_with_custom_players,
    get_roulette,
    set_roulette_message_id,
    get_active_chat_roulette,
    join_roulette,
    leave_roulette,
    get_roulette_players,
    update_roulette_player_roll,
    finish_roulette,
    cancel_roulette,
    update_balance,
    get_or_create_user
)
from handlers.games import GAME_EMOJIS, GAME_NAMES, describe_roll

logger = logging.getLogger(__name__)

router = Router()

# Кэш мастера настроек: (admin_id, chat_id) -> dict
wizard_cache: Dict[tuple[int, int], Dict[str, Any]] = {}

# Премиум-наборы для быстрого запуска рулеток админом
PREMIUM_ROULETTE_PRESETS: Dict[str, Dict[str, Any]] = {
    "football_3_vip": {
        "title": "⚽ 3 места / VIP",
        "game_type": "football",
        "slots": 3,
        "fee": 0,
        "prize": "VIP-статус",
    },
    "basketball_5_500": {
        "title": "🏀 5 мест / 500 🪙",
        "game_type": "basketball",
        "slots": 5,
        "fee": 0,
        "prize": "500 🪙",
    },
    "darts_10_2500": {
        "title": "🎯 10 мест / 2500 🪙",
        "game_type": "darts",
        "slots": 10,
        "fee": 0,
        "prize": "2500 🪙",
    },
    "slots_12_badge": {
        "title": "🎰 12 мест / Бэйдж",
        "game_type": "slots",
        "slots": 12,
        "fee": 0,
        "prize": "Уникальный значок",
    },
    "dice_20_title": {
        "title": "🎲 20 мест / Титул",
        "game_type": "dice",
        "slots": 20,
        "fee": 0,
        "prize": "Титул чемпиона",
    },
}

# Состояние текущего хода с 2-минутным таймером: chat_id -> dict
active_turn_states: Dict[int, Dict[str, Any]] = {}


def wizard_cache_key(admin_id: int, chat_id: int) -> tuple[int, int]:
    return (admin_id, chat_id)


def get_wizard_state(admin_id: int, chat_id: int) -> Optional[Dict[str, Any]]:
    key = wizard_cache_key(admin_id, chat_id)
    if key in wizard_cache:
        return wizard_cache[key]
    legacy_key = admin_id
    if legacy_key in wizard_cache:
        state = wizard_cache.pop(legacy_key)
        wizard_cache[key] = state
        return state
    return None


def set_wizard_state(admin_id: int, chat_id: int, state: Dict[str, Any]) -> None:
    wizard_cache[wizard_cache_key(admin_id, chat_id)] = state
    wizard_cache.pop(admin_id, None)


def pop_wizard_state(admin_id: int, chat_id: int) -> Optional[Dict[str, Any]]:
    key = wizard_cache_key(admin_id, chat_id)
    if key in wizard_cache:
        return wizard_cache.pop(key)
    legacy = wizard_cache.pop(admin_id, None)
    if legacy is not None:
        return legacy
    return None

def calculate_score(game_type: str, roll_value: int) -> int:
    """Подсчет очков для турнирной таблицы."""
    if game_type == "football":
        if roll_value == 5:
            return 50
        elif roll_value in (3, 4):
            return 30
        elif roll_value == 2:
            return 5
        return 0
    elif game_type == "basketball":
        if roll_value == 5:
            return 50
        elif roll_value == 4:
            return 30
        return 0
    elif game_type == "darts":
        pts = {1: 0, 2: 10, 3: 15, 4: 25, 5: 35, 6: 60}
        return pts.get(roll_value, roll_value)
    elif game_type == "bowling":
        pins = {1: 0, 2: 10, 3: 20, 4: 30, 5: 40, 6: 60}
        return pins.get(roll_value, roll_value)
    elif game_type == "slots":
        if roll_value == 64:
            return 100
        elif roll_value in (1, 22, 43):
            return 50
        return roll_value
    return roll_value * 10

def parse_participants_list(raw_text: str) -> List[str]:
    lines = raw_text.strip().split("\n")
    participants = []
    for line in lines:
        cleaned = line.strip()
        if not cleaned:
            continue
        if cleaned.startswith("/") or cleaned.startswith("Приз:") or cleaned.startswith("Игра:"):
            continue
        cleaned = re.sub(r"^(\d+[\.)\-]?\s*|[\-\•\*]\s*)", "", cleaned).strip()
        if cleaned:
            participants.append(cleaned)
    return participants

def format_players_list(players: List[Dict[str, Any]], max_players: int) -> str:
    if not players:
        return f"<i>Свободно мест: {max_players}</i>"

    lines = []
    for i, p in enumerate(players, 1):
        name = f"@{p['username']}" if p.get("username") else p["full_name"]
        badge = f"{p['badge']} " if p.get("badge") else ""
        lines.append(f"{i}. {badge}<b>{name}</b>")

    remaining = max_players - len(players)
    if remaining > 0:
        lines.append(f"<i>(Свободно мест: {remaining})</i>")
    else:
        lines.append("🔥 <b>Все места заняты! Старт...</b>")

    return "\n".join(lines)

def roulette_post_keyboard(roulette_id: int, current_count: int, max_players: int) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(text=f"🎟 Записаться ({current_count}/{max_players})", callback_data=f"r_join:{roulette_id}"),
            InlineKeyboardButton(text="❌ Выйти", callback_data=f"r_leave:{roulette_id}")
        ],
        [
            InlineKeyboardButton(text="▶️ Запустить (Админ)", callback_data=f"r_force_start:{roulette_id}"),
            InlineKeyboardButton(text="🚫 Отмена (Админ)", callback_data=f"r_cancel:{roulette_id}")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def premium_roulette_keyboard() -> InlineKeyboardMarkup:
    rows: List[List[InlineKeyboardButton]] = []
    for i, preset in enumerate(PREMIUM_ROULETTE_PRESETS.values(), 1):
        rows.append([
            InlineKeyboardButton(text=preset["title"], callback_data=f"quick_roulette:{list(PREMIUM_ROULETTE_PRESETS.keys())[i-1]}")
        ])
    rows.append([
        InlineKeyboardButton(text="🔙 Назад в админку", callback_data="admin_roulette_info")
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# Кнопки выбора приза (без скидок — только монеты и косметика)
def prize_buttons(prefix: str) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(text="🪙 500 монет", callback_data=f"{prefix}:500 🪙"),
            InlineKeyboardButton(text="🪙 1000 монет", callback_data=f"{prefix}:1000 🪙")
        ],
        [
            InlineKeyboardButton(text="🪙 2500 монет", callback_data=f"{prefix}:2500 🪙"),
            InlineKeyboardButton(text="👑 VIP-статус", callback_data=f"{prefix}:VIP-статус")
        ],
        [
            InlineKeyboardButton(text="🏅 Уникальный значок", callback_data=f"{prefix}:Уникальный значок"),
            InlineKeyboardButton(text="⭐ Титул чемпиона", callback_data=f"{prefix}:Титул чемпиона")
        ],
        [
            InlineKeyboardButton(text="❌ Отмена", callback_data="wiz_cancel")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# Кнопки выбора игры
def game_buttons(prefix: str) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(text="⚽ Футбол", callback_data=f"{prefix}:football"),
            InlineKeyboardButton(text="🏀 Баскетбол", callback_data=f"{prefix}:basketball")
        ],
        [
            InlineKeyboardButton(text="🎯 Дартс", callback_data=f"{prefix}:darts"),
            InlineKeyboardButton(text="🎳 Боулинг", callback_data=f"{prefix}:bowling")
        ],
        [
            InlineKeyboardButton(text="🎲 Кости", callback_data=f"{prefix}:dice"),
            InlineKeyboardButton(text="🎰 Слоты", callback_data=f"{prefix}:slots")
        ],
        [
            InlineKeyboardButton(text="❌ Отмена", callback_data="wiz_cancel")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# =================================================================
# 1. ЗАГРУЗКА ГОТОВОГО СПИСКА УЧАСТНИКОВ (/list_game)
# =================================================================

@router.message(Command("list_game", "load_list", "run_list"))
async def cmd_load_list_game(message: Message):
    if message.chat.type == "private":
        await message.reply("💡 Игры по списку — только в групповом чате!")
        return

    if not await is_admin(message.from_user.id):
        await message.reply("❌ Только админы.")
        return

    active = await get_active_chat_roulette(message.chat.id)
    if active:
        await message.reply(f"⚠️ Уже идет игра #{active['id']}!")
        return

    raw_text = ""
    if message.reply_to_message and message.reply_to_message.text:
        raw_text = message.reply_to_message.text
    else:
        parts = message.text.split("\n", 1)
        if len(parts) > 1:
            raw_text = parts[1]

    participants = parse_participants_list(raw_text)

    if len(participants) < 2:
        await message.reply(
            "📋 <b>Как запустить по списку:</b>\n\n"
            "<b>Вариант 1:</b>\n"
            "<code>/list_game\n"
            "1. @ivan\n"
            "2. @sergey\n"
            "3. @dmitry</code>\n\n"
            "<b>Вариант 2:</b> Ответьте <code>/list_game</code> на сообщение со списком!",
            parse_mode="HTML"
        )
        return

    set_wizard_state(message.from_user.id, message.chat.id, {
        "participants": participants,
        "chat_id": message.chat.id
    })

    p_preview = "\n".join([f"• {p}" for p in participants[:10]])
    if len(participants) > 10:
        p_preview += f"\n<i>...и еще {len(participants) - 10}</i>"

    await message.reply(
        f"✅ <b>Список загружен ({len(participants)} чел.)</b>\n\n"
        f"{p_preview}\n\n"
        f"Выберите дисциплину:",
        reply_markup=game_buttons("lg_game"),
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("lg_game:"))
async def cb_lg_game(callback: CallbackQuery):
    logger.info(f"cb_lg_game: user={callback.from_user.id}, data={callback.data}")
    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ Только для админов!", show_alert=True)
        return

    game_type = callback.data.split(":")[1]
    data = get_wizard_state(callback.from_user.id, callback.message.chat.id)
    if not data:
        await callback.answer("❌ Сессия устарела, повторите команду.", show_alert=True)
        return

    data["game_type"] = game_type

    await callback.message.edit_text(
        f"🎮 Дисциплина: <b>{GAME_NAMES.get(game_type, game_type)}</b>\n\n"
        f"Выберите приз:",
        reply_markup=prize_buttons("lg_prize"),
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data.startswith("lg_prize:"))
async def cb_lg_prize(callback: CallbackQuery):
    logger.info(f"cb_lg_prize: user={callback.from_user.id}, data={callback.data}")
    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ Только для админов!", show_alert=True)
        return

    prize = callback.data.split(":", 1)[1]
    data = get_wizard_state(callback.from_user.id, callback.message.chat.id)
    if not data:
        await callback.answer("❌ Сессия устарела.", show_alert=True)
        return

    data["prize"] = prize

    buttons = [
        [
            InlineKeyboardButton(text="⏱ Живой ход (2 мин / DQ)", callback_data="lg_start:live"),
        ],
        [
            InlineKeyboardButton(text="⚡ Быстрый авто-бросок", callback_data="lg_start:fast")
        ],
        [
            InlineKeyboardButton(text="❌ Отмена", callback_data="wiz_cancel")
        ]
    ]
    await callback.message.edit_text(
        f"🎮 {GAME_NAMES.get(data['game_type'], '?')} | 🎁 {prize}\n"
        f"👥 Участников: {len(data['participants'])}\n\n"
        f"Режим проведения:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data.startswith("lg_start:"))
async def cb_lg_start(callback: CallbackQuery, bot: Bot):
    logger.info(f"cb_lg_start: user={callback.from_user.id}, data={callback.data}")
    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ Только для админов!", show_alert=True)
        return

    mode = callback.data.split(":")[1]
    data = pop_wizard_state(callback.from_user.id, callback.message.chat.id)
    if not data:
        await callback.answer("❌ Сессия устарела.", show_alert=True)
        return

    chat_id = data["chat_id"]
    participants = data["participants"]
    game_type = data["game_type"]
    prize = data["prize"]

    await callback.message.delete()

    r_id = await create_roulette_with_custom_players(
        chat_id=chat_id,
        creator_id=callback.from_user.id,
        game_type=game_type,
        prize=prize,
        players_list=participants
    )

    asyncio.create_task(run_roulette_game(
        bot=bot,
        chat_id=chat_id,
        roulette_id=r_id,
        is_live_timer=(mode == "live")
    ))


# =================================================================
# 2. ИНТЕРАКТИВНЫЙ МАСТЕР СОЗДАНИЯ РУЛЕТКИ С САМОЗАПИСЬЮ (/game)
# =================================================================

@router.callback_query(F.data == "admin_quick_roulette")
async def cb_admin_quick_roulette(callback: CallbackQuery):
    if callback.message.chat.type == "private":
        await callback.answer("💡 Быстрый запуск доступен только в группах.", show_alert=True)
        return
    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ Только для админов!", show_alert=True)
        return

    text = (
        "🚀 <b>ПРЕМИУМ-ЗАПУСК РУЛЕТОК</b>\n\n"
        "Выберите готовый пресет или вернитесь к обычному мастеру."
    )
    await callback.message.edit_text(text, reply_markup=premium_roulette_keyboard(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("quick_roulette:"))
async def cb_quick_roulette(callback: CallbackQuery, bot: Bot):
    if callback.message.chat.type == "private":
        await callback.answer("💡 Рулетки запускаются только в групповых чатах.", show_alert=True)
        return
    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ Только для админов!", show_alert=True)
        return

    preset_id = callback.data.split(":", 1)[1]
    preset = PREMIUM_ROULETTE_PRESETS.get(preset_id)
    if not preset:
        await callback.answer("❌ Пресет не найден.", show_alert=True)
        return

    active = await get_active_chat_roulette(callback.message.chat.id)
    if active:
        await callback.answer(f"⚠️ Уже идет игра #{active['id']}!", show_alert=True)
        return

    chat_id = callback.message.chat.id
    game_type = preset["game_type"]
    slots = preset["slots"]
    fee = preset["fee"]
    prize = preset["prize"]

    await callback.message.delete()

    r_id = await create_roulette(
        chat_id=chat_id,
        creator_id=callback.from_user.id,
        game_type=game_type,
        prize=prize,
        max_players=slots,
        entry_fee=fee,
    )

    fee_text = f"<code>{fee}</code> 🪙" if fee > 0 else "БЕСПЛАТНЫЙ"
    game_title = GAME_NAMES.get(game_type, "Футбол")

    post = await bot.send_message(
        chat_id=chat_id,
        text=(
            f"🎰 <b>РУЛЕТКА {SHOP_NAME}!</b> 🎰\n\n"
            f"🎮 {game_title}\n"
            f"🎁 Приз: <b>{prize}</b>\n"
            f"💰 Вход: {fee_text}\n"
            f"👥 Мест: <b>{slots}</b>\n"
            f"⏱ 2 мин на ход или DQ!\n\n"
            f"<b>Участники (0/{slots}):</b>\n"
            f"<i>Свободно мест: {slots}</i>\n\n"
            f"👇 <i>Жмите «Записаться»!</i>"
        ),
        reply_markup=roulette_post_keyboard(r_id, 0, slots),
        parse_mode="HTML"
    )
    await set_roulette_message_id(r_id, post.message_id)
    await callback.answer(f"✅ Рулетка запущена: {preset['title']}")


@router.message(Command("game", "roulette", "start_game"))
async def cmd_start_roulette(message: Message):
    logger.info(f"cmd_start_roulette: user={message.from_user.id}, chat={message.chat.id}, type={message.chat.type}")

    if message.chat.type == "private":
        await message.reply("💡 Игры проводятся в групповом чате!")
        return

    if not await is_admin(message.from_user.id):
        await message.reply("❌ Только админы могут запускать игры.")
        return

    active = await get_active_chat_roulette(message.chat.id)
    if active:
        await message.reply(f"⚠️ Уже идет игра #{active['id']}!")
        return

    # Сохраняем chat_id сразу в кэш мастера
    set_wizard_state(message.from_user.id, message.chat.id, {"chat_id": message.chat.id})

    await message.reply(
        "🎰 <b>Создание игры</b>\n\nВыберите дисциплину:",
        reply_markup=game_buttons("wiz_game"),
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("wiz_game:"))
async def cb_wiz_game(callback: CallbackQuery):
    logger.info(f"cb_wiz_game FIRED: user={callback.from_user.id}, data={callback.data}")

    admin_ok = await is_admin(callback.from_user.id)
    logger.info(f"cb_wiz_game is_admin={admin_ok}")

    if not admin_ok:
        await callback.answer("❌ Только для админов!", show_alert=True)
        return

    game_type = callback.data.split(":")[1]

    # Берём существующий кэш или создаём новый
    data = get_wizard_state(callback.from_user.id, callback.message.chat.id)
    if data is None:
        data = {"chat_id": callback.message.chat.id}
        set_wizard_state(callback.from_user.id, callback.message.chat.id, data)

    data["game_type"] = game_type

    buttons = [
        [
            InlineKeyboardButton(text="3 места", callback_data="wiz_slots:3"),
            InlineKeyboardButton(text="5 мест", callback_data="wiz_slots:5"),
            InlineKeyboardButton(text="10 мест", callback_data="wiz_slots:10")
        ],
        [
            InlineKeyboardButton(text="15 мест", callback_data="wiz_slots:15"),
            InlineKeyboardButton(text="20 мест", callback_data="wiz_slots:20"),
            InlineKeyboardButton(text="30 мест", callback_data="wiz_slots:30")
        ],
        [
            InlineKeyboardButton(text="❌ Отмена", callback_data="wiz_cancel")
        ]
    ]
    try:
        await callback.message.edit_text(
            f"🎮 <b>{GAME_NAMES.get(game_type, game_type)}</b>\n\nКоличество мест:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"cb_wiz_game edit_text error: {e}")
    await callback.answer()

@router.callback_query(F.data.startswith("wiz_slots:"))
async def cb_wiz_slots(callback: CallbackQuery):
    logger.info(f"cb_wiz_slots: user={callback.from_user.id}, data={callback.data}")
    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ Только для админов!", show_alert=True)
        return

    slots = int(callback.data.split(":")[1])
    data = get_wizard_state(callback.from_user.id, callback.message.chat.id)
    if data is None:
        data = {"game_type": "football", "chat_id": callback.message.chat.id}
        set_wizard_state(callback.from_user.id, callback.message.chat.id, data)
    data["slots"] = slots

    buttons = [
        [
            InlineKeyboardButton(text="🆓 Бесплатно", callback_data="wiz_fee:0"),
            InlineKeyboardButton(text="💰 50 🪙", callback_data="wiz_fee:50")
        ],
        [
            InlineKeyboardButton(text="💰 100 🪙", callback_data="wiz_fee:100"),
            InlineKeyboardButton(text="💰 250 🪙", callback_data="wiz_fee:250")
        ],
        [
            InlineKeyboardButton(text="❌ Отмена", callback_data="wiz_cancel")
        ]
    ]
    await callback.message.edit_text(
        f"👥 Мест: <b>{slots}</b>\n\nСтоимость участия:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data.startswith("wiz_fee:"))
async def cb_wiz_fee(callback: CallbackQuery):
    logger.info(f"cb_wiz_fee: user={callback.from_user.id}, data={callback.data}")
    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ Только для админов!", show_alert=True)
        return

    fee = int(callback.data.split(":")[1])
    data = get_wizard_state(callback.from_user.id, callback.message.chat.id)
    if not data:
        data = {"game_type": "football", "slots": 10, "chat_id": callback.message.chat.id}
        set_wizard_state(callback.from_user.id, callback.message.chat.id, data)
    data["fee"] = fee

    await callback.message.edit_text(
        f"👥 Мест: <b>{data.get('slots', 10)}</b> | Взнос: <b>{fee} 🪙</b>\n\n"
        f"Выберите приз:",
        reply_markup=prize_buttons("wiz_prize"),
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data.startswith("wiz_prize:"))
async def cb_wiz_prize(callback: CallbackQuery, bot: Bot):
    logger.info(f"cb_wiz_prize: user={callback.from_user.id}, data={callback.data}")
    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ Только для админов!", show_alert=True)
        return

    prize = callback.data.split(":", 1)[1]
    data = pop_wizard_state(callback.from_user.id, callback.message.chat.id)
    if not data:
        data = {"game_type": "football", "slots": 10, "fee": 0, "chat_id": callback.message.chat.id}

    game_type = data.get("game_type", "football")
    slots = data.get("slots", 10)
    fee = data.get("fee", 0)
    chat_id = data.get("chat_id", callback.message.chat.id)

    await callback.message.delete()

    r_id = await create_roulette(
        chat_id=chat_id,
        creator_id=callback.from_user.id,
        game_type=game_type,
        prize=prize,
        max_players=slots,
        entry_fee=fee
    )

    fee_text = f"<code>{fee}</code> 🪙" if fee > 0 else "БЕСПЛАТНЫЙ"
    game_title = GAME_NAMES.get(game_type, "Футбол")

    post = await bot.send_message(
        chat_id=chat_id,
        text=(
            f"🎰 <b>РУЛЕТКА {SHOP_NAME}!</b> 🎰\n\n"
            f"🎮 {game_title}\n"
            f"🎁 Приз: <b>{prize}</b>\n"
            f"💰 Вход: {fee_text}\n"
            f"👥 Мест: <b>{slots}</b>\n"
            f"⏱ 2 мин на ход или DQ!\n\n"
            f"<b>Участники (0/{slots}):</b>\n"
            f"<i>Свободно мест: {slots}</i>\n\n"
            f"👇 <i>Жмите «Записаться»!</i>"
        ),
        reply_markup=roulette_post_keyboard(r_id, 0, slots),
        parse_mode="HTML"
    )
    await set_roulette_message_id(r_id, post.message_id)
    await callback.answer("✅ Рулетка открыта!")

@router.callback_query(F.data == "wiz_cancel")
async def cb_wiz_cancel(callback: CallbackQuery):
    pop_wizard_state(callback.from_user.id, callback.message.chat.id)
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.answer("Отменено.")


# =================================================================
# 3. ЗАПИСЬ НА ИГРУ ПО КНОПКЕ В ЧАТЕ
# =================================================================

@router.callback_query(F.data.startswith("r_join:"))
async def cb_roulette_join(callback: CallbackQuery, bot: Bot):
    roulette_id = int(callback.data.split(":")[1])
    user = callback.from_user

    await get_or_create_user(user.id, user.username, user.full_name)

    success, msg, count, max_p = await join_roulette(
        roulette_id=roulette_id,
        user_id=user.id,
        username=user.username,
        full_name=user.full_name
    )

    if not success:
        await callback.answer(msg, show_alert=True)
        return

    await callback.answer("🎟 Вы записались!")

    roulette = await get_roulette(roulette_id)
    players = await get_roulette_players(roulette_id)
    players_text = format_players_list(players, roulette["max_players"])

    fee_text = f"<code>{roulette['entry_fee']}</code> 🪙" if roulette["entry_fee"] > 0 else "БЕСПЛАТНЫЙ"
    game_title = GAME_NAMES.get(roulette["game_type"], "Футбол")

    text = (
        f"🎰 <b>РУЛЕТКА {SHOP_NAME}!</b> 🎰\n\n"
        f"🎮 {game_title}\n"
        f"🎁 Приз: <b>{roulette['prize']}</b>\n"
        f"💰 Вход: {fee_text}\n"
        f"👥 Мест: <b>{roulette['max_players']}</b>\n"
        f"⏱ 2 мин на ход или DQ!\n\n"
        f"<b>Участники ({len(players)}/{roulette['max_players']}):</b>\n"
        f"{players_text}\n\n"
        f"👇 <i>Жмите «Записаться»!</i>"
    )

    try:
        await callback.message.edit_text(
            text,
            reply_markup=roulette_post_keyboard(roulette_id, len(players), roulette["max_players"]),
            parse_mode="HTML"
        )
    except Exception:
        pass

    if count >= max_p:
        asyncio.create_task(run_roulette_game(bot, callback.message.chat.id, roulette_id, is_live_timer=True))

@router.callback_query(F.data.startswith("r_leave:"))
async def cb_roulette_leave(callback: CallbackQuery):
    roulette_id = int(callback.data.split(":")[1])
    user = callback.from_user

    success, msg = await leave_roulette(roulette_id, user.id)
    if not success:
        await callback.answer(msg, show_alert=True)
        return

    await callback.answer("Вы вышли.")

    roulette = await get_roulette(roulette_id)
    if not roulette or roulette["status"] != "registration":
        return

    players = await get_roulette_players(roulette_id)
    players_text = format_players_list(players, roulette["max_players"])
    fee_text = f"<code>{roulette['entry_fee']}</code> 🪙" if roulette["entry_fee"] > 0 else "БЕСПЛАТНЫЙ"
    game_title = GAME_NAMES.get(roulette["game_type"], "Футбол")

    text = (
        f"🎰 <b>РУЛЕТКА {SHOP_NAME}!</b> 🎰\n\n"
        f"🎮 {game_title}\n"
        f"🎁 Приз: <b>{roulette['prize']}</b>\n"
        f"💰 Вход: {fee_text}\n"
        f"👥 Мест: <b>{roulette['max_players']}</b>\n\n"
        f"<b>Участники ({len(players)}/{roulette['max_players']}):</b>\n"
        f"{players_text}\n\n"
        f"👇 <i>Жмите «Записаться»!</i>"
    )

    try:
        await callback.message.edit_text(
            text,
            reply_markup=roulette_post_keyboard(roulette_id, len(players), roulette["max_players"]),
            parse_mode="HTML"
        )
    except Exception:
        pass

@router.callback_query(F.data.startswith("r_force_start:"))
async def cb_roulette_force_start(callback: CallbackQuery, bot: Bot):
    roulette_id = int(callback.data.split(":")[1])
    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ Только админы!", show_alert=True)
        return

    roulette = await get_roulette(roulette_id)
    if not roulette or roulette["status"] != "registration":
        await callback.answer("❌ Игра уже началась или завершена!", show_alert=True)
        return

    players = await get_roulette_players(roulette_id)
    if len(players) < 2:
        await callback.answer("❌ Нужно минимум 2 участника!", show_alert=True)
        return

    await callback.answer("🚀 Запуск...")
    asyncio.create_task(run_roulette_game(bot, callback.message.chat.id, roulette_id, is_live_timer=True))

@router.callback_query(F.data.startswith("r_cancel:"))
async def cb_roulette_cancel(callback: CallbackQuery):
    roulette_id = int(callback.data.split(":")[1])
    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ Только админы!", show_alert=True)
        return

    success = await cancel_roulette(roulette_id)
    if success:
        await callback.message.edit_text(
            f"🚫 <b>Рулетка #{roulette_id} отменена.</b>",
            parse_mode="HTML"
        )
        await callback.answer("Отменено.")
    else:
        await callback.answer("Не удалось отменить.", show_alert=True)


# =================================================================
# 4. ОБРАБОТЧИКИ ХОДА: БРОСОК ИЛИ DQ
# =================================================================

@router.callback_query(F.data.startswith("turn_roll:"))
async def cb_turn_roll(callback: CallbackQuery, bot: Bot):
    chat_id = int(callback.data.split(":")[1])
    state = active_turn_states.get(chat_id)
    if not state:
        await callback.answer("Ход уже завершен.", show_alert=True)
        return

    current_player = state["player"]
    user = callback.from_user

    is_turn_player = (user.id == current_player.get("user_id")) or \
                     (user.username and f"@{user.username}".lower() == f"@{current_player.get('username', '')}".lower())
    user_is_admin = await is_admin(user.id)

    if not is_turn_player and not user_is_admin:
        await callback.answer("❌ Не ваш ход!", show_alert=True)
        return

    game_emoji = state["emoji"]
    d = await bot.send_dice(chat_id=chat_id, emoji=game_emoji)
    val = d.dice.value

    state["roll_val"] = val
    state["event"].set()
    await callback.answer("🎲 Бросок сделан!")

@router.callback_query(F.data.startswith("turn_dq:"))
async def cb_turn_dq(callback: CallbackQuery):
    chat_id = int(callback.data.split(":")[1])
    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ Только админ!", show_alert=True)
        return

    state = active_turn_states.get(chat_id)
    if not state:
        await callback.answer("Ход не активен.", show_alert=True)
        return

    state["dq"] = True
    state["event"].set()
    await callback.answer("⚠️ Игрок дисквалифицирован.")


# =================================================================
# 5. ДВИЖОК ТУРНИРА + ТАЙМЕР 2 МИН (DQ)
# =================================================================

async def run_roulette_game(bot: Bot, chat_id: int, roulette_id: int, is_live_timer: bool = True):
    roulette = await get_roulette(roulette_id)
    if not roulette:
        return

    players = await get_roulette_players(roulette_id)
    if not players:
        return

    game_type = roulette["game_type"]
    game_emoji = GAME_EMOJIS.get(game_type, "⚽")
    game_title = GAME_NAMES.get(game_type, "Футбол")

    timer_note = "⏱ <b>2 мин на ход или DQ!</b>\n\n" if is_live_timer else ""

    await bot.send_message(
        chat_id=chat_id,
        text=(
            f"🚨 <b>ТУРНИР НАЧИНАЕТСЯ!</b> 🚨\n\n"
            f"🎮 {game_title} | 🎁 {roulette['prize']}\n"
            f"👥 Участников: {len(players)}\n"
            f"{timer_note}"
            f"<i>Приготовьтесь...</i>"
        ),
        parse_mode="HTML"
    )
    await asyncio.sleep(2)

    scores = []

    for i, p in enumerate(players, 1):
        name = f"@{p['username']}" if p.get("username") else p["full_name"]
        badge = f"{p['badge']} " if p.get("badge") else ""
        display_name = f"{badge}{name}"

        if is_live_timer:
            event = asyncio.Event()
            active_turn_states[chat_id] = {
                "player": p,
                "emoji": game_emoji,
                "event": event,
                "roll_val": None,
                "dq": False
            }

            turn_kb = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text=f"🎲 Бросок {game_emoji}", callback_data=f"turn_roll:{chat_id}")
                ],
                [
                    InlineKeyboardButton(text="⏭ DQ (Админ)", callback_data=f"turn_dq:{chat_id}")
                ]
            ])

            turn_msg = await bot.send_message(
                chat_id=chat_id,
                text=(
                    f"🎯 <b>Ход {i}/{len(players)}:</b> {display_name}\n\n"
                    f"Жми кнопку {game_emoji}\n"
                    f"⏳ <b>2 мин или DQ!</b>"
                ),
                reply_markup=turn_kb,
                parse_mode="HTML"
            )

            try:
                await asyncio.wait_for(event.wait(), timeout=120.0)
            except asyncio.TimeoutError:
                active_turn_states[chat_id]["dq"] = True

            state = active_turn_states.pop(chat_id, {})
            try:
                await turn_msg.delete()
            except Exception:
                pass

            if state.get("dq"):
                await bot.send_message(
                    chat_id=chat_id,
                    text=(
                        f"⏰ <b>ВРЕМЯ!</b>\n"
                        f"❌ {display_name} — <b>DQ</b>"
                    ),
                    parse_mode="HTML"
                )
                await update_roulette_player_roll(roulette_id, p["user_id"], 0, -1)
                scores.append({
                    "user_id": p["user_id"],
                    "name": display_name,
                    "roll": 0,
                    "score": -1,
                    "desc": "❌ DQ"
                })
                await asyncio.sleep(2)
                continue
            else:
                val = state["roll_val"]
                await asyncio.sleep(3.5)

        else:
            await bot.send_message(chat_id, f"🎯 <b>Ход {i}/{len(players)}:</b> {display_name}...", parse_mode="HTML")
            dice_msg = await bot.send_dice(chat_id=chat_id, emoji=game_emoji)
            val = dice_msg.dice.value
            await asyncio.sleep(3.5)

        score = calculate_score(game_type, val)
        await update_roulette_player_roll(roulette_id, p["user_id"], val, score)
        desc = describe_roll(game_type, val)

        scores.append({
            "user_id": p["user_id"],
            "name": display_name,
            "roll": val,
            "score": score,
            "desc": desc
        })

    scores.sort(key=lambda x: x["score"], reverse=True)

    active_scores = [s for s in scores if s["score"] >= 0]

    if not active_scores:
        await bot.send_message(chat_id, "💀 <b>Все DQ! Игра без победителя.</b>", parse_mode="HTML")
        await finish_roulette(roulette_id, 0, "Никто")
        return

    top_score = active_scores[0]["score"]
    leaders = [s for s in active_scores if s["score"] == top_score]

    if len(leaders) > 1:
        tied_names = ", ".join([l["name"] for l in leaders])
        await bot.send_message(
            chat_id,
            f"⚔️ <b>НИЧЬЯ ({top_score} очков)!</b>\n"
            f"{tied_names}\n\n"
            f"🔥 <b>СУПЕРФИНАЛ!</b>",
            parse_mode="HTML"
        )
        await asyncio.sleep(2.5)

        while len(leaders) > 1:
            tie_scores = []
            for l in leaders:
                await bot.send_message(chat_id, f"⚡ {l['name']}...", parse_mode="HTML")
                d = await bot.send_dice(chat_id=chat_id, emoji=game_emoji)
                val = d.dice.value
                score = calculate_score(game_type, val)
                tie_scores.append({"user_id": l["user_id"], "name": l["name"], "score": score, "roll": val})
                await asyncio.sleep(3.5)

            tie_scores.sort(key=lambda x: x["score"], reverse=True)
            best_score = tie_scores[0]["score"]
            leaders = [s for s in tie_scores if s["score"] == best_score]

            if len(leaders) > 1:
                await bot.send_message(chat_id, "🤝 Снова ничья! Ещё раз...")
                await asyncio.sleep(2)

        winner = leaders[0]
    else:
        winner = active_scores[0]

    await finish_roulette(roulette_id, winner["user_id"], winner["name"])

    prize_str = roulette["prize"]
    prize_words = prize_str.split()
    if prize_words and prize_words[0].isdigit() and winner["user_id"] > 0:
        coin_amount = int(prize_words[0])
        await update_balance(winner["user_id"], coin_amount)

    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    table_lines = []
    for i, s in enumerate(scores):
        if s["score"] < 0:
            table_lines.append(f"❌ <b>{s['name']}</b> — DQ")
        else:
            m = medals[i] if i < len(medals) else f"{i+1}."
            table_lines.append(f"{m} <b>{s['name']}</b> — {s['desc']} (<b>{s['score']}</b>)")

    table_content = "\n".join(table_lines)

    result_text = (
        f"🏁 <b>ИТОГИ:</b>\n\n"
        f"{table_content}\n\n"
        f"🏆 <b>ПОБЕДИТЕЛЬ:</b> {winner['name']}!\n"
        f"🎁 <b>ПРИЗ:</b> {roulette['prize']}"
    )

    await bot.send_message(chat_id, result_text, parse_mode="HTML")
