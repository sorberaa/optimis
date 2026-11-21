import aiosqlite
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from config import DB_PATH, START_BALANCE, DAILY_BONUS, ADMIN_IDS

async def init_db():
    """Инициализация таблиц базы данных и базовых товаров магазина."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA synchronous=NORMAL")
        await db.execute("PRAGMA busy_timeout=5000")
        await db.execute("PRAGMA foreign_keys=ON")

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

        # Таблица драконов пользователей
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_dragons (
                user_id INTEGER PRIMARY KEY,
                name TEXT DEFAULT 'Огнекрыл',
                element TEXT DEFAULT '🔥 Огонь',
                stage INTEGER DEFAULT 1,
                level INTEGER DEFAULT 1,
                xp INTEGER DEFAULT 0,
                energy INTEGER DEFAULT 100,
                max_energy INTEGER DEFAULT 100,
                power INTEGER DEFAULT 15,
                last_fed TIMESTAMP,
                last_trained TIMESTAMP,
                last_expedition TIMESTAMP,
                last_income TIMESTAMP,
                expeditions_count INTEGER DEFAULT 0,
                wins_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Таблица инвентаря предметов
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_inventory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                item_key TEXT NOT NULL,
                title TEXT NOT NULL,
                quantity INTEGER DEFAULT 1,
                UNIQUE(user_id, item_key)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_hemp (
                user_id INTEGER PRIMARY KEY,
                leaves INTEGER DEFAULT 0,
                seed_stock INTEGER DEFAULT 5,
                level INTEGER DEFAULT 1,
                xp INTEGER DEFAULT 0,
                quality INTEGER DEFAULT 1,
                plots INTEGER DEFAULT 1,
                active_plots INTEGER DEFAULT 0,
                harvest_ready INTEGER DEFAULT 0,
                last_collect TIMESTAMP,
                last_harvest TIMESTAMP,
                harvest_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS dragon_expedition_cooldowns (
                user_id INTEGER NOT NULL,
                expedition TEXT NOT NULL,
                last_used TIMESTAMP NOT NULL,
                PRIMARY KEY (user_id, expedition)
            )
        """)

        # Добавим колонки декораций и бонусов в users если их ещё нет
        for col, col_def in [
            ("badge", "TEXT DEFAULT ''"),
            ("aura", "TEXT DEFAULT ''"),
            ("taunt", "TEXT DEFAULT ''"),
            ("bonus_streak", "INTEGER DEFAULT 1"),
            ("last_bonus_date", "TEXT DEFAULT ''"),
            ("nickname", "TEXT DEFAULT ''"),
            ("is_banned", "INTEGER DEFAULT 0")
        ]:
            try:
                await db.execute(f"ALTER TABLE users ADD COLUMN {col} {col_def}")
            except Exception:
                pass

        # Индексы для основных выборок и проверок состояния.
        await db.execute("CREATE INDEX IF NOT EXISTS idx_users_balance ON users(balance DESC)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_users_wins ON users(wins DESC)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_duels_status_chat ON duels(status, chat_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_duels_players ON duels(creator_id, opponent_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_roulette_chat_status ON roulettes(chat_id, status)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_roulette_players_roll ON roulette_players(roulette_id, score DESC)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_purchases_user ON purchases(user_id, purchased_at DESC)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_inventory_user ON user_inventory(user_id, item_key)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_dragon_expiry ON dragon_expedition_cooldowns(user_id, expedition)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_hemp_level ON user_hemp(level DESC, xp DESC)")

        # Товары в магазине: ТОЛЬКО виртуальные приколы внутри бота
        # Пересоздадим базовый ассортимент если пусто или устарело
        shop_catalog = [
            # Титулы и значки к нику
            ("🕶 [Блатной]", "Прикольный значок к нику в рулетках", 100, "badge", "🕶 [Блатной]"),
            ("🎯 [Снайпер Gang]", "Стикер меткого стрелка в играх", 180, "badge", "🎯 [Снайпер Gang]"),
            ("⚽ [Золотая Нога]", "Футбольный статус бомбардира", 220, "badge", "⚽ [Золотая Нога]"),
            ("🎰 [Фартовый]", "Статус везунчика клуба", 300, "badge", "🎰 [Фартовый]"),
            ("⚡ [Гроза Рулеток]", "Грозный титул в чат-играх", 450, "badge", "⚡ [Гроза Рулеток]"),
            ("💀 [Головорез]", "Опасный боевой статус в чате", 750, "badge", "💀 [Головорез]"),
            ("👑 [Шеф Gang]", "Высший авторитет Optimus Gang", 1000, "badge", "👑 [Шеф Gang]"),

            # Ауры оформления профиля
            ("🔥 Огненная Аура", "Пылающая рамка в карточке профиля", 150, "aura", "🔥 [Огненная Аура]"),
            ("⚡ Неоновый Разряд", "Стильное кибер-свечение профиля", 250, "aura", "⚡ [Неоновый Разряд]"),
            ("💎 Алмазный Градиент", "Роскошный сверкающий стиль профиля", 400, "aura", "💎 [Алмазный Градиент]"),
            ("🌌 Космическая Бездна", "Мистическая аура далеких звезд", 550, "aura", "🌌 [Космическая Бездна]"),

            # Победные боевые кличи (насмешки в чат при победе)
            ("🗣 Клич: «Легчайшая!»", "Бот кричит вашу насмешку при победе", 120, "taunt", "🗣 «Легчайшая для величайшего! Следующий!»"),
            ("🗣 Клич: «Кто на вылет?»", "Дерзкий победный клич в чате", 160, "taunt", "🗣 «Кто там следующий на вылет из клуба? 😏»"),
            ("🗣 Клич: «Удача со мной!»", "Победная фраза везунчика", 200, "taunt", "🗣 «Удача любит дерзких, а не пугливых! 😎»"),
            ("🗣 Клич: «Шеф на связи»", "Фирменный панчлайн клуба Optimus", 300, "taunt", "🗣 «Optimus Gang на связи — остальные отдыхают! 🔥»"),

            # Предметы и улучшения конопляной фермы
            ("🌱 Набор семян", "10 семян для посадки грядок", 25, "hemp_item", "seeds"),
            ("🧪 Удобрение", "Повышает качество и цену следующего сбора урожая", 100, "hemp_item", "fertilizer"),
            ("🏠 Теплица", "Навсегда открывает дополнительную грядку, максимум 4", 300, "hemp_item", "greenhouse")
        ]

        async with db.execute("SELECT COUNT(*) FROM shop_items") as cursor:
            count = (await cursor.fetchone())[0]

        await db.execute(
            "DELETE FROM shop_items WHERE item_type IS NULL OR item_type NOT IN ('badge', 'aura', 'taunt', 'hemp_item')"
        )
        for title, desc, price, i_type, content in shop_catalog:
            await db.execute(
                """INSERT INTO shop_items (title, description, price, item_type, content)
                   SELECT ?, ?, ?, ?, ?
                   WHERE NOT EXISTS (
                       SELECT 1 FROM shop_items WHERE item_type = ? AND content = ?
                   )""",
                (title, desc, price, i_type, content, i_type, content)
            )

        # Синхронизация администраторов из .env ADMIN_IDS
        for admin_id in ADMIN_IDS:
            await db.execute(
                "INSERT OR IGNORE INTO admins (user_id, username, added_by, is_superadmin) VALUES (?, 'Owner', 0, 1)",
                (admin_id,)
            )

        for index_sql in [
            "CREATE INDEX IF NOT EXISTS idx_roulettes_chat_status_id ON roulettes(chat_id, status, id DESC)",
            "CREATE INDEX IF NOT EXISTS idx_roulette_players_user_id ON roulette_players(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_duels_creator_status ON duels(creator_id, status)",
            "CREATE INDEX IF NOT EXISTS idx_duels_opponent_status ON duels(opponent_id, status)",
            "CREATE INDEX IF NOT EXISTS idx_users_balance_rank ON users(balance DESC)",
            "CREATE INDEX IF NOT EXISTS idx_users_wins_rank ON users(wins DESC)",
            "CREATE INDEX IF NOT EXISTS idx_users_recent ON users(created_at DESC, user_id DESC)",
            "CREATE INDEX IF NOT EXISTS idx_user_dragons_rank ON user_dragons(level DESC, power DESC)",
            "CREATE INDEX IF NOT EXISTS idx_purchases_user_recent ON purchases(user_id, purchased_at DESC)"
        ]:
            await db.execute(index_sql)

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

async def is_account_banned(user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT is_banned FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            return bool(row and row[0])

async def get_accounts_page(page: int, page_size: int = 8) -> tuple[List[Dict[str, Any]], int]:
    page = max(page, 0)
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT COUNT(*) FROM users") as cursor:
            total = (await cursor.fetchone())[0]
        async with db.execute(
            """SELECT user_id, username, full_name, nickname, balance, is_banned
               FROM users ORDER BY created_at DESC, user_id DESC LIMIT ? OFFSET ?""",
            (page_size, page * page_size)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows], total

async def get_account_details(user_id: int) -> Optional[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT u.*,
                      (SELECT COUNT(*) FROM duels d
                       WHERE d.creator_id = u.user_id OR d.opponent_id = u.user_id) AS duel_count,
                      (SELECT COUNT(*) FROM roulette_players rp
                       WHERE rp.user_id = u.user_id) AS roulette_count
               FROM users u WHERE u.user_id = ?""",
            (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

async def set_account_banned(user_id: int, is_banned: bool) -> bool:
    if user_id in ADMIN_IDS:
        return False
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,)) as cursor:
            if await cursor.fetchone():
                return False
        cursor = await db.execute(
            "UPDATE users SET is_banned = ? WHERE user_id = ?",
            (int(is_banned), user_id)
        )
        await db.commit()
        return cursor.rowcount == 1

async def set_account_balance(user_id: int, balance: int) -> bool:
    if balance < 0:
        return False
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "UPDATE users SET balance = ? WHERE user_id = ?",
            (balance, user_id)
        )
        await db.commit()
        return cursor.rowcount == 1

async def set_account_nickname(user_id: int, nickname: str) -> bool:
    clean = nickname.strip()[:32]
    if not clean:
        return False
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "UPDATE users SET nickname = ? WHERE user_id = ?",
            (clean, user_id)
        )
        await db.commit()
        return cursor.rowcount == 1

async def delete_account(user_id: int) -> bool:
    if user_id in ADMIN_IDS:
        return False
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("BEGIN IMMEDIATE")
        async with db.execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,)) as cursor:
            if await cursor.fetchone():
                await db.rollback()
                return False
        async with db.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,)) as cursor:
            if not await cursor.fetchone():
                await db.rollback()
                return False
        async with db.execute(
            """SELECT 1 FROM roulettes
               WHERE creator_id = ? AND status = 'playing'
               UNION ALL
               SELECT 1 FROM roulette_players rp
               JOIN roulettes r ON r.id = rp.roulette_id
               WHERE rp.user_id = ? AND r.status = 'playing'
               LIMIT 1""",
            (user_id, user_id)
        ) as cursor:
            if await cursor.fetchone():
                await db.rollback()
                return False
        async with db.execute(
            """SELECT 1 FROM duels
               WHERE status = 'playing' AND (creator_id = ? OR opponent_id = ?)
               LIMIT 1""",
            (user_id, user_id)
        ) as cursor:
            if await cursor.fetchone():
                await db.rollback()
                return False
        await db.execute(
            "UPDATE duels SET status = 'cancelled' WHERE creator_id = ? AND status = 'waiting'",
            (user_id,)
        )

        async with db.execute(
            """SELECT id, entry_fee FROM roulettes
               WHERE creator_id = ? AND status IN ('registration', 'ready', 'playing')""",
            (user_id,)
        ) as cursor:
            owned_lobbies = await cursor.fetchall()
        for lobby_id, entry_fee in owned_lobbies:
            if entry_fee > 0:
                await db.execute(
                    """UPDATE users SET balance = balance + ?
                       WHERE user_id IN (
                           SELECT user_id FROM roulette_players
                           WHERE roulette_id = ? AND user_id != ?
                       )""",
                    (entry_fee, lobby_id, user_id)
                )

        async with db.execute(
            """SELECT rp.roulette_id, r.status
               FROM roulette_players rp
               JOIN roulettes r ON r.id = rp.roulette_id
               WHERE rp.user_id = ? AND r.status IN ('registration', 'ready')""",
            (user_id,)
        ) as cursor:
            joined_lobbies = await cursor.fetchall()
        for lobby_id, status in joined_lobbies:
            if status == "ready":
                await db.execute(
                    "UPDATE roulettes SET status = 'registration' WHERE id = ? AND status = 'ready'",
                    (lobby_id,)
                )

        await db.execute(
            "UPDATE roulettes SET winner_id = NULL, winner_name = 'Удалённый аккаунт' WHERE winner_id = ?",
            (user_id,)
        )
        await db.execute(
            "DELETE FROM roulette_players WHERE roulette_id IN "
            "(SELECT id FROM roulettes WHERE creator_id = ?)",
            (user_id,)
        )
        await db.execute("DELETE FROM roulette_players WHERE user_id = ?", (user_id,))
        await db.execute("DELETE FROM roulettes WHERE creator_id = ?", (user_id,))
        await db.execute("DELETE FROM duels WHERE creator_id = ? OR opponent_id = ?", (user_id, user_id))
        await db.execute("DELETE FROM purchases WHERE user_id = ?", (user_id,))
        await db.execute("DELETE FROM user_inventory WHERE user_id = ?", (user_id,))
        await db.execute("DELETE FROM user_hemp WHERE user_id = ?", (user_id,))
        await db.execute("DELETE FROM user_dragons WHERE user_id = ?", (user_id,))
        await db.execute("DELETE FROM dragon_expedition_cooldowns WHERE user_id = ?", (user_id,))
        await db.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
        await db.commit()
        return True

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

async def spend_balance(user_id: int, amount: int) -> bool:
    """Atomically deduct a positive stake only when the user can afford it."""
    if user_id <= 0 or amount <= 0:
        return False
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "UPDATE users SET balance = balance - ? WHERE user_id = ? AND balance >= ?",
            (amount, user_id, amount)
        )
        await db.commit()
        return cursor.rowcount == 1

async def claim_daily_bonus(user_id: int) -> tuple[bool, int, Optional[str], int]:
    """
    Получение прогрессивного ежедневного бонуса (стрик дней).
    Возвращает (успех, сумма_бонуса, сообщение_или_время, текущий_стрик).
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("BEGIN IMMEDIATE")
        async with db.execute("SELECT balance, last_bonus, bonus_streak FROM users WHERE user_id = ?", (user_id,)) as cursor:
            user = await cursor.fetchone()
            if not user:
                await db.rollback()
                return False, 0, "Пользователь не найден.", 0

        last_bonus_str = user["last_bonus"]
        streak = user["bonus_streak"] or 1
        now = datetime.now()

        if last_bonus_str:
            try:
                last_bonus_time = datetime.fromisoformat(last_bonus_str)
                time_passed = now - last_bonus_time

                if time_passed < timedelta(hours=24):
                    remaining = timedelta(hours=24) - time_passed
                    hours, remainder = divmod(int(remaining.total_seconds()), 3600)
                    minutes, _ = divmod(remainder, 60)
                    await db.rollback()
                    return False, user["balance"], f"{hours} ч. {minutes} мин.", streak

                # Если прошло больше 48 часов, серия сбрасывается
                if time_passed > timedelta(hours=48):
                    streak = 1
                else:
                    streak = min(streak + 1, 7)
            except Exception:
                streak = 1

        # Награда: день 1 = 15, день 2 = 20, день 3 = 25 ... день 7 = 50
        bonus_amount = 15 + (streak - 1) * 5
        new_balance = user["balance"] + bonus_amount

        await db.execute(
            "UPDATE users SET balance = ?, last_bonus = ?, bonus_streak = ? WHERE user_id = ?",
            (new_balance, now.isoformat(), streak, user_id)
        )
        await db.commit()
        return True, bonus_amount, None, streak

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
    if bet <= 0:
        return 0
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "UPDATE users SET balance = balance - ? WHERE user_id = ? AND balance >= ?",
            (bet, creator_id, bet)
        )
        if cursor.rowcount == 0:
            await db.rollback()
            return 0
        cursor = await db.execute(
            """INSERT INTO duels (chat_id, creator_id, creator_name, game_type, bet, message_id, status)
               VALUES (?, ?, ?, ?, ?, ?, 'waiting')""",
            (chat_id, creator_id, creator_name, game_type, bet, message_id)
        )
        duel_id = cursor.lastrowid or 0
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
        await db.execute("BEGIN IMMEDIATE")
        async with db.execute("SELECT * FROM duels WHERE id = ? AND status = 'waiting'", (duel_id,)) as cursor:
            duel = await cursor.fetchone()
            if not duel:
                await db.rollback()
                return False
        if opponent_id == duel["creator_id"]:
            await db.rollback()
            return False

        cursor = await db.execute(
            "UPDATE users SET balance = balance - ? WHERE user_id = ? AND balance >= ?",
            (duel["bet"], opponent_id, duel["bet"])
        )
        if cursor.rowcount == 0:
            await db.rollback()
            return False

        cursor = await db.execute(
            "UPDATE duels SET opponent_id = ?, opponent_name = ?, status = 'playing' WHERE id = ? AND status = 'waiting'",
            (opponent_id, opponent_name, duel_id)
        )
        if cursor.rowcount == 0:
            await db.rollback()
            return False
        await db.commit()
        return True

async def record_duel_result(duel_id: int, winner_id: Optional[int], is_draw: bool, creator_id: int, opponent_id: int, bet: int):
    """Атомарно фиксирует один единственный результат дуэли."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA busy_timeout=5000")
        await db.execute("BEGIN IMMEDIATE")
        async with db.execute(
            "SELECT status FROM duels WHERE id = ?",
            (duel_id,)
        ) as cursor:
            row = await cursor.fetchone()
        if not row or row[0] != "playing":
            await db.rollback()
            return False

        try:
            if is_draw:
                await db.execute(
                    "UPDATE users SET balance = balance + ?, draws = draws + 1, total_games = total_games + 1 WHERE user_id = ?",
                    (bet, creator_id)
                )
                await db.execute(
                    "UPDATE users SET balance = balance + ?, draws = draws + 1, total_games = total_games + 1 WHERE user_id = ?",
                    (bet, opponent_id)
                )
                await db.execute(
                    "UPDATE duels SET status = 'finished', winner_id = NULL WHERE id = ?",
                    (duel_id,)
                )
            else:
                loser_id = opponent_id if winner_id == creator_id else creator_id
                await db.execute(
                    "UPDATE users SET balance = balance + ?, wins = wins + 1, total_games = total_games + 1 WHERE user_id = ?",
                    (bet * 2, winner_id)
                )
                await db.execute(
                    "UPDATE users SET losses = losses + 1, total_games = total_games + 1 WHERE user_id = ?",
                    (loser_id,)
                )
                await db.execute(
                    "UPDATE duels SET status = 'finished', winner_id = ? WHERE id = ?",
                    (winner_id, duel_id)
                )
            await db.commit()
            return True
        except Exception:
            await db.rollback()
            raise

async def get_top_players(limit: int = 10, by: str = "balance") -> List[Dict[str, Any]]:
    """Топ игроков по балансу или по количеству побед."""
    order_column = "balance" if by == "balance" else "wins"
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            f"""SELECT user_id, username, full_name, nickname,
                       COALESCE(NULLIF(nickname, ''), username, full_name) AS display_name,
                       balance, wins, total_games
                FROM users ORDER BY {order_column} DESC LIMIT ?""",
            (limit,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

# ==========================================
# КОНОПЛЯНАЯ ФЕРМА В ЧАТЕ
# ==========================================

async def get_or_create_hemp(user_id: int) -> Dict[str, Any]:
    """Получает карточку фермы пользователя или создает новую."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM user_hemp WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(row)
        await db.execute(
            "INSERT INTO user_hemp (user_id) VALUES (?)",
            (user_id,)
        )
        await db.commit()
        async with db.execute("SELECT * FROM user_hemp WHERE user_id = ?", (user_id,)) as cursor:
            return dict(await cursor.fetchone())

async def collect_hemp(user_id: int) -> tuple[bool, int, str, Dict[str, Any]]:
    """Быстрый сбор листьев с коротким кулдауном против спама."""
    import random
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("BEGIN IMMEDIATE")
        async with db.execute("SELECT * FROM user_hemp WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
        if not row:
            await db.execute("INSERT INTO user_hemp (user_id) VALUES (?)", (user_id,))
            async with db.execute("SELECT * FROM user_hemp WHERE user_id = ?", (user_id,)) as cursor:
                row = await cursor.fetchone()

        hemp = dict(row)
        now = datetime.now()
        last_collect = hemp["last_collect"]
        if last_collect:
            try:
                remaining = timedelta(seconds=30) - (now - datetime.fromisoformat(last_collect))
                if remaining.total_seconds() > 0:
                    seconds = max(1, int(remaining.total_seconds()))
                    await db.rollback()
                    return False, 0, f"Следующий сбор через {seconds} сек.", hemp
            except Exception:
                pass

        amount = 5 + hemp["level"] * 2 + random.randint(0, 4)
        xp = hemp["xp"] + 4
        level = hemp["level"]
        while xp >= level * 100:
            xp -= level * 100
            level += 1

        await db.execute(
            "UPDATE user_hemp SET leaves = leaves + ?, xp = ?, level = ?, last_collect = ? WHERE user_id = ?",
            (amount, xp, level, now.isoformat(), user_id)
        )
        await db.commit()
        hemp.update({"leaves": hemp["leaves"] + amount, "xp": xp, "level": level, "last_collect": now.isoformat()})
        return True, amount, "Конопля собрана!", hemp

async def plant_hemp(user_id: int) -> tuple[bool, str, Dict[str, Any]]:
    """Посадка семян на свободные грядки."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("BEGIN IMMEDIATE")
        async with db.execute("SELECT * FROM user_hemp WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
        if not row:
            await db.execute("INSERT INTO user_hemp (user_id) VALUES (?)", (user_id,))
            async with db.execute("SELECT * FROM user_hemp WHERE user_id = ?", (user_id,)) as cursor:
                row = await cursor.fetchone()
        hemp = dict(row)

        if hemp["seed_stock"] <= 0:
            await db.rollback()
            return False, "Нет семян. Купи набор в магазине.", hemp
        if hemp["active_plots"] >= hemp["plots"]:
            await db.rollback()
            return False, "Все грядки заняты. Дождись сбора урожая.", hemp

        harvest_at = datetime.now() + timedelta(minutes=3)
        await db.execute(
            """UPDATE user_hemp
               SET seed_stock = seed_stock - 1,
                   active_plots = active_plots + 1,
                   harvest_ready = 0,
                   harvest_at = ?
               WHERE user_id = ?""",
            (harvest_at.isoformat(), user_id)
        )
        await db.commit()
        hemp["seed_stock"] -= 1
        hemp["active_plots"] += 1
        hemp["harvest_at"] = harvest_at.isoformat()
        return True, "Семя посажено! Урожай созреет через 3 минуты.", hemp

async def harvest_hemp(user_id: int) -> tuple[bool, int, str, Dict[str, Any]]:
    """Сбор созревшего урожая с применением улучшений."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("BEGIN IMMEDIATE")
        async with db.execute("SELECT * FROM user_hemp WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
        if not row:
            await db.rollback()
            return False, 0, "Сначала открой ферму.", {}

        hemp = dict(row)
        if hemp["active_plots"] <= 0:
            await db.rollback()
            return False, 0, "Грядки пустые. Посади семена.", hemp
        if not hemp["harvest_at"]:
            await db.rollback()
            return False, 0, "Урожай еще не посажен.", hemp

        now = datetime.now()
        try:
            remaining = datetime.fromisoformat(hemp["harvest_at"]) - now
        except Exception:
            remaining = timedelta(seconds=-1)
        if remaining.total_seconds() > 0:
            minutes = max(1, int(remaining.total_seconds() // 60))
            await db.rollback()
            return False, 0, f"Урожай созревает ещё примерно {minutes} мин.", hemp

        quality_gain = 0
        async with db.execute(
            "SELECT quantity FROM user_inventory WHERE user_id = ? AND item_key = 'fertilizer'",
            (user_id,)
        ) as cursor:
            fertilizer = await cursor.fetchone()
        if fertilizer and fertilizer[0] > 0:
            quality_gain = 1
            await db.execute(
                "UPDATE user_inventory SET quantity = quantity - 1 WHERE user_id = ? AND item_key = 'fertilizer'",
                (user_id,)
            )

        base_yield = 30 + hemp["level"] * 5
        amount = int(base_yield * hemp["active_plots"])
        quality = min(5, hemp["quality"] + quality_gain)
        xp = hemp["xp"] + 25 * hemp["active_plots"]
        level = hemp["level"]
        while xp >= level * 100:
            xp -= level * 100
            level += 1

        await db.execute(
            """UPDATE user_hemp
               SET leaves = leaves + ?, quality = ?, xp = ?, level = ?,
                   active_plots = 0, harvest_ready = 0, harvest_at = NULL,
                   last_harvest = ?
               WHERE user_id = ?""",
            (amount, quality, xp, level, now.isoformat(), user_id)
        )
        await db.commit()
        hemp.update({
            "leaves": hemp["leaves"] + amount,
            "quality": quality,
            "xp": xp,
            "level": level,
            "active_plots": 0,
            "harvest_ready": 0,
            "harvest_at": None,
        })
        return True, amount, "Урожай собран!", hemp

async def sell_hemp(user_id: int) -> tuple[bool, int, int, Dict[str, Any]]:
    """Продажа всей собранной конопли по рыночной цене качества."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("BEGIN IMMEDIATE")
        async with db.execute("SELECT * FROM user_hemp WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
        if not row:
            await db.rollback()
            return False, 0, 0, {}

        hemp = dict(row)
        leaves = hemp["leaves"]
        if leaves <= 0:
            await db.rollback()
            return False, 0, 0, hemp

        price = 8 + (hemp["quality"] - 1) * 2
        coins = leaves * price
        await db.execute("UPDATE user_hemp SET leaves = 0 WHERE user_id = ?", (user_id,))
        await db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (coins, user_id))
        await db.commit()
        hemp["leaves"] = 0
        return True, leaves, coins, hemp

async def get_top_hemp(limit: int = 10) -> List[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT h.*, u.username, u.full_name, u.nickname
               FROM user_hemp h
               JOIN users u ON u.user_id = h.user_id
               ORDER BY h.level DESC, h.xp DESC, h.leaves DESC
               LIMIT ?""",
            (limit,)
        ) as cursor:
            return [dict(row) for row in await cursor.fetchall()]

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
        await db.execute("BEGIN IMMEDIATE")
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
            user = await cursor.fetchone()
            if not user:
                await db.rollback()
                return False, "Пользователь не найден.", None

        async with db.execute("SELECT * FROM shop_items WHERE id = ? AND is_active = 1", (item_id,)) as cursor:
            item = await cursor.fetchone()
            if not item:
                await db.rollback()
                return False, "Товар не найден или недоступен.", None

        if item["item_type"] not in {"badge", "aura", "taunt", "hemp_item"}:
            await db.rollback()
            return False, "Этот предмет недоступен в игровом магазине.", None

        if item["price"] < 0:
            await db.rollback()
            return False, "У товара указана некорректная цена.", None

        if user["balance"] < item["price"]:
            await db.rollback()
            return False, f"Недостаточно монет! Требуется {item['price']} 🪙, у вас {user['balance']} 🪙.", None

        cursor = await db.execute(
            "UPDATE users SET balance = balance - ? WHERE user_id = ? AND balance >= ?",
            (item["price"], user_id, item["price"])
        )
        if cursor.rowcount == 0:
            await db.rollback()
            return False, f"Недостаточно монет! Требуется {item['price']} 🪙.", None

        # Экипировка в зависимости от типа товара
        if item["item_type"] == "badge":
            await db.execute("UPDATE users SET badge = ? WHERE user_id = ?", (item["content"], user_id))
        elif item["item_type"] == "aura":
            await db.execute("UPDATE users SET aura = ? WHERE user_id = ?", (item["content"], user_id))
        elif item["item_type"] == "taunt":
            await db.execute("UPDATE users SET taunt = ? WHERE user_id = ?", (item["content"], user_id))
        elif item["item_type"] == "hemp_item":
            await db.execute(
                "INSERT OR IGNORE INTO user_hemp (user_id) VALUES (?)",
                (user_id,)
            )
            if item["content"] == "seeds":
                await db.execute(
                    "UPDATE user_hemp SET seed_stock = seed_stock + 10 WHERE user_id = ?",
                    (user_id,)
                )
            elif item["content"] == "greenhouse":
                async with db.execute(
                    "SELECT plots FROM user_hemp WHERE user_id = ?",
                    (user_id,)
                ) as cursor:
                    hemp_row = await cursor.fetchone()
                if not hemp_row or hemp_row[0] >= 4:
                    await db.rollback()
                    return False, "Все грядки уже открыты! Максимум: 4.", None
                await db.execute(
                    "UPDATE user_hemp SET plots = MIN(4, plots + 1) WHERE user_id = ?",
                    (user_id,)
                )
            else:
                await db.execute("""
                    INSERT INTO user_inventory (user_id, item_key, title, quantity)
                    VALUES (?, ?, ?, 1)
                    ON CONFLICT(user_id, item_key) DO UPDATE SET quantity = quantity + 1
                """, (user_id, item["content"], item["title"]))

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

async def get_user_decorations(user_id: int) -> Dict[str, str]:
    """Получает декорации профиля (титул, аура, боевой клич)."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT badge, aura, taunt FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return {
                    "badge": row["badge"] or "",
                    "aura": row["aura"] or "",
                    "taunt": row["taunt"] or ""
                }
            return {"badge": "", "aura": "", "taunt": ""}

async def get_user_inventory(user_id: int) -> List[Dict[str, Any]]:
    """Получает инвентарь пользователя."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM user_inventory WHERE user_id = ? AND quantity > 0", (user_id,)) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

async def use_inventory_item(user_id: int, item_key: str) -> bool:
    """Использует 1 штуку предмета из инвентаря."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "UPDATE user_inventory SET quantity = quantity - 1 WHERE user_id = ? AND item_key = ? AND quantity > 0",
            (user_id, item_key)
        )
        await db.commit()
        return cursor.rowcount > 0

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
            "SELECT * FROM roulettes WHERE chat_id = ? AND status IN ('registration', 'ready', 'playing') ORDER BY id DESC LIMIT 1",
            (chat_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

async def set_roulette_status(roulette_id: int, status: str):
    """Обновляет статус рулетки."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE roulettes SET status = ? WHERE id = ?", (status, roulette_id))
        await db.commit()

async def start_roulette(roulette_id: int) -> bool:
    """Starts a full lobby exactly once after an admin confirms it."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """UPDATE roulettes SET status = 'playing'
               WHERE id = ? AND status = 'ready'
                 AND (SELECT COUNT(*) FROM roulette_players WHERE roulette_id = ?) >= max_players""",
            (roulette_id, roulette_id)
        )
        await db.commit()
        return cursor.rowcount == 1

async def join_roulette(roulette_id: int, user_id: int, username: Optional[str], full_name: str) -> tuple[bool, str, int, int]:
    """
    Запись участника на рулетку.
    Возвращает (успех, сообщение, текущее_кол-во, макс_кол-во).
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("BEGIN IMMEDIATE")
        async with db.execute("SELECT * FROM roulettes WHERE id = ?", (roulette_id,)) as cursor:
            roulette = await cursor.fetchone()
            if not roulette or roulette["status"] != "registration":
                await db.rollback()
                return False, "Запись на эту рулетку закрыта!", 0, 0

        max_p = roulette["max_players"]
        async with db.execute(
            "SELECT COUNT(*) FROM roulette_players WHERE roulette_id = ?",
            (roulette_id,)
        ) as cursor:
            count = (await cursor.fetchone())[0]
        if count >= max_p:
            await db.rollback()
            return False, "Свободных мест больше нет.", count, max_p

        async with db.execute("SELECT 1 FROM roulette_players WHERE roulette_id = ? AND user_id = ?", (roulette_id, user_id)) as cursor:
            if await cursor.fetchone():
                await db.rollback()
                return False, "Вы уже записались в список участников!", 0, 0

        entry_fee = roulette["entry_fee"]
        if entry_fee > 0:
            cursor = await db.execute(
                "UPDATE users SET balance = balance - ? WHERE user_id = ? AND balance >= ?",
                (entry_fee, user_id, entry_fee)
            )
            if cursor.rowcount == 0:
                await db.rollback()
                return False, f"Недостаточно монет для взноса! Нужно {entry_fee} 🪙.", 0, 0

        try:
            await db.execute(
                """INSERT INTO roulette_players (roulette_id, user_id, username, full_name)
                   VALUES (?, ?, ?, ?)""",
                (roulette_id, user_id, username, full_name)
            )
        except aiosqlite.IntegrityError:
            await db.rollback()
            return False, "Вы уже записаны!", 0, 0

        async with db.execute("SELECT COUNT(*) FROM roulette_players WHERE roulette_id = ?", (roulette_id,)) as cursor:
            count = (await cursor.fetchone())[0]

        if count == max_p:
            # Места заполнены — переводим статус в 'ready' (ждёт нажатия админа)
            await db.execute("UPDATE roulettes SET status = 'ready' WHERE id = ? AND status = 'registration'", (roulette_id,))

        await db.commit()
        return True, "Вы успешно записаны!", count, max_p

async def leave_roulette(roulette_id: int, user_id: int) -> tuple[bool, str]:
    """Выход участника из списка до начала игры (с возвратом взноса)."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("BEGIN IMMEDIATE")
        async with db.execute("SELECT * FROM roulettes WHERE id = ?", (roulette_id,)) as cursor:
            roulette = await cursor.fetchone()
            if not roulette or roulette["status"] != "registration":
                await db.rollback()
                return False, "Нельзя выйти, игра уже началась или готова к старту!"

        cursor = await db.execute("DELETE FROM roulette_players WHERE roulette_id = ? AND user_id = ?", (roulette_id, user_id))
        if cursor.rowcount == 0:
            await db.rollback()
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
            """SELECT rp.*, COALESCE(u.badge, '') as badge,
                      COALESCE(NULLIF(u.nickname, ''), rp.full_name) AS display_name
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

async def link_roulette_player_user(
    roulette_id: int,
    placeholder_id: int,
    user_id: int,
    username: Optional[str],
    full_name: str
) -> bool:
    """Replaces a list-game placeholder with the Telegram account that sent a roll."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """UPDATE roulette_players
               SET user_id = ?, username = ?, full_name = ?
               WHERE roulette_id = ? AND user_id = ?
                 AND NOT EXISTS (
                     SELECT 1 FROM roulette_players
                     WHERE roulette_id = ? AND user_id = ?
                 )""",
            (user_id, username, full_name, roulette_id, placeholder_id, roulette_id, user_id)
        )
        await db.commit()
        return cursor.rowcount == 1

async def finish_roulette(roulette_id: int, winner_id: int, winner_name: str):
    """Завершает рулетку и фиксирует победителя."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA busy_timeout=5000")
        await db.execute("BEGIN IMMEDIATE")
        async with db.execute(
            "SELECT status FROM roulettes WHERE id = ?",
            (roulette_id,)
        ) as cursor:
            row = await cursor.fetchone()
        if not row or row[0] != "playing":
            await db.rollback()
            return False

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
        return True

async def cancel_roulette(roulette_id: int) -> bool:
    """Отменяет рулетку и возвращает взносы всем участникам."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("BEGIN IMMEDIATE")
        async with db.execute("SELECT * FROM roulettes WHERE id = ? AND status IN ('registration', 'ready')", (roulette_id,)) as cursor:
            roulette = await cursor.fetchone()
            if not roulette:
                await db.rollback()
                return False

        entry_fee = roulette["entry_fee"]
        if entry_fee > 0:
            async with db.execute("SELECT user_id FROM roulette_players WHERE roulette_id = ?", (roulette_id,)) as cursor:
                players = await cursor.fetchall()
                for (uid,) in players:
                    await db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (entry_fee, uid))

        await db.execute("UPDATE roulettes SET status = 'cancelled' WHERE id = ? AND status IN ('registration', 'ready')", (roulette_id,))
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
            user_id = None
            if username:
                async with db.execute(
                    "SELECT user_id FROM users WHERE lower(username) = lower(?) ORDER BY user_id LIMIT 1",
                    (username,)
                ) as user_cursor:
                    row = await user_cursor.fetchone()
                    user_id = row[0] if row else None
            # Unknown usernames receive a placeholder that is linked when they send their first roll.
            await db.execute(
                """INSERT INTO roulette_players (roulette_id, user_id, username, full_name)
                   VALUES (?, ?, ?, ?)""",
                (roulette_id, user_id if user_id is not None else -i, username, clean_name)
            )
        await db.commit()
        return roulette_id

# ==========================================
# ИГРА: ВЫРАЩИВАНИЕ ДРАКОНОВ OPTIMUS GANG
# ==========================================

DRAGON_STAGES = {
    1: {"name": "🥚 Древнее Яйцо", "min_lvl": 1},
    2: {"name": "🐣 Дракончик-малыш", "min_lvl": 2},
    3: {"name": "🐲 Юный Огнекрыл", "min_lvl": 5},
    4: {"name": "🐉 Боевой Дракон-воин", "min_lvl": 10},
    5: {"name": "👑 Дракон-Титан Optimus", "min_lvl": 15}
}

DRAGON_EXPEDITIONS = {
    "forest": {
        "name": "🌲 Зачарованный Лес",
        "min_lvl": 1,
        "energy_cost": 20,
        "cooldown_min": 15,
        "success_rate": 85,
        "reward_coins": (5, 15),
        "reward_xp": 20
    },
    "cave": {
        "name": "⛰️ Пещера Черепа",
        "min_lvl": 4,
        "energy_cost": 35,
        "cooldown_min": 60,
        "success_rate": 70,
        "reward_coins": (20, 45),
        "reward_xp": 50
    },
    "volcano": {
        "name": "🌋 Вулкан Древних Титанов",
        "min_lvl": 8,
        "energy_cost": 50,
        "cooldown_min": 180,
        "success_rate": 55,
        "reward_coins": (50, 100),
        "reward_xp": 110
    }
}

def get_dragon_stage(level: int) -> int:
    if level >= 15:
        return 5
    elif level >= 10:
        return 4
    elif level >= 5:
        return 3
    elif level >= 2:
        return 2
    return 1

def xp_for_next_level(level: int) -> int:
    return 50 + (level - 1) * 40

async def get_or_create_dragon(user_id: int) -> Dict[str, Any]:
    """Получает дракона игрока или создает нового в стадии яйца."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM user_dragons WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(row)

        await db.execute("BEGIN IMMEDIATE")
        await db.execute("""
            INSERT INTO user_dragons (
                user_id, name, element, stage, level, xp, energy, max_energy, power
            ) VALUES (?, 'Огнекрыл', '🔥 Огонь', 1, 1, 0, 100, 100, 15)
            ON CONFLICT(user_id) DO NOTHING
        """, (user_id,))

        async with db.execute("SELECT * FROM user_dragons WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
        await db.commit()
        return dict(row)

async def feed_dragon(user_id: int, item_key: Optional[str] = None) -> tuple[bool, str, Dict[str, Any]]:
    """Кормление дракона (бесплатно раз в час или специальным предметом)."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("BEGIN IMMEDIATE")
        async with db.execute("SELECT * FROM user_dragons WHERE user_id = ?", (user_id,)) as cursor:
            dragon = await cursor.fetchone()
            if not dragon:
                await db.rollback()
                return False, "У вас еще нет дракона!", {}

        dragon = dict(dragon)
        now = datetime.now()

        xp_gain = 0
        energy_gain = 0
        power_gain = 0
        msg_detail = ""

        if not item_key:
            # Бесплатная еда раз в 1 час
            last_fed_str = dragon.get("last_fed")
            if last_fed_str:
                try:
                    last_time = datetime.fromisoformat(last_fed_str)
                    if (now - last_time) < timedelta(hours=1):
                        diff = timedelta(hours=1) - (now - last_time)
                        mins = int(diff.total_seconds() // 60)
                        await db.rollback()
                        return False, f"Дракон сыт! Бесплатная порция через: <b>{mins} мин.</b>", dragon
                except Exception:
                    pass
            xp_gain = 25
            energy_gain = 25
            msg_detail = "🍖 Вы покормили дракона свежим мясом (+25 ⚡ энергии, +25 XP)!"
        elif item_key == "steak":
            item_cursor = await db.execute(
                "UPDATE user_inventory SET quantity = quantity - 1 "
                "WHERE user_id = ? AND item_key = 'steak' AND quantity > 0",
                (user_id,)
            )
            if item_cursor.rowcount == 0:
                await db.rollback()
                return False, "У вас нет Стейка из виверны! Купите его в магазине.", dragon
            xp_gain = 35
            energy_gain = 50
            power_gain = 2
            msg_detail = "🥩 Сочный стейк придал дракону диких сил (+50 ⚡, +35 XP, +2 💪 силы)!"
        elif item_key == "potion":
            item_cursor = await db.execute(
                "UPDATE user_inventory SET quantity = quantity - 1 "
                "WHERE user_id = ? AND item_key = 'potion' AND quantity > 0",
                (user_id,)
            )
            if item_cursor.rowcount == 0:
                await db.rollback()
                return False, "У вас нет Зелья бодрости! Купите его в магазине.", dragon
            xp_gain = 50
            energy_gain = 100
            power_gain = 3
            msg_detail = "🧪 Зелье наполнило дракона чистой магией (100% ⚡ энергии, +50 XP, +3 💪)!"
        elif item_key == "crystal":
            item_cursor = await db.execute(
                "UPDATE user_inventory SET quantity = quantity - 1 "
                "WHERE user_id = ? AND item_key = 'crystal' AND quantity > 0",
                (user_id,)
            )
            if item_cursor.rowcount == 0:
                await db.rollback()
                return False, "У вас нет Кристалла эволюции!", dragon
            xp_gain = 150
            energy_gain = 30
            power_gain = 8
            msg_detail = "✨ Кристалл эволюции вызвал яркую вспышку (+150 XP, +8 💪 силы)!"

        new_energy = min(dragon["max_energy"], dragon["energy"] + energy_gain)
        new_xp = dragon["xp"] + xp_gain
        new_power = dragon["power"] + power_gain
        new_level = dragon["level"]

        # Проверка повышения уровня
        req_xp = xp_for_next_level(new_level)
        level_up_msg = ""
        while new_xp >= req_xp:
            new_xp -= req_xp
            new_level += 1
            new_power += 5
            req_xp = xp_for_next_level(new_level)
            level_up_msg += f"\n🎉 <b>УРОВЕНЬ ПОВЫШЕН! Теперь уровень {new_level}!</b> (+5 к силе)"

        new_stage = get_dragon_stage(new_level)
        if new_stage > dragon["stage"]:
            level_up_msg += f"\n🔥 <b>ДРАКОН ЭВОЛЮЦИОНИРОВАЛ В СТАДИЮ: {DRAGON_STAGES[new_stage]['name']}!</b>"

        await db.execute("""
            UPDATE user_dragons SET
                xp = ?, level = ?, stage = ?, energy = ?, power = ?, last_fed = ?
            WHERE user_id = ?
        """, (new_xp, new_level, new_stage, new_energy, new_power, now.isoformat(), user_id))
        await db.commit()

        dragon["xp"] = new_xp
        dragon["level"] = new_level
        dragon["stage"] = new_stage
        dragon["energy"] = new_energy
        dragon["power"] = new_power

        return True, f"{msg_detail}{level_up_msg}", dragon

async def train_dragon(user_id: int) -> tuple[bool, str, Dict[str, Any]]:
    """Тренировка дракона (тратит 25 энергии, кулдаун 10 минут)."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("BEGIN IMMEDIATE")
        async with db.execute("SELECT * FROM user_dragons WHERE user_id = ?", (user_id,)) as cursor:
            dragon = await cursor.fetchone()
            if not dragon:
                await db.rollback()
                return False, "У вас еще нет дракона!", {}

        dragon = dict(dragon)
        now = datetime.now()

        if dragon["stage"] == 1:
            await db.rollback()
            return False, "🥚 Яйцо пока не может тренироваться! Сначала кормите его, чтобы вылупился дракончик.", dragon

        if dragon["energy"] < 25:
            await db.rollback()
            return False, f"❌ Недостаточно энергии! Требуется 25 ⚡, у дракона {dragon['energy']} ⚡. Покормите его!", dragon

        last_train_str = dragon.get("last_trained")
        if last_train_str:
            try:
                last_time = datetime.fromisoformat(last_train_str)
                if (now - last_time) < timedelta(minutes=10):
                    diff = timedelta(minutes=10) - (now - last_time)
                    mins = int(diff.total_seconds() // 60) + 1
                    await db.rollback()
                    return False, f"⏳ Дракон восстанавливает дыхание! Следующая тренировка через: <b>{mins} мин.</b>", dragon
            except Exception:
                pass

        import random
        xp_gain = random.randint(25, 40)
        power_gain = random.randint(2, 5)

        new_energy = dragon["energy"] - 25
        new_xp = dragon["xp"] + xp_gain
        new_power = dragon["power"] + power_gain
        new_level = dragon["level"]

        req_xp = xp_for_next_level(new_level)
        level_up_msg = ""
        while new_xp >= req_xp:
            new_xp -= req_xp
            new_level += 1
            new_power += 5
            req_xp = xp_for_next_level(new_level)
            level_up_msg += f"\n🎉 <b>УРОВЕНЬ ПОВЫШЕН! Теперь уровень {new_level}!</b>"

        new_stage = get_dragon_stage(new_level)
        if new_stage > dragon["stage"]:
            level_up_msg += f"\n🔥 <b>ЭВОЛЮЦИЯ: {DRAGON_STAGES[new_stage]['name']}!</b>"

        await db.execute("""
            UPDATE user_dragons SET
                xp = ?, level = ?, stage = ?, energy = ?, power = ?, last_trained = ?
            WHERE user_id = ?
        """, (new_xp, new_level, new_stage, new_energy, new_power, now.isoformat(), user_id))
        await db.commit()

        dragon["xp"] = new_xp
        dragon["level"] = new_level
        dragon["stage"] = new_stage
        dragon["energy"] = new_energy
        dragon["power"] = new_power

        return True, (
            f"🥊 <b>Боевая тренировка завершена!</b>\n"
            f"Дракон отработал удары хвостом и огненное дыхание!\n"
            f"📈 Получено: <b>+{xp_gain} XP</b>, <b>+{power_gain} 💪 силы</b>\n"
            f"⚡ Энергия: <code>{new_energy}/100</code>"
            f"{level_up_msg}"
        ), dragon

async def send_dragon_expedition(user_id: int, exp_type: str) -> tuple[bool, str, Dict[str, Any]]:
    """Отправка дракона в поход/экспедицию за монетами и сокровищами."""
    import random
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("BEGIN IMMEDIATE")
        async with db.execute("SELECT * FROM user_dragons WHERE user_id = ?", (user_id,)) as cursor:
            dragon = await cursor.fetchone()
            if not dragon:
                await db.rollback()
                return False, "У вас нет дракона!", {}

        dragon = dict(dragon)
        now = datetime.now()

        if dragon["stage"] == 1:
            await db.rollback()
            return False, "🥚 Яйцо не может летать в экспедиции! Сначала согрейте и покормите его.", dragon

        conf = DRAGON_EXPEDITIONS.get(exp_type)
        if not conf:
            await db.rollback()
            return False, "Неизвестная экспедиция.", dragon

        if dragon["level"] < conf["min_lvl"]:
            await db.rollback()
            return False, f"🔒 Для похода в «{conf['name']}» требуется {conf['min_lvl']} уровень дракона!", dragon

        element = dragon["element"]
        energy_cost = max(10, conf["energy_cost"] - (5 if "Лёд" in element else 0))
        if dragon["energy"] < energy_cost:
            await db.rollback()
            return False, f"❌ Недостаточно энергии! Требуется {energy_cost} ⚡, у дракона {dragon['energy']} ⚡.", dragon

        async with db.execute(
            "SELECT last_used FROM dragon_expedition_cooldowns WHERE user_id = ? AND expedition = ?",
            (user_id, exp_type)
        ) as cursor:
            cooldown_row = await cursor.fetchone()
        last_exp_str = cooldown_row["last_used"] if cooldown_row else None
        if last_exp_str:
            try:
                last_time = datetime.fromisoformat(last_exp_str)
                cd = timedelta(minutes=conf["cooldown_min"])
                if (now - last_time) < cd:
                    diff = cd - (now - last_time)
                    mins = int(diff.total_seconds() // 60) + 1
                    await db.rollback()
                    return False, f"⏳ Дракон еще не вернулся из предыдущего рейда! Подождите: <b>{mins} мин.</b>", dragon
            except Exception:
                pass

        # Проверка на оберег удачи в инвентаре
        async with db.execute("SELECT quantity FROM user_inventory WHERE user_id = ? AND item_key = 'amulet' AND quantity > 0", (user_id,)) as cur:
            has_amulet = (await cur.fetchone()) is not None

        if has_amulet:
            await db.execute(
                "UPDATE user_inventory SET quantity = quantity - 1 "
                "WHERE user_id = ? AND item_key = 'amulet' AND quantity > 0",
                (user_id,)
            )

        success_chance = conf["success_rate"] + (15 if has_amulet else 0) + (dragon["power"] // 10)
        if "Огонь" in element:
            success_chance += 10
        success_chance = min(95, success_chance)
        roll = random.randint(1, 100)
        is_success = roll <= success_chance

        new_energy = dragon["energy"] - energy_cost
        new_xp = dragon["xp"]
        new_power = dragon["power"]
        new_level = dragon["level"]
        coins_found = 0
        rare_find_text = ""

        if is_success:
            coins_found = random.randint(*conf["reward_coins"])
            # Бонус стихии
            if "Тень" in element:
                coins_found = int(coins_found * 1.3)
            elif "Золото" in element:
                coins_found = int(coins_found * 1.15)
            if has_amulet:
                coins_found = int(coins_found * 1.1)
            if random.randint(1, 100) <= 5:
                rare_bonus = random.randint(25, 60)
                coins_found += rare_bonus
                new_xp += 25
                rare_find_text = (
                    f"\n🌠 <b>РЕДКАЯ НАХОДКА!</b> Дракон обнаружил метеоритный осколок "
                    f"(+{rare_bonus} 🪙 и +25 XP)!"
                )
            new_xp += conf["reward_xp"]
            new_power += 1
            await db.execute(
                "UPDATE users SET balance = balance + ? WHERE user_id = ?",
                (coins_found, user_id)
            )

            req_xp = xp_for_next_level(new_level)
            level_up_msg = ""
            while new_xp >= req_xp:
                new_xp -= req_xp
                new_level += 1
                new_power += 5
                req_xp = xp_for_next_level(new_level)
                level_up_msg += f"\n🎉 <b>УРОВЕНЬ ПОВЫШЕН! Теперь уровень {new_level}!</b>"

            new_stage = get_dragon_stage(new_level)

            await db.execute("""
                UPDATE user_dragons SET
                    xp = ?, level = ?, stage = ?, energy = ?, power = ?,
                    last_expedition = ?, expeditions_count = expeditions_count + 1, wins_count = wins_count + 1
                WHERE user_id = ?
            """, (new_xp, new_level, new_stage, new_energy, new_power, now.isoformat(), user_id))
            await db.execute(
                """INSERT INTO dragon_expedition_cooldowns (user_id, expedition, last_used)
                   VALUES (?, ?, ?)
                   ON CONFLICT(user_id, expedition) DO UPDATE SET last_used = excluded.last_used""",
                (user_id, exp_type, now.isoformat())
            )
            await db.commit()

            return True, (
                f"⚔️ <b>УСПЕХ В ЭКСПЕДИЦИИ: {conf['name']}!</b>\n\n"
                f"Дракон сразил монстров подземелья и вернулся с добычей!\n"
                f"💰 Найдено монет: <b>+{coins_found} 🪙</b>\n"
                f"📈 Опыт: <b>+{conf['reward_xp']} XP</b> (+1 к силе)\n"
                f"⚡ Энергия: <code>{new_energy}/100</code> (потрачено {energy_cost})"
                f"{rare_find_text}{level_up_msg}"
            ), dragon
        else:
            # Неудача
            new_xp += 5
            req_xp = xp_for_next_level(new_level)
            level_up_msg = ""
            while new_xp >= req_xp:
                new_xp -= req_xp
                new_level += 1
                new_power += 5
                req_xp = xp_for_next_level(new_level)
                level_up_msg += f"\n🎉 <b>УРОВЕНЬ ПОВЫШЕН! Теперь уровень {new_level}!</b>"
            new_stage = get_dragon_stage(new_level)
            await db.execute("""
                UPDATE user_dragons SET
                    xp = ?, level = ?, stage = ?, energy = ?, power = ?,
                    last_expedition = ?, expeditions_count = expeditions_count + 1
                WHERE user_id = ?
            """, (new_xp, new_level, new_stage, new_energy, new_power, now.isoformat(), user_id))
            await db.execute(
                """INSERT INTO dragon_expedition_cooldowns (user_id, expedition, last_used)
                   VALUES (?, ?, ?)
                   ON CONFLICT(user_id, expedition) DO UPDATE SET last_used = excluded.last_used""",
                (user_id, exp_type, now.isoformat())
            )
            await db.commit()

            return False, (
                f"⚠️ <b>Опасное отступление из: {conf['name']}!</b>\n\n"
                f"В глубинах логова враги оказались слишком сильны, дракон был вынужден отступить.\n"
                f"Получено немного опыта за бой (+5 XP), но сокровища не найдены.\n"
                f"Потренируйте дракона и восстановите энергию!{level_up_msg}"
            ), dragon

async def claim_dragon_income(user_id: int) -> tuple[bool, int, Optional[str]]:
    """Сбор пассивной дани из логова дракона (раз в 12 часов)."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("BEGIN IMMEDIATE")
        async with db.execute("SELECT * FROM user_dragons WHERE user_id = ?", (user_id,)) as cursor:
            dragon = await cursor.fetchone()
            if not dragon:
                await db.rollback()
                return False, 0, "У вас нет дракона!"

        dragon = dict(dragon)
        now = datetime.now()

        if dragon["stage"] == 1:
            await db.rollback()
            return False, 0, "🥚 Яйцо еще не приносит дохода. Вырастите дракончика!"

        last_inc_str = dragon.get("last_income")
        if last_inc_str:
            try:
                last_time = datetime.fromisoformat(last_inc_str)
                if (now - last_time) < timedelta(hours=12):
                    diff = timedelta(hours=12) - (now - last_time)
                    hours = int(diff.total_seconds() // 3600)
                    mins = int((diff.total_seconds() % 3600) // 60)
                    await db.rollback()
                    return False, 0, f"{hours} ч. {mins} мин."
            except Exception:
                pass

        # Доход зависит от уровня
        base_income = 10 + dragon["level"] * 3
        if "Золото" in dragon["element"]:
            base_income = int(base_income * 1.5)

        await db.execute(
            "UPDATE users SET balance = balance + ? WHERE user_id = ?",
            (base_income, user_id)
        )
        await db.execute("UPDATE user_dragons SET last_income = ? WHERE user_id = ?", (now.isoformat(), user_id))
        await db.commit()
        return True, base_income, None

async def rename_dragon(user_id: int, new_name: str) -> bool:
    """Смена клички дракона."""
    clean = new_name.strip()[:25]
    if not clean:
        return False
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE user_dragons SET name = ? WHERE user_id = ?", (clean, user_id))
        await db.commit()
        return True

async def set_dragon_element(user_id: int, element: str) -> bool:
    """Выбор стихии дракона при рождении."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE user_dragons SET element = ? WHERE user_id = ?", (element, user_id))
        await db.commit()
        return True

async def get_top_dragons(limit: int = 10) -> List[Dict[str, Any]]:
    """Топ сильнейших драконов клуба."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT d.*, u.username, u.full_name
            FROM user_dragons d
            LEFT JOIN users u ON d.user_id = u.user_id
            ORDER BY d.level DESC, d.power DESC
            LIMIT ?
        """, (limit,)) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]
