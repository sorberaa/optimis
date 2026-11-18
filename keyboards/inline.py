from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from typing import List, Dict, Any

def main_menu_keyboard(is_chat: bool = False) -> InlineKeyboardMarkup:
    """Главное меню бота."""
    buttons = [
        [
            InlineKeyboardButton(text="⚔️ Создать дуэль", callback_data="menu_duels"),
            InlineKeyboardButton(text="🎲 Игра против бота", callback_data="menu_solo")
        ],
        [
            InlineKeyboardButton(text="👤 Мой профиль", callback_data="profile"),
            InlineKeyboardButton(text="🎁 Бонус дня", callback_data="bonus")
        ],
        [
            InlineKeyboardButton(text="🛍 Магазин приколов", callback_data="shop"),
            InlineKeyboardButton(text="🏆 Топ игроков", callback_data="top_balance")
        ],
        [
            InlineKeyboardButton(text="🐉 Вырастить дракона", callback_data="dragon")
        ],
        [
            InlineKeyboardButton(text="📜 Правила и помощь", callback_data="help")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def games_selection_keyboard(mode: str = "duel") -> InlineKeyboardMarkup:
    """
    Выбор игры.
    mode: 'duel' (для вызова игрока) или 'solo' (для одиночной игры против бота)
    """
    prefix = "duel_game" if mode == "duel" else "solo_game"
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
            InlineKeyboardButton(text="🎰 Слоты 777", callback_data=f"{prefix}:slots")
        ],
        [
            InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="back_main")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def bet_selection_keyboard(mode: str, game_type: str, user_balance: int) -> InlineKeyboardMarkup:
    """Показывает только ставки, доступные игроку."""
    affordable = [bet for bet in (25, 50, 100, 250, 500) if bet <= user_balance]
    buttons = [
        [
            InlineKeyboardButton(
                text=f"{bet} 🪙",
                callback_data=f"set_bet:{mode}:{game_type}:{bet}"
            )
            for bet in affordable[index:index + 3]
        ]
        for index in range(0, len(affordable), 3)
    ]

    if user_balance > 0 and user_balance not in affordable:
        buttons.append([
            InlineKeyboardButton(
                text=f"🔥 Ва-банк ({user_balance} 🪙)",
                callback_data=f"set_bet:{mode}:{game_type}:{user_balance}"
            )
        ])
    elif user_balance <= 0:
        buttons.append([
            InlineKeyboardButton(text="🎁 Забрать бонус", callback_data="bonus")
        ])

    buttons.append([InlineKeyboardButton(text="⬅️ Назад к играм", callback_data=f"menu_{mode}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def duel_invitation_keyboard(duel_id: int, bet: int) -> InlineKeyboardMarkup:
    """Кнопки в сообщении активной дуэли."""
    buttons = [
        [
            InlineKeyboardButton(text=f"⚔️ Принять вызов ({bet} 🪙)", callback_data=f"accept_duel:{duel_id}")
        ],
        [
            InlineKeyboardButton(text="❌ Отменить дуэль", callback_data=f"cancel_duel:{duel_id}")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def shop_keyboard(items: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    """Клавиатура магазина Optimus Gang."""
    buttons = []
    for item in items:
        buttons.append([
            InlineKeyboardButton(
                text=f"{item['title']} — {item['price']} 🪙",
                callback_data=f"shop_buy:{item['id']}"
            )
        ])
    buttons.append([
        InlineKeyboardButton(text="🎒 Мои эффекты", callback_data="my_purchases"),
        InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main")
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def profile_keyboard() -> InlineKeyboardMarkup:
    """Кнопки в окне профиля."""
    buttons = [
        [
            InlineKeyboardButton(text="🎁 Забрать бонус", callback_data="bonus"),
            InlineKeyboardButton(text="🛍 В магазин", callback_data="shop"),
            InlineKeyboardButton(text="🐉 Дракон", callback_data="dragon")
        ],
        [
            InlineKeyboardButton(text="⬅️ Главное меню", callback_data="back_main")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def top_keyboard() -> InlineKeyboardMarkup:
    """Переключение топа (по балансу / по победам)."""
    buttons = [
        [
            InlineKeyboardButton(text="💰 По балансу", callback_data="top_balance"),
            InlineKeyboardButton(text="🏆 По победам", callback_data="top_wins")
        ],
        [
            InlineKeyboardButton(text="⬅️ Главное меню", callback_data="back_main")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def back_to_menu_keyboard() -> InlineKeyboardMarkup:
    """Кнопка возврата в главное меню."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Главное меню", callback_data="back_main")]
    ])
