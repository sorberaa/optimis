from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from config import SHOP_NAME
from database import get_or_create_user, claim_daily_bonus, get_top_players, get_user_badge
from keyboards.inline import profile_keyboard, top_keyboard, back_to_menu_keyboard

router = Router()

@router.message(Command("profile", "me", "stats"))
async def cmd_profile(message: Message):
    user = await get_or_create_user(message.from_user.id, message.from_user.username, message.from_user.full_name)
    badge = await get_user_badge(message.from_user.id)
    badge_text = f"Титул: <b>{badge}</b>\n" if badge else ""

    total = user["total_games"]
    wins = user["wins"]
    winrate = round((wins / total * 100), 1) if total > 0 else 0

    text = (
        f"👤 <b>Профиль:</b> {message.from_user.mention_html()}\n"
        f"{badge_text}"
        f"💰 <b>Баланс:</b> <code>{user['balance']}</code> 🪙\n"
        f"🏆 <b>Игры:</b> {total} (Побед: {wins} | Винрейт: {winrate}%)"
    )
    await message.answer(text, reply_markup=profile_keyboard(), parse_mode="HTML")

@router.callback_query(F.data == "profile")
async def cb_profile(callback: CallbackQuery):
    user = await get_or_create_user(callback.from_user.id, callback.from_user.username, callback.from_user.full_name)
    badge = await get_user_badge(callback.from_user.id)
    badge_text = f"Титул: <b>{badge}</b>\n" if badge else ""

    total = user["total_games"]
    wins = user["wins"]
    winrate = round((wins / total * 100), 1) if total > 0 else 0

    text = (
        f"👤 <b>Профиль:</b> {callback.from_user.mention_html()}\n"
        f"{badge_text}"
        f"💰 <b>Баланс:</b> <code>{user['balance']}</code> 🪙\n"
        f"🏆 <b>Игры:</b> {total} (Побед: {wins} | Винрейт: {winrate}%)"
    )
    await callback.message.edit_text(text, reply_markup=profile_keyboard(), parse_mode="HTML")
    await callback.answer()

@router.message(Command("bonus"))
async def cmd_bonus(message: Message):
    await get_or_create_user(message.from_user.id, message.from_user.username, message.from_user.full_name)
    success, amount_or_bal, msg = await claim_daily_bonus(message.from_user.id)

    if success:
        await message.answer(f"🎁 <b>Бонус получен!</b> +{amount_or_bal} 🪙 на ваш баланс.", parse_mode="HTML")
    else:
        await message.answer(f"⏳ Следующий бонус через: <b>{msg}</b>.", parse_mode="HTML")

@router.callback_query(F.data == "bonus")
async def cb_bonus(callback: CallbackQuery):
    await get_or_create_user(callback.from_user.id, callback.from_user.username, callback.from_user.full_name)
    success, amount_or_bal, msg = await claim_daily_bonus(callback.from_user.id)

    if success:
        await callback.message.edit_text(
            f"🎁 <b>Бонус получен!</b> +{amount_or_bal} 🪙 на баланс.",
            reply_markup=back_to_menu_keyboard(),
            parse_mode="HTML"
        )
        await callback.answer("Бонус начислен!")
    else:
        await callback.answer(f"⏳ Бонус уже получен. До следующего: {msg}", show_alert=True)

@router.message(Command("top"))
async def cmd_top(message: Message):
    players = await get_top_players(limit=10, by="balance")
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]

    lines = []
    for i, p in enumerate(players):
        medal = medals[i] if i < len(medals) else f"{i+1}."
        name = p["username"] if p["username"] else p["full_name"]
        lines.append(f"{medal} <b>{name}</b> — <code>{p['balance']}</code> 🪙 (побед: {p['wins']})")

    content = "\n".join(lines) if lines else "Пока нет игроков в рейтинге."
    text = f"🏆 <b>Топ игроков {SHOP_NAME}:</b>\n\n{content}"
    await message.answer(text, reply_markup=top_keyboard(), parse_mode="HTML")

@router.callback_query(F.data.in_(["top_balance", "top_wins"]))
async def cb_top(callback: CallbackQuery):
    by = "balance" if callback.data == "top_balance" else "wins"
    title_suffix = "Балансу" if by == "balance" else "Победам"
    players = await get_top_players(limit=10, by=by)
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]

    lines = []
    for i, p in enumerate(players):
        medal = medals[i] if i < len(medals) else f"{i+1}."
        name = p["username"] if p["username"] else p["full_name"]
        if by == "balance":
            lines.append(f"{medal} <b>{name}</b> — <code>{p['balance']}</code> 🪙")
        else:
            lines.append(f"{medal} <b>{name}</b> — <b>{p['wins']} побед</b>")

    content = "\n".join(lines) if lines else "Пока нет игроков в рейтинге."
    text = f"🏆 <b>Топ игроков по {title_suffix}:</b>\n\n{content}"
    await callback.message.edit_text(text, reply_markup=top_keyboard(), parse_mode="HTML")
    await callback.answer()
