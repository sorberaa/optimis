import asyncio
import html
import time
from typing import Dict
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from config import SHOP_NAME
from database import (
    get_or_create_user,
    get_user,
    create_duel,
    get_duel,
    accept_duel,
    cancel_duel,
    record_duel_result,
    update_balance,
    spend_balance,
    get_user_decorations
)
from keyboards.inline import (
    games_selection_keyboard,
    bet_selection_keyboard,
    duel_invitation_keyboard,
    back_to_menu_keyboard
)

router = Router()

# Маппинг типов игр на эмодзи Telegram
GAME_EMOJIS = {
    "football": "⚽",
    "basketball": "🏀",
    "darts": "🎯",
    "bowling": "🎳",
    "dice": "🎲",
    "slots": "🎰"
}

GAME_NAMES = {
    "football": "⚽ Футбол (Пенальти)",
    "basketball": "🏀 Баскетбол (Бросок)",
    "darts": "🎯 Дартс (В яблочко)",
    "bowling": "🎳 Боулинг (Страйк)",
    "dice": "🎲 Кости (Кубик)",
    "slots": "🎰 Слоты (777)"
}

# Кулдаун на броски эмодзи в чате (секунды): user_id -> timestamp
dice_cooldowns: Dict[int, float] = {}
MAX_DICE_COOLDOWNS = 5000

def get_game_emoji(game_type: str) -> str:
    return GAME_EMOJIS.get(game_type, "🎲")

def bet_prompt_text(game_title: str, user_balance: int, mode: str) -> str:
    if user_balance <= 0:
        hint = "Баланс пуст — забери бонус или заработай монеты в чат-играх."
    elif user_balance < 25:
        hint = "Для тебя доступен ва-банк на весь баланс."
    else:
        hint = "Выбери комфортную ставку. Показаны только доступные суммы."
    prefix = "⚔️ Дуэль" if mode == "duel" else "🎲 Игра против бота"
    return (
        f"{prefix}: <b>{game_title}</b>\n\n"
        f"💰 Баланс: <code>{user_balance}</code> 🪙\n"
        f"{hint}"
    )

def describe_roll(game_type: str, value: int) -> str:
    """Текстовое описание результата броска эмодзи."""
    if game_type == "football":
        if value == 1:
            return f"❌ <b>Мимо ворот</b> (сила: {value})"
        elif value == 2:
            return f"⚠️ <b>Штанга/перекладина</b> (сила: {value})"
        elif value in (3, 4):
            return f"⚽ <b>ГОЛ!</b> (сила: {value})"
        elif value == 5:
            return f"⚽🔥 <b>ГОЛ В ДЕВЯТКУ!</b> (сила: {value})"
    elif game_type == "basketball":
        if value in (1, 2, 3):
            return f"❌ <b>Мимо кольца</b> (очки: {value})"
        elif value == 4:
            return f"🏀 <b>Попадание!</b> (очки: {value})"
        elif value == 5:
            return f"🏀🔥 <b>Чистый трехочковый!</b> (очки: {value})"
    elif game_type == "darts":
        if value == 1:
            return "❌ <b>Мимо мишени</b> (1)"
        elif value in (2, 3):
            return f"🎯 <b>Внешнее кольцо</b> ({value})"
        elif value in (4, 5):
            return f"🎯 <b>Внутреннее кольцо</b> ({value})"
        elif value == 6:
            return "🎯🔥 <b>В САМОЕ ЯБЛОЧКО!</b> (50 очков)"
    elif game_type == "bowling":
        if value == 1:
            return "❌ <b>Мимо / желоб</b> (0 кеглей)"
        elif value in (2, 3, 4, 5):
            return f"🎳 <b>Сбито кеглей: {value - 1}</b>"
        elif value == 6:
            return "🎳💥 <b>СТРАЙК! Все кегли повержены!</b> (6)"
    elif game_type == "dice":
        return f"🎲 <b>Выпало число: {value}</b>"
    elif game_type == "slots":
        if value == 64:
            return "🎰🔥🔥 <b>ДЖЕКПОТ 777!</b>"
        elif value in (1, 22, 43):
            return f"🎰 <b>Выигрышная линия!</b> ({value})"
        else:
            return f"🎰 <b>Комбинация:</b> {value}"
    return f"Результат: {value}"

def evaluate_duel(game_type: str, val1: int, val2: int) -> int:
    """
    Честный судейский подсчет победителя:
    Возвращает:
      1  — победил Игрок 1
     -1  — победил Игрок 2
      0  — ничья
    """
    if game_type == "football":
        goal1 = val1 in (3, 4, 5)
        goal2 = val2 in (3, 4, 5)
        if goal1 and not goal2:
            return 1
        elif goal2 and not goal1:
            return -1
        elif not goal1 and not goal2:
            return 0  # Оба промазали — ничья 0:0
        else:
            # Оба забили — сравниваем точность (девятка 5 бьет обычный гол 3, 4)
            if val1 > val2:
                return 1
            elif val2 > val1:
                return -1
            return 0

    elif game_type == "basketball":
        in1 = val1 in (4, 5)
        in2 = val2 in (4, 5)
        if in1 and not in2:
            return 1
        elif in2 and not in1:
            return -1
        elif not in1 and not in2:
            return 0  # Оба промазали
        else:
            if val1 > val2:
                return 1
            elif val2 > val1:
                return -1
            return 0

    elif game_type == "darts":
        pts = {1: 0, 2: 10, 3: 15, 4: 25, 5: 35, 6: 50}
        p1 = pts.get(val1, val1)
        p2 = pts.get(val2, val2)
        if p1 > p2:
            return 1
        elif p2 > p1:
            return -1
        return 0

    elif game_type == "bowling":
        pins = {1: 0, 2: 1, 3: 3, 4: 4, 5: 5, 6: 10}
        p1 = pins.get(val1, val1)
        p2 = pins.get(val2, val2)
        if p1 > p2:
            return 1
        elif p2 > p1:
            return -1
        return 0

    elif game_type == "slots":
        rank1 = 100 if val1 == 64 else (50 if val1 in (1, 22, 43) else val1)
        rank2 = 100 if val2 == 64 else (50 if val2 in (1, 22, 43) else val2)
        if rank1 > rank2:
            return 1
        elif rank2 > rank1:
            return -1
        return 0

    # По умолчанию (кости 🎲)
    if val1 > val2:
        return 1
    elif val2 > val1:
        return -1
    return 0


# ==========================================
# 1. ВЫБОР ИГРЫ И СОЗДАНИЕ ДУЭЛИ
# ==========================================

@router.callback_query(F.data == "menu_duels")
async def cb_menu_duels(callback: CallbackQuery):
    note = ""
    if callback.message.chat.type == "private":
        note = "\n\n💡 <i>Для дуэлей с другими участниками добавьте бота в ваш чат и пишите /duel прямо там!</i>"

    await callback.message.edit_text(
        f"⚔️ <b>Выберите дисциплину для дуэли:</b>\n\n"
        f"Вы бросаете вызов участникам чата. Кто примет бой — сразится с вами на ставку!{note}",
        reply_markup=games_selection_keyboard(mode="duel"),
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data == "menu_solo")
async def cb_menu_solo(callback: CallbackQuery):
    await callback.message.edit_text(
        "🎲 <b>Выберите игру против бота:</b>\n\n"
        "Сразитесь с ботом Optimus Gang 1 на 1 и удвойте свою ставку!",
        reply_markup=games_selection_keyboard(mode="solo"),
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data.startswith("duel_game:"))
async def cb_duel_game_selected(callback: CallbackQuery):
    game_type = callback.data.split(":")[1]
    user = await get_or_create_user(callback.from_user.id, callback.from_user.username, callback.from_user.full_name)

    game_title = GAME_NAMES.get(game_type, "Игру")
    text = bet_prompt_text(game_title, user["balance"], "duel")
    await callback.message.edit_text(
        text,
        reply_markup=bet_selection_keyboard(mode="duel", game_type=game_type, user_balance=user["balance"]),
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data.startswith("solo_game:"))
async def cb_solo_game_selected(callback: CallbackQuery):
    game_type = callback.data.split(":")[1]
    user = await get_or_create_user(callback.from_user.id, callback.from_user.username, callback.from_user.full_name)

    game_title = GAME_NAMES.get(game_type, "Игру")
    text = bet_prompt_text(game_title, user["balance"], "solo")
    await callback.message.edit_text(
        text,
        reply_markup=bet_selection_keyboard(mode="solo", game_type=game_type, user_balance=user["balance"]),
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data.startswith("set_bet:"))
async def cb_set_bet(callback: CallbackQuery, bot: Bot):
    parts = callback.data.split(":")
    if len(parts) != 4 or parts[1] not in {"solo", "duel"} or parts[2] not in GAME_EMOJIS:
        await callback.answer("Эта игровая кнопка устарела. Открой игру заново.", show_alert=True)
        return
    mode = parts[1]
    game_type = parts[2]
    try:
        bet = int(parts[3])
    except ValueError:
        await callback.answer("Некорректная ставка.", show_alert=True)
        return

    user = await get_user(callback.from_user.id)
    if not user or user["balance"] < bet or bet <= 0:
        await callback.answer("❌ Недостаточно средств на балансе!", show_alert=True)
        return

    game_emoji = get_game_emoji(game_type)
    game_title = GAME_NAMES.get(game_type, "Игру")

    if mode == "solo":
        # Игра против бота
        if not await spend_balance(callback.from_user.id, bet):
            await callback.answer("Баланс изменился — обнови игру и выбери ставку снова.", show_alert=True)
            return
        await callback.message.edit_text(
            f"🎲 <b>Раунд против бота начался!</b>\n"
            f"Дисциплина: {game_title}\n"
            f"Ставка: {bet} 🪙 (Возможный выигрыш: {bet * 2} 🪙)\n\n"
            f"⏳ Бросаем снаряд игрока {callback.from_user.full_name}...",
            parse_mode="HTML"
        )

        chat_id = callback.message.chat.id

        # Бросок игрока
        user_dice = await bot.send_dice(chat_id=chat_id, emoji=game_emoji)
        user_val = user_dice.dice.value
        await asyncio.sleep(3.5)

        # Бросок бота
        await bot.send_message(chat_id, f"🤖 Теперь ход бота {SHOP_NAME}...")
        bot_dice = await bot.send_dice(chat_id=chat_id, emoji=game_emoji)
        bot_val = bot_dice.dice.value
        await asyncio.sleep(3.5)

        # Определение победителя
        u_desc = describe_roll(game_type, user_val)
        b_desc = describe_roll(game_type, bot_val)
        outcome = evaluate_duel(game_type, user_val, bot_val)

        if outcome == 1:
            win_amount = bet * 2
            await update_balance(callback.from_user.id, win_amount)
            res_text = (
                f"🎉 <b>ПОБЕДА!</b> 🎉\n\n"
                f"👤 Ты: {u_desc}\n"
                f"🤖 Бот: {b_desc}\n\n"
                f"💰 Твой выигрыш: <b>+{bet * 2}</b> 🪙!\n"
                f"Поздравляем бойца {SHOP_NAME}!"
            )
        elif outcome == -1:
            res_text = (
                f"💀 <b>ПОРАЖЕНИЕ!</b> 💀\n\n"
                f"👤 Ты: {u_desc}\n"
                f"🤖 Бот: {b_desc}\n\n"
                f"Ставка <b>{bet} 🪙</b> уходит в банк казино.\n"
                f"Не унывай, отыграйся в следующем раунде!"
            )
        else:
            # Ничья
            await update_balance(callback.from_user.id, bet)
            res_text = (
                f"🤝 <b>НИЧЬЯ!</b> 🤝\n\n"
                f"👤 Ты: {u_desc}\n"
                f"🤖 Бот: {b_desc}\n\n"
                f"Ставка <b>{bet} 🪙</b> возвращена на твой баланс."
            )

        if outcome == 1:
            taunt = (await get_user_decorations(callback.from_user.id)).get("taunt")
            if taunt:
                res_text += f"\n\n{html.escape(taunt)}"

        await bot.send_message(chat_id, res_text, reply_markup=back_to_menu_keyboard(), parse_mode="HTML")
        await callback.answer()

    elif mode == "duel":
        if callback.message.chat.type == "private":
            await callback.answer(
                "💡 Создавать дуэли нужно в групповом чате! Добавьте бота в ваш чат Optimus Gang и создайте вызов через /duel.",
                show_alert=True
            )
            return

        # Создание дуэли в текущем чате
        duel_msg = await bot.send_message(
            chat_id=callback.message.chat.id,
            text=(
                f"🔥 <b>[{SHOP_NAME}] ВЫЗОВ НА ДУЭЛЬ!</b> 🔥\n\n"
                f"👤 <b>Инициатор:</b> {callback.from_user.mention_html()}\n"
                f"🎮 <b>Дисциплина:</b> {game_title}\n"
                f"💰 <b>Ставка:</b> <code>{bet}</code> 🪙\n"
                f"🏆 <b>Банк победителя:</b> <code>{bet * 2}</code> 🪙\n\n"
                f"<i>Кто осмелится принять бой? Нажмите кнопку ниже!</i>"
            ),
            reply_markup=duel_invitation_keyboard(0, bet),
            parse_mode="HTML"
        )

        duel_id = await create_duel(
            chat_id=callback.message.chat.id,
            creator_id=callback.from_user.id,
            creator_name=user.get("nickname") or callback.from_user.full_name,
            game_type=game_type,
            bet=bet,
            message_id=duel_msg.message_id
        )
        if not duel_id:
            await duel_msg.edit_text(
                "❌ Вызов не создан: баланс изменился или средств не хватает. Попробуй снова."
            )
            await callback.answer("Ставка не списана.", show_alert=True)
            return

        # Обновляем кнопку с правильным duel_id
        await duel_msg.edit_reply_markup(reply_markup=duel_invitation_keyboard(duel_id, bet))

        # Уведомляем создателя
        await callback.answer("✅ Вызов создан и отправлен в чат!", show_alert=False)


# ==========================================
# 2. ПРИНЯТИЕ И ОТМЕНА ДУЭЛИ
# ==========================================

@router.callback_query(F.data.startswith("accept_duel:"))
async def cb_accept_duel(callback: CallbackQuery, bot: Bot):
    duel_id = int(callback.data.split(":")[1])
    duel = await get_duel(duel_id)

    if not duel or duel["status"] != "waiting":
        await callback.answer("❌ Дуэль уже недействительна или завершена!", show_alert=True)
        return

    if callback.from_user.id == duel["creator_id"]:
        await callback.answer("❌ Вы не можете принять собственный вызов!", show_alert=True)
        return

    # Проверяем баланс оппонента
    user = await get_or_create_user(callback.from_user.id, callback.from_user.username, callback.from_user.full_name)
    opponent_name = user.get("nickname") or callback.from_user.full_name
    opponent_display_name = html.escape(opponent_name)
    if user["balance"] < duel["bet"]:
        await callback.answer(f"❌ Недостаточно монет! Требуется {duel['bet']} 🪙, у вас {user['balance']} 🪙.", show_alert=True)
        return

    # Списываем ставку и переводим дуэль в статус playing
    success = await accept_duel(duel_id, callback.from_user.id, opponent_name)
    if not success:
        await callback.answer("❌ Не удалось принять: дуэль занята или не хватает монет.", show_alert=True)
        return

    await callback.answer("⚔️ Вы приняли вызов! Да начнется битва!")

    game_type = duel["game_type"]
    game_emoji = get_game_emoji(game_type)
    game_title = GAME_NAMES.get(game_type, "Игру")
    chat_id = duel["chat_id"]
    creator_display_name = html.escape(duel["creator_name"])

    # Обновляем сообщение дуэли
    await callback.message.edit_text(
        f"⚔️ <b>ДУЭЛЬ НАЧАЛАСЬ!</b> ⚔️\n\n"
        f"🔴 <b>Игрок 1:</b> {creator_display_name}\n"
        f"🔵 <b>Игрок 2:</b> {opponent_display_name}\n"
        f"🎮 <b>Дисциплина:</b> {game_title}\n"
        f"💰 <b>Банк на кону:</b> <code>{duel['bet'] * 2}</code> 🪙\n\n"
        f"<i>Приготовьтесь, судья разыгрывает снаряды...</i>",
        parse_mode="HTML"
    )

    await asyncio.sleep(2)

    # 1. Бросок Создателя
    await bot.send_message(chat_id, f"🔴 Бросок игрока <b>{creator_display_name}</b>:", parse_mode="HTML")
    d1 = await bot.send_dice(chat_id=chat_id, emoji=game_emoji)
    val1 = d1.dice.value
    await asyncio.sleep(3.5)

    # 2. Бросок Оппонента
    await bot.send_message(chat_id, f"🔵 Бросок игрока <b>{opponent_display_name}</b>:", parse_mode="HTML")
    d2 = await bot.send_dice(chat_id=chat_id, emoji=game_emoji)
    val2 = d2.dice.value
    await asyncio.sleep(3.5)

    # Результаты
    desc1 = describe_roll(game_type, val1)
    desc2 = describe_roll(game_type, val2)
    outcome = evaluate_duel(game_type, val1, val2)

    if outcome == 1:
        # Победил Создатель
        await record_duel_result(duel_id, duel["creator_id"], False, duel["creator_id"], callback.from_user.id, duel["bet"])
        res_text = (
            f"🏆 <b>ПОБЕДА ИГРОКА 1!</b> 🏆\n\n"
            f"🔴 <b>{creator_display_name}:</b> {desc1}\n"
            f"🔵 <b>{opponent_display_name}:</b> {desc2}\n\n"
            f"🎉 <b>{creator_display_name}</b> забирает весь банк <b>+{duel['bet'] * 2} 🪙</b>!\n"
            f"Красивая победа в клубе {SHOP_NAME}! 🔥"
        )
    elif outcome == -1:
        # Победил Оппонент
        await record_duel_result(duel_id, callback.from_user.id, False, duel["creator_id"], callback.from_user.id, duel["bet"])
        res_text = (
            f"🏆 <b>ПОБЕДА ИГРОКА 2!</b> 🏆\n\n"
            f"🔴 <b>{creator_display_name}:</b> {desc1}\n"
            f"🔵 <b>{opponent_display_name}:</b> {desc2}\n\n"
            f"🎉 <b>{opponent_display_name}</b> забирает весь банк <b>+{duel['bet'] * 2} 🪙</b>!\n"
            f"Красивая победа в клубе {SHOP_NAME}! 🔥"
        )
    else:
        # Ничья
        await record_duel_result(duel_id, None, True, duel["creator_id"], callback.from_user.id, duel["bet"])
        res_text = (
            f"🤝 <b>БОЕВАЯ НИЧЬЯ!</b> 🤝\n\n"
            f"🔴 <b>{creator_display_name}:</b> {desc1}\n"
            f"🔵 <b>{opponent_display_name}:</b> {desc2}\n\n"
            f"Оба бойца показали равный результат. Ставки возвращены участникам!"
        )

    winner_id = duel["creator_id"] if outcome == 1 else callback.from_user.id if outcome == -1 else None
    if winner_id:
        taunt = (await get_user_decorations(winner_id)).get("taunt")
        if taunt:
            res_text += f"\n\n{html.escape(taunt)}"

    await bot.send_message(chat_id, res_text, parse_mode="HTML")

@router.callback_query(F.data.startswith("cancel_duel:"))
async def cb_cancel_duel(callback: CallbackQuery):
    duel_id = int(callback.data.split(":")[1])
    duel = await get_duel(duel_id)

    if not duel or duel["status"] != "waiting":
        await callback.answer("❌ Дуэль уже недействительна!", show_alert=True)
        return

    if callback.from_user.id != duel["creator_id"]:
        await callback.answer("❌ Только создатель может отменить вызов!", show_alert=True)
        return

    await cancel_duel(duel_id)
    await callback.message.edit_text(
        f"❌ <b>Дуэль #{duel_id} отменена создателем.</b>\n"
        f"Ставка <code>{duel['bet']}</code> 🪙 возвращена на баланс.",
        parse_mode="HTML"
    )
    await callback.answer("Дуэль успешно отменена.")


# ==========================================
# 3. БЫСТРАЯ КОМАНДА /duel В ЧАТЕ
# ==========================================

@router.message(Command("duel"))
async def cmd_duel(message: Message, bot: Bot):
    args = message.text.split()[1:]
    bet = 50
    if args and args[0].isdigit():
        bet = int(args[0])

    user = await get_or_create_user(message.from_user.id, message.from_user.username, message.from_user.full_name)
    if user["balance"] < bet or bet <= 0:
        await message.reply(f"❌ Недостаточно средств на балансе! Твой баланс: {user['balance']} 🪙.")
        return

    # Отправляем меню выбора игры для дуэли
    await message.reply(
        f"⚔️ <b>Создание дуэли на ставку {bet} 🪙</b>\n"
        f"Выберите дисциплину:",
        reply_markup=games_selection_keyboard(mode="duel"),
        parse_mode="HTML"
    )


# ==========================================
# 4. РЕАКЦИЯ НА БРОСКИ СТИКЕРОВ-ЭМОДЗИ В ЧАТЕ
# ==========================================

@router.message(F.dice)
async def handle_chat_dice(message: Message):
    """
    Перехватывает официальные эмодзи-кости Telegram (⚽, 🏀, 🎯, 🎳, 🎲, 🎰) прямо в чате.
    Начисляет награды за красивые попадания и джекпоты!
    """
    user_id = message.from_user.id
    now = time.time()
    await get_or_create_user(user_id, message.from_user.username, message.from_user.full_name)
    from handlers.roulette import handle_active_turn_dice

    if await handle_active_turn_dice(message):
        return

    # Анти-спам проверка (1 бросок в 8 секунд для начисления наград)
    last_reward = dice_cooldowns.get(user_id)
    if last_reward is not None:
        if now - last_reward < 8:
            dice_cooldowns.pop(user_id)
            dice_cooldowns[user_id] = last_reward
            return
        dice_cooldowns.pop(user_id, None)

    dice = message.dice
    emoji = dice.emoji
    value = dice.value

    reward = 0
    congrats = ""

    if emoji == "⚽":
        if value == 5:
            reward = 15
            congrats = f"⚽🔥🔥 <b>ГОООЛ В ДЕВЯТКУ!</b> Шедевральный удар от {message.from_user.mention_html()}! (+15 🪙 в {SHOP_NAME})"
        elif value in (3, 4):
            reward = 5
            congrats = f"⚽ <b>ГОООЛ!</b> Точный мяч в сетку от {message.from_user.mention_html()}! (+5 🪙)"
    elif emoji == "🏀":
        if value == 5:
            reward = 15
            congrats = f"🏀🔥 <b>ЧИСТОЕ ПОПАДАНИЕ!</b> Идеальный трехочковый бросок от {message.from_user.mention_html()}! (+15 🪙)"
        elif value == 4:
            reward = 5
            congrats = f"🏀 <b>Мяч в корзине!</b> Меткий бросок от {message.from_user.mention_html()}! (+5 🪙)"
    elif emoji == "🎯":
        if value == 6:
            reward = 30
            congrats = f"🎯🎯🎯 <b>В САМОЕ ЯБЛОЧКО!</b> Абсолютный снайпер {message.from_user.mention_html()}! (+30 🪙)"
        elif value in (4, 5):
            reward = 5
            congrats = f"🎯 <b>Точно в цель!</b> Хороший выстрел от {message.from_user.mention_html()}! (+5 🪙)"
    elif emoji == "🎳":
        if value == 6:
            reward = 30
            congrats = f"🎳💥 <b>СТРАЙК!</b> Все кегли снесены под ноль! Мощь от {message.from_user.mention_html()}! (+30 🪙)"
    elif emoji == "🎲":
        if value == 6:
            reward = 10
            congrats = f"🎲 <b>ШЕСТЕРКА!</b> Максимальный кубик от {message.from_user.mention_html()}! (+10 🪙)"
    elif emoji == "🎰":
        if value == 64:
            reward = 100
            congrats = f"🎰🔥🔥 <b>ДЖЕКПОТ 777!</b> Невероятный куш сорвал {message.from_user.mention_html()}! (+100 🪙 в {SHOP_NAME})"
        elif value in (1, 22, 43):
            reward = 25
            congrats = f"🎰 <b>Три в ряд!</b> Выигрышная линия от {message.from_user.mention_html()}! (+25 🪙)"

    if reward > 0:
        dice_cooldowns.pop(user_id, None)
        dice_cooldowns[user_id] = now
        if len(dice_cooldowns) > MAX_DICE_COOLDOWNS:
            dice_cooldowns.pop(next(iter(dice_cooldowns)))
        await update_balance(user_id, reward)
        # Ждем 3.5 секунды пока проиграется анимация стикера
        await asyncio.sleep(3.5)
        await message.reply(congrats, parse_mode="HTML")
