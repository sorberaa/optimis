import aiosqlite
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from config import DB_PATH, START_BALANCE, DAILY_BONUS, ADMIN_IDS

async def init_db():
    """Инициализация таблиц базы данных и базовых товаров магазина."""
    async with aiosqlite.connect(DB_PATH) as db:
        # Таблица игроков
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                balance INTEGER DEFAULT 200,
                wins INTEGER DEFAULT 0,
                losses INTEGER DEFAULT 0,
                draws INTEGER DEFAULT 0,
                total_games INTEGER DEFAULT 0,
                last_bonus TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Таблица дуэлей в чате
        await db.execute("""
            CREATE TABLE IF NOT EXISTS duels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                creator_id INTEGER NOT NULL,
                creator_name TEXT NOT NULL,
                opponent_id INTEGER,
                opponent_name TEXT,
                game_type TEXT NOT NULL,
                bet INTEGER NOT NULL,
                creator_score INTEGER,
                opponent_score INTEGER,
                status TEXT DEFAULT 'waiting',
                winner_id INTEGER,
                message_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Таблица администраторов
        await db.execute("""
            CREATE TABLE IF NOT EXISTS admins (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                added_by INTEGER,
                is_superadmin INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Таблица товаров магазина
        await db.execute("""
            CREATE TABLE IF NOT EXISTS shop_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                price INTEGER NOT NULL,
                item_type TEXT DEFAULT 'promocode',
                content TEXT NOT NULL,
                is_active INTEGER DEFAULT 1
            )
        """)

        # Таблица покупок
        await db.execute("""
            CREATE TABLE IF NOT EXISTS purchases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                item_id INTEGER NOT NULL,
                item_title TEXT NOT NULL,
                content TEXT NOT NULL,
                purchased_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Таблица массовых рулеток / турниров в чате
        await db.execute("""
            CREATE TABLE IF NOT EXISTS roulettes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                creator_id INTEGER NOT NULL,
                game_type TEXT NOT NULL,
                prize TEXT NOT NULL,
                max_players INTEGER NOT NULL,
                entry_fee INTEGER DEFAULT 0,
                status TEXT DEFAULT 'registration',
                message_id INTEGER DEFAULT 0,
                winner_id INTEGER,
                winner_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Таблица участников рулетки
        await db.execute("""
            CREATE TABLE IF NOT EXISTS roulette_players (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                roulette_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                username TEXT,
                full_name TEXT NOT NULL,
                roll_value INTEGER,
                score INTEGER,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(roulette_id, user_id)
            )
        """)

        # Добавим колонку badge в users если её ещё нет
        try:
            await db.execute("ALTER TABLE users ADD COLUMN badge TEXT DEFAULT ''")
        except Exception:
            pass

        # Обновим товары в магазине: убираем скидки/промокоды, ставим стикеры и приколы к нику
        await db.execute("DELETE FROM shop_items WHERE item_type = 'promocode'")

        async with db.execute("SELECT COUNT(*) FROM shop_items") as cursor:
            count = (await cursor.fetchone())[0]

        if count == 0:
            badge_items = [
                ("🕶 [Блатной]", "Прикольный значок к нику в рулетках", 150, "badge", "🕶 [Блатной]"),
                ("🎯 [Снайпер]", "Стикер меткого стрелка в играх", 250, "badge", "🎯 [Снайпер]"),
                ("⚽ [Форвард Gang]", "Футбольный статус бомбардира", 250, "badge", "⚽ [Форвард Gang]"),
                ("⚡ [Гроза рулеток]", "Грозный титул в чат-играх", 400, "badge", "⚡ [Гроза рулеток]"),
                ("🎰 [Фартовый]", "Статус главного везунчика клуба", 400, "badge", "🎰 [Фартовый]"),
                ("💀 [Головорез]", "Опасный боевой статус в чате", 600, "badge", "💀 [Головорез]"),
                ("💎 [VIP Gang]", "Премиум статус в турнирах и профиле", 800, "badge", "💎 [VIP Gang]"),
                ("👑 [Шеф Gang]", "Высший авторитет Optimus Gang", 1200, "badge", "👑 [Шеф Gang]")
            ]
            await db.executemany(
                "INSERT INTO shop_items (title, description, price, item_type, content) VALUES (?, ?, ?, ?, ?)",
                badge_items
            )

        # Синхронизация администраторов из .env ADMIN_IDS
        for admin_id in ADMIN_IDS:
            await db.execute(
                "INSERT OR IGNORE INTO admins (user_id, username, added_by, is_superadmin) VALUES (?, 'Owner', 0, 1)",
                (admin_id,)
            )

        await db.commit()

# ==========================================
# ПОЛЬЗОВАТЕЛИ И БАЛАНС
# ==========================================

async def get_or_create_user(user_id: int, username: Optional[str], full_name: str) -> Dict[str, Any]:
    """Получает пользователя из БД или регистрирует нового с приветственным балансом."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                if row["username"] != username or row["full_name"] != full_name:
                    await db.execute(
                        "UPDATE users SET username = ?, full_name = ? WHERE user_id = ?",
                        (username, full_name, user_id)
                    )
                    await db.commit()
                return dict(row)

        await db.execute(
            """INSERT INTO users (user_id, username, full_name, balance)
               VALUES (?, ?, ?, ?)""",
            (user_id, username, full_name, START_BALANCE)
        )
        await db.commit()

        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
            new_row = await cursor.fetchone()
            return dict(new_row)

async def get_user(user_id: int) -> Optional[Dict[str, Any]]:
    """Получает пользователя по ID."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

async def update_balance(user_id: int, amount: int) -> int:
    """Изменяет баланс пользователя (amount может быть отрицательным) и возвращает новый баланс."""
    if user_id <= 0:
        return 0
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
        await db.commit()
        async with db.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0

async def claim_daily_bonus(user_id: int) -> tuple[bool, int, Optional[str]]:
    """Получение ежедневного бонуса раз в 24 часа."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT balance, last_bonus FROM users WHERE user_id = ?", (user_id,)) as cursor:
            user = await cursor.fetchone()
            if not user:
                return False, 0, "Пользователь не найден."

        last_bonus_str = user["last_bonus"]
        now = datetime.now()

        if last_bonus_str:
            try:
                last_bonus_time = datetime.fromisoformat(last_bonus_str)
                time_passed = now - last_bonus_time
                if time_passed < timedelta(hours=24):
                    remaining = timedelta(hours=24) - time_passed
                    hours, remainder = divmod(int(remaining.total_seconds()), 3600)
                    minutes, _ = divmod(remainder, 60)
                    return False, user["balance"], f"{hours} ч. {minutes} мин."
            except Exception:
                pass

        new_balance = user["balance"] + DAILY_BONUS
        await db.execute(
            "UPDATE users SET balance = ?, last_bonus = ? WHERE user_id = ?",
            (new_balance, now.isoformat(), user_id)
        )
        await db.commit()
        return True, DAILY_BONUS, None

# ==========================================
# УПРАВЛЕНИЕ АДМИНИСТРАТОРАМИ
# ==========================================

async def is_admin(user_id: int) -> bool:
    """Проверяет, является ли пользователь администратором."""
    if not ADMIN_IDS:
        # Если ADMIN_IDS в .env пуст, проверим, есть ли хоть один админ в БД
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT COUNT(*) FROM admins") as cur:
                count = (await cur.fetchone())[0]
            if count == 0:
                # Первому пользователю временно разрешено
                return True
            async with db.execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,)) as cur:
                return (await cur.fetchone()) is not None

    if user_id in ADMIN_IDS:
        return True

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,)) as cursor:
            return (await cursor.fetchone()) is not None

async def is_superadmin(user_id: int) -> bool:
    """Проверяет, является ли пользователь главным админом (владельцем)."""
    if not ADMIN_IDS:
        return True
    if user_id in ADMIN_IDS:
        return True
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT is_superadmin FROM admins WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            return bool(row and row[0] == 1)

async def add_admin(user_id: int, username: Optional[str], added_by: int) -> bool:
    """Добавляет нового администратора бота."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO admins (user_id, username, added_by, is_superadmin) VALUES (?, ?, ?, 0)",
            (user_id, username or "Admin", added_by)
        )
        await db.commit()
        return True

async def remove_admin(user_id: int) -> bool:
    """Снимает права администратора."""
    if user_id in ADMIN_IDS:
        return False  # Нельзя удалить суперадмина из .env
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("DELETE FROM admins WHERE user_id = ? AND is_superadmin = 0", (user_id,))
        await db.commit()
        return cursor.rowcount > 0

async def get_all_admins() -> List[Dict[str, Any]]:
    """Возвращает список всех администраторов."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM admins ORDER BY is_superadmin DESC, created_at ASC") as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

# ==========================================
# ИГРОВЫЕ ДУЭЛИ В ЧАТЕ (АТОМАРНЫЕ ОПЕРАЦИИ)
# ==========================================

async def create_duel(chat_id: int, creator_id: int, creator_name: str, game_type: str, bet: int, message_id: int) -> int:
    """Создает запись дуэли и списывает ставку создателя."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (bet, creator_id))
        cursor = await db.execute(
            """INSERT INTO duels (chat_id, creator_id, creator_name, game_type, bet, message_id, status)
               VALUES (?, ?, ?, ?, ?, ?, 'waiting')""",
            (chat_id, creator_id, creator_name, game_type, bet, message_id)
        )
        duel_id = cursor.lastrowid
        await db.commit()
        return duel_id

async def get_duel(duel_id: int) -> Optional[Dict[str, Any]]:
    """Информация о дуэли."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM duels WHERE id = ?", (duel_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

async def cancel_duel(duel_id: int) -> bool:
    """Атомарно отменяет ожидающую дуэль и возвращает ставку создателю."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM duels WHERE id = ? AND status = 'waiting'", (duel_id,)) as cursor:
            duel = await cursor.fetchone()
            if not duel:
                return False

        # Атомарный перевод в cancelled
        cursor = await db.execute("UPDATE duels SET status = 'cancelled' WHERE id = ? AND status = 'waiting'", (duel_id,))
        if cursor.rowcount == 0:
            return False

        await db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (duel["bet"], duel["creator_id"]))
        await db.commit()
        return True

async def accept_duel(duel_id: int, opponent_id: int, opponent_name: str) -> bool:
    """
    Атомарно принимает дуэль (защита от race condition, когда двое жмут одновременно).
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM duels WHERE id = ? AND status = 'waiting'", (duel_id,)) as cursor:
            duel = await cursor.fetchone()
            if not duel:
                return False

        # Атомарно занимаем дуэль
        cursor = await db.execute(
            "UPDATE duels SET opponent_id = ?, opponent_name = ?, status = 'playing' WHERE id = ? AND status = 'waiting'",
            (opponent_id, opponent_name, duel_id)
        )
        if cursor.rowcount == 0:
            return False  # Кто-то другой уже нажал кнопку на миллисекунду раньше

        # Списываем ставку оппонента
        await db.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (duel["bet"], opponent_id))
        await db.commit()
        return True

async def record_duel_result(duel_id: int, winner_id: Optional[int], is_draw: bool, creator_id: int, opponent_id: int, bet: int):
    """Фиксирует результат дуэли в статистике игроков."""
    async with aiosqlite.connect(DB_PATH) as db:
        if is_draw:
            # Возврат ставок обоим игрокам
            await db.execute("UPDATE users SET balance = balance + ?, draws = draws + 1, total_games = total_games + 1 WHERE user_id = ?", (bet, creator_id))
            await db.execute("UPDATE users SET balance = balance + ?, draws = draws + 1, total_games = total_games + 1 WHERE user_id = ?", (bet, opponent_id))
            await db.execute("UPDATE duels SET status = 'finished', winner_id = NULL WHERE id = ?", (duel_id,))
        else:
            loser_id = opponent_id if winner_id == creator_id else creator_id
            # Победитель забирает банк (ставка * 2)
            await db.execute("UPDATE users SET balance = balance + ?, wins = wins + 1, total_games = total_games + 1 WHERE user_id = ?", (bet * 2, winner_id))
            await db.execute("UPDATE users SET losses = losses + 1, total_games = total_games + 1 WHERE user_id = ?", (loser_id,))
            await db.execute("UPDATE duels SET status = 'finished', winner_id = ? WHERE id = ?", (winner_id, duel_id))

        await db.commit()

async def get_top_players(limit: int = 10, by: str = "balance") -> List[Dict[str, Any]]:
    """Топ игроков по балансу или по количеству побед."""
    order_column = "balance" if by == "balance" else "wins"
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            f"SELECT user_id, username, full_name, balance, wins, total_games FROM users ORDER BY {order_column} DESC LIMIT ?",
            (limit,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

# ==========================================
# МАГАЗИН И ПОКУПКИ
# ==========================================

async def get_shop_items() -> List[Dict[str, Any]]:
    """Список активных товаров в магазине."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM shop_items WHERE is_active = 1") as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

async def get_shop_item(item_id: int) -> Optional[Dict[str, Any]]:
    """Информация о конкретном товаре."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM shop_items WHERE id = ? AND is_active = 1", (item_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

async def buy_item(user_id: int, item_id: int) -> tuple[bool, str, Optional[Dict[str, Any]]]:
    """Покупка товара в магазине Optimus Gang."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
            user = await cursor.fetchone()
            if not user:
                return False, "Пользователь не найден.", None

        async with db.execute("SELECT * FROM shop_items WHERE id = ? AND is_active = 1", (item_id,)) as cursor:
            item = await cursor.fetchone()
            if not item:
                return False, "Товар не найден или недоступен.", None

        if user["balance"] < item["price"]:
            return False, f"Недостаточно монет! Требуется {item['price']} 🪙, у вас {user['balance']} 🪙.", None

        await db.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (item["price"], user_id))

        # Если это значок/стикер к нику — сразу экипируем его
        if item["item_type"] == "badge":
            await db.execute("UPDATE users SET badge = ? WHERE user_id = ?", (item["content"], user_id))

        await db.execute(
            "INSERT INTO purchases (user_id, item_id, item_title, content) VALUES (?, ?, ?, ?)",
            (user_id, item["id"], item["title"], item["content"])
        )
        await db.commit()
        return True, "Успешная покупка!", dict(item)

async def get_user_badge(user_id: int) -> str:
    """Получает текущий значок/стикер пользователя к нику."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT badge FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row and row[0] else ""

async def get_user_purchases(user_id: int) -> List[Dict[str, Any]]:
    """История покупок пользователя."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM purchases WHERE user_id = ? ORDER BY id DESC LIMIT 15", (user_id,)) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

async def add_shop_item(title: str, description: str, price: int, item_type: str, content: str) -> int:
    """Добавление нового товара администратором."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO shop_items (title, description, price, item_type, content) VALUES (?, ?, ?, ?, ?)",
            (title, description, price, item_type, content)
        )
        await db.commit()
        return cursor.lastrowid

# ==========================================
# МАССОВЫЕ РУЛЕТКИ И ТУРНИРЫ ДЛЯ ЧАТА
# ==========================================

async def create_roulette(chat_id: int, creator_id: int, game_type: str, prize: str, max_players: int, entry_fee: int = 0) -> int:
    """Создает новую рулетку в чате."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """INSERT INTO roulettes (chat_id, creator_id, game_type, prize, max_players, entry_fee, status)
               VALUES (?, ?, ?, ?, ?, ?, 'registration')""",
            (chat_id, creator_id, game_type, prize, max_players, entry_fee)
        )
        roulette_id = cursor.lastrowid
        await db.commit()
        return roulette_id

async def set_roulette_message_id(roulette_id: int, message_id: int):
    """Обновляет message_id сообщения рулетки."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE roulettes SET message_id = ? WHERE id = ?", (message_id, roulette_id))
        await db.commit()

async def get_roulette(roulette_id: int) -> Optional[Dict[str, Any]]:
    """Получает информацию о рулетке."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM roulettes WHERE id = ?", (roulette_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

async def get_active_chat_roulette(chat_id: int) -> Optional[Dict[str, Any]]:
    """Получает текущую активную рулетку в чате."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM roulettes WHERE chat_id = ? AND status IN ('registration', 'playing') ORDER BY id DESC LIMIT 1",
            (chat_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

async def join_roulette(roulette_id: int, user_id: int, username: Optional[str], full_name: str) -> tuple[bool, str, int, int]:
    """
    Запись участника на рулетку.
    Возвращает (успех, сообщение, текущее_кол-во, макс_кол-во).
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM roulettes WHERE id = ?", (roulette_id,)) as cursor:
            roulette = await cursor.fetchone()
            if not roulette or roulette["status"] != "registration":
                return False, "Запись на эту рулетку закрыта!", 0, 0

        # Проверим, не записан ли уже
        async with db.execute("SELECT 1 FROM roulette_players WHERE roulette_id = ? AND user_id = ?", (roulette_id, user_id)) as cursor:
            if await cursor.fetchone():
                return False, "Вы уже записались в список участников!", 0, 0

        # Проверим баланс если есть входной взнос
        entry_fee = roulette["entry_fee"]
        if entry_fee > 0:
            async with db.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,)) as cursor:
                user = await cursor.fetchone()
                if not user or user["balance"] < entry_fee:
                    return False, f"Недостаточно монет для взноса! Нужно {entry_fee} 🪙.", 0, 0
            # Списываем взнос
            await db.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (entry_fee, user_id))

        # Добавляем в список участников
        try:
            await db.execute(
                """INSERT INTO roulette_players (roulette_id, user_id, username, full_name)
                   VALUES (?, ?, ?, ?)""",
                (roulette_id, user_id, username, full_name)
            )
        except Exception:
            return False, "Вы уже записаны!", 0, 0

        # Считаем текущее количество
        async with db.execute("SELECT COUNT(*) FROM roulette_players WHERE roulette_id = ?", (roulette_id,)) as cursor:
            count = (await cursor.fetchone())[0]

        max_p = roulette["max_players"]
        if count >= max_p:
            # Места заполнены — переводим статус в playing
            await db.execute("UPDATE roulettes SET status = 'playing' WHERE id = ?", (roulette_id,))

        await db.commit()
        return True, "Вы успешно записаны!", count, max_p

async def leave_roulette(roulette_id: int, user_id: int) -> tuple[bool, str]:
    """Выход участника из списка до начала игры (с возвратом взноса)."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM roulettes WHERE id = ?", (roulette_id,)) as cursor:
            roulette = await cursor.fetchone()
            if not roulette or roulette["status"] != "registration":
                return False, "Нельзя выйти, игра уже началась!"

        cursor = await db.execute("DELETE FROM roulette_players WHERE roulette_id = ? AND user_id = ?", (roulette_id, user_id))
        if cursor.rowcount == 0:
            return False, "Вы не были записаны в эту рулетку."

        entry_fee = roulette["entry_fee"]
        if entry_fee > 0:
            await db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (entry_fee, user_id))

        await db.commit()
        return True, "Вы успешно покинули список участников."

async def get_roulette_players(roulette_id: int) -> List[Dict[str, Any]]:
    """Список участников конкретной рулетки с их значками."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT rp.*, COALESCE(u.badge, '') as badge
               FROM roulette_players rp
               LEFT JOIN users u ON rp.user_id = u.user_id
               WHERE rp.roulette_id = ? ORDER BY rp.id ASC""",
            (roulette_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

async def update_roulette_player_roll(roulette_id: int, user_id: int, roll_value: int, score: int):
    """Фиксирует результат броска участника."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE roulette_players SET roll_value = ?, score = ? WHERE roulette_id = ? AND user_id = ?",
            (roll_value, score, roulette_id, user_id)
        )
        await db.commit()

async def finish_roulette(roulette_id: int, winner_id: int, winner_name: str):
    """Завершает рулетку и фиксирует победителя."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE roulettes SET status = 'finished', winner_id = ?, winner_name = ? WHERE id = ?",
            (winner_id, winner_name, roulette_id)
        )
        if winner_id > 0:
            await db.execute(
                "UPDATE users SET wins = wins + 1, total_games = total_games + 1 WHERE user_id = ?",
                (winner_id,)
            )
        await db.commit()

async def cancel_roulette(roulette_id: int) -> bool:
    """Отменяет рулетку и возвращает взносы всем участникам."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM roulettes WHERE id = ? AND status IN ('registration', 'playing')", (roulette_id,)) as cursor:
            roulette = await cursor.fetchone()
            if not roulette:
                return False

        entry_fee = roulette["entry_fee"]
        if entry_fee > 0:
            async with db.execute("SELECT user_id FROM roulette_players WHERE roulette_id = ?", (roulette_id,)) as cursor:
                players = await cursor.fetchall()
                for (uid,) in players:
                    await db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (entry_fee, uid))

        await db.execute("UPDATE roulettes SET status = 'cancelled' WHERE id = ?", (roulette_id,))
        await db.commit()
        return True

async def create_roulette_with_custom_players(chat_id: int, creator_id: int, game_type: str, prize: str, players_list: List[str]) -> int:
    """Создает рулетку и сразу записывает готовый список участников от админа."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """INSERT INTO roulettes (chat_id, creator_id, game_type, prize, max_players, entry_fee, status)
               VALUES (?, ?, ?, ?, ?, 0, 'playing')""",
            (chat_id, creator_id, game_type, prize, len(players_list))
        )
        roulette_id = cursor.lastrowid
        for i, name in enumerate(players_list, 1):
            clean_name = name.strip()
            username = clean_name.lstrip("@") if clean_name.startswith("@") else None
            # Для кастомных списков используем временный уникальный user_id (отрицательный i), если нет реального
            await db.execute(
                """INSERT INTO roulette_players (roulette_id, user_id, username, full_name)
                   VALUES (?, ?, ?, ?)""",
                (roulette_id, -i, username, clean_name)
            )
        await db.commit()
        return roulette_id
