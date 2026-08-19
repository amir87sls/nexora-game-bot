import os
from threading import Thread

import psycopg
from flask import Flask

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)

from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)


BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")


if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not configured.")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not configured.")


app = Flask(__name__)


@app.route("/")
def home():
    return "Nexora Bot is running!"


@app.route("/healthz")
def healthz():
    return "OK"


def run_web():
    port = int(os.getenv("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)


def db():
    return psycopg.connect(DATABASE_URL)


def init_database():

    with db() as conn:

        with conn.cursor() as cur:

            cur.execute("""
                CREATE TABLE IF NOT EXISTS players (
                    id BIGSERIAL PRIMARY KEY,
                    telegram_id BIGINT UNIQUE NOT NULL,
                    username TEXT,
                    first_name TEXT,
                    country_id BIGINT,
                    role TEXT DEFAULT 'player',
                    government_type TEXT,
                    money BIGINT DEFAULT 0,
                    bank_money BIGINT DEFAULT 0,
                    quiz_passed BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cur.execute("""
                ALTER TABLE players
                ADD COLUMN IF NOT EXISTS country_id BIGINT
            """)

            cur.execute("""
                ALTER TABLE players
                ADD COLUMN IF NOT EXISTS role TEXT DEFAULT 'player'
            """)

            cur.execute("""
                ALTER TABLE players
                ADD COLUMN IF NOT EXISTS government_type TEXT
            """)

            cur.execute("""
                ALTER TABLE players
                ADD COLUMN IF NOT EXISTS money BIGINT DEFAULT 0
            """)

            cur.execute("""
                ALTER TABLE players
                ADD COLUMN IF NOT EXISTS bank_money BIGINT DEFAULT 0
            """)

            cur.execute("""
                ALTER TABLE players
                ADD COLUMN IF NOT EXISTS quiz_passed BOOLEAN DEFAULT FALSE
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS owner (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    telegram_id BIGINT UNIQUE NOT NULL,
                    username TEXT,
                    first_name TEXT,
                    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS countries (
                    id BIGSERIAL PRIMARY KEY,
                    name TEXT UNIQUE NOT NULL,
                    flag TEXT DEFAULT '🌍',
                    description TEXT DEFAULT '',
                    government_type TEXT,
                    ruler_telegram_id BIGINT UNIQUE,
                    active BOOLEAN DEFAULT FALSE,
                    treasury BIGINT DEFAULT 0,
                    daily_income BIGINT DEFAULT 0,
                    public_satisfaction INTEGER DEFAULT 100,
                    stability INTEGER DEFAULT 100,
                    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cur.execute("""
                ALTER TABLE countries
                ADD COLUMN IF NOT EXISTS government_type TEXT
            """)

            cur.execute("""
                ALTER TABLE countries
                ADD COLUMN IF NOT EXISTS ruler_telegram_id BIGINT
            """)

            cur.execute("""
                ALTER TABLE countries
                ADD COLUMN IF NOT EXISTS active BOOLEAN DEFAULT FALSE
            """)

            cur.execute("""
                ALTER TABLE countries
                ADD COLUMN IF NOT EXISTS treasury BIGINT DEFAULT 0
            """)

            cur.execute("""
                ALTER TABLE countries
                ADD COLUMN IF NOT EXISTS daily_income BIGINT DEFAULT 0
            """)

            cur.execute("""
                ALTER TABLE countries
                ADD COLUMN IF NOT EXISTS public_satisfaction INTEGER DEFAULT 100
            """)

            cur.execute("""
                ALTER TABLE countries
                ADD COLUMN IF NOT EXISTS stability INTEGER DEFAULT 100
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS official_links (
                    key TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    url TEXT DEFAULT ''
                )
            """)

            links = [
                ("bot", "🤖 ربات Nexora"),
                ("chat", "💬 گپ بازیکنان"),
                ("news", "📰 کانال اخبار"),
                ("owner", "👑 پیوی مالک"),
                ("rules", "📚 قوانین و آموزش"),
            ]

            for key, title in links:

                cur.execute(
                    """
                    INSERT INTO official_links
                    (key, title)
                    VALUES (%s, %s)
                    ON CONFLICT (key) DO NOTHING
                    """,
                    (key, title),
                )

        conn.commit()


def get_owner():

    with db() as conn:

        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT telegram_id
                FROM owner
                WHERE id = 1
                """
            )

            return cur.fetchone()


def is_owner(user_id):

    owner = get_owner()

    return (
        owner is not None
        and owner[0] == user_id
    )


def register_player(user):

    with db() as conn:

        with conn.cursor() as cur:

            cur.execute(
                """
                INSERT INTO players
                (
                    telegram_id,
                    username,
                    first_name
                )
                VALUES (%s, %s, %s)
                ON CONFLICT (telegram_id)
                DO UPDATE SET
                    username = EXCLUDED.username,
                    first_name = EXCLUDED.first_name
                """,
                (
                    user.id,
                    user.username,
                    user.first_name,
                ),
            )

        conn.commit()


async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    user = update.effective_user

    register_player(user)

    owner = get_owner()

    if owner is None:

        keyboard = [
            [
                InlineKeyboardButton(
                    "👑 قبول مالکیت",
                    callback_data="claim_owner",
                ),
                InlineKeyboardButton(
                    "❌ انصراف",
                    callback_data="cancel_owner",
                ),
            ]
        ]

        await update.message.reply_text(
            "🌍 به Nexora خوش آمدید!\n\n"
            "هنوز مالک بازی تعیین نشده است.\n\n"
            "اگر شما سازنده بازی هستید، "
            "می‌توانید مالکیت Nexora را بر عهده بگیرید.",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

        return

    if is_owner(user.id):

        await owner_panel(update, context)

        return

    await player_home(update, context)


async def player_home(
    update,
    context,
):

    keyboard = [
        [
            InlineKeyboardButton(
                "🌍 کشورها",
                callback_data="country_menu",
            )
        ],
        [
            InlineKeyboardButton(
                "👤 پروفایل من",
                callback_data="my_profile",
            )
        ],
    ]

    text = (
        "🌍 Nexora\n\n"
        "👤 حساب بازیکن شما فعال است.\n\n"
        "برای ادامه یکی از گزینه‌ها را انتخاب کنید."
    )

    if update.callback_query:

        await update.callback_query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    else:

        await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
        )


async def claim_owner(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    query = update.callback_query

    await query.answer()

    user = query.from_user

    with db() as conn:

        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT telegram_id
                FROM owner
                WHERE id = 1
                """
            )

            owner = cur.fetchone()

            if owner is not None:

                await query.edit_message_text(
                    "🔒 مالک Nexora قبلاً تعیین شده است."
                )

                return

            cur.execute(
                """
                INSERT INTO owner
                (
                    id,
                    telegram_id,
                    username,
                    first_name
                )
                VALUES (1, %s, %s, %s)
                """,
                (
                    user.id,
                    user.username,
                    user.first_name,
                ),
            )

        conn.commit()

    await query.edit_message_text(
        "👑 تبریک!\n\n"
        "شما با موفقیت مالک Nexora شدید. 🔒\n\n"
        "دوباره /start را بزنید تا پنل مالک باز شود."
    )


async def cancel_owner(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    query = update.callback_query

    await query.answer()

    await query.edit_message_text(
        "❌ درخواست مالکیت لغو شد.\n\n"
        "برای شروع دوباره /start را بزنید."
            )
async def player_home(
    update,
    context,
):

    if update.callback_query:

        query = update.callback_query
        await query.answer()

        if not is_owner(query.from_user.id):

            await query.edit_message_text(
                "⛔ دسترسی غیرمجاز."
            )

            return

    else:

        if not is_owner(update.effective_user.id):

            return


    keyboard = [
        [
            InlineKeyboardButton(
                "🌍 مدیریت کشورها",
                callback_data="country_admin",
            )
        ],
        [
            InlineKeyboardButton(
                "👥 بازیکنان",
                callback_data="players_admin",
            )
        ],
        [
            InlineKeyboardButton(
                "🔗 لینک‌های رسمی",
                callback_data="links_admin",
            )
        ],
    ]


    text = (
        "👑 پنل مالک Nexora\n\n"
        "یک بخش را انتخاب کنید:"
    )


    if update.callback_query:

        await update.callback_query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    else:

        await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
        )


async def country_admin(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    query = update.callback_query

    await query.answer()

    if not is_owner(query.from_user.id):

        await query.edit_message_text(
            "⛔ دسترسی غیرمجاز."
        )

        return


    keyboard = [
        [
            InlineKeyboardButton(
                "➕ ساخت کشور",
                callback_data="add_country",
            )
        ],
        [
            InlineKeyboardButton(
                "📋 لیست کشورها",
                callback_data="country_list",
            )
        ],
        [
            InlineKeyboardButton(
                "👑 تعیین حاکم",
                callback_data="assign_ruler",
            )
        ],
        [
            InlineKeyboardButton(
                "🔙 بازگشت",
                callback_data="owner_panel",
            )
        ],
    ]


    await query.edit_message_text(
        "🌍 مدیریت کشورها",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def add_country(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    query = update.callback_query

    await query.answer()

    if not is_owner(query.from_user.id):

        await query.edit_message_text(
            "⛔ دسترسی غیرمجاز."
        )

        return


    context.user_data["country_step"] = "name"


    await query.edit_message_text(
        "➕ ساخت کشور\n\n"
        "نام کشور را ارسال کنید.\n\n"
        "مثال:\n"
        "ایران"
    )


async def receive_country(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not is_owner(update.effective_user.id):

        return


    step = context.user_data.get(
        "country_step"
    )


    if step == "name":

        name = update.message.text.strip()


        if not name:

            await update.message.reply_text(
                "❌ نام کشور نمی‌تواند خالی باشد."
            )

            return


        context.user_data[
            "country_name"
        ] = name


        context.user_data[
            "country_step"
        ] = "flag"


        await update.message.reply_text(
            "🏳️ پرچم کشور را ارسال کنید.\n\n"
            "مثال: 🇮🇷"
        )

        return


    if step == "flag":

        flag = update.message.text.strip()


        if not flag:

            flag = "🌍"


        context.user_data[
            "country_flag"
        ] = flag


        context.user_data[
            "country_step"
        ] = "description"


        await update.message.reply_text(
            "📝 توضیح کشور را ارسال کنید.\n\n"
            "اگر توضیح نمی‌خواهید بنویسید:\n"
            "ندارد"
        )

        return


    if step == "description":

        description = update.message.text.strip()


        if description == "ندارد":

            description = ""


        context.user_data[
            "country_description"
        ] = description


        context.user_data[
            "country_step"
        ] = "government"


        keyboard = [
            [
                InlineKeyboardButton(
                    "🇺🇳 جمهوری",
                    callback_data="gov:republic",
                )
            ],
            [
                InlineKeyboardButton(
                    "👑 پادشاهی",
                    callback_data="gov:monarchy",
                )
            ],
            [
                InlineKeyboardButton(
                    "🏛️ رهبری",
                    callback_data="gov:leadership",
                )
            ],
        ]


        await update.message.reply_text(
            "🏛️ نوع حکومت کشور را انتخاب کنید:",
            reply_markup=InlineKeyboardMarkup(
                keyboard
            ),
        )

        return


async def select_government(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    query = update.callback_query

    await query.answer()


    if not is_owner(query.from_user.id):

        await query.edit_message_text(
            "⛔ دسترسی غیرمجاز."
        )

        return


    if context.user_data.get(
        "country_step"
    ) != "government":

        await query.edit_message_text(
            "❌ این درخواست منقضی شده است."
        )

        return


    government_map = {
        "republic": "جمهوری",
        "monarchy": "پادشاهی",
        "leadership": "رهبری",
    }


    government_key = query.data.split(
        ":",
        1,
    )[1]


    government = government_map.get(
        government_key
    )


    if not government:

        await query.edit_message_text(
            "❌ نوع حکومت نامعتبر است."
        )

        return


    name = context.user_data.get(
        "country_name"
    )

    flag = context.user_data.get(
        "country_flag",
        "🌍",
    )

    description = context.user_data.get(
        "country_description",
        "",
    )


    try:

        with db() as conn:

            with conn.cursor() as cur:

                cur.execute(
                    """
                    INSERT INTO countries
                    (
                        name,
                        flag,
                        description,
                        government_type,
                        active,
                        treasury,
                        daily_income,
                        public_satisfaction,
                        stability
                    )
                    VALUES
                    (
                        %s,
                        %s,
                        %s,
                        %s,
                        FALSE,
                        0,
                        0,
                        100,
                        100
                    )
                    """,
                    (
                        name,
                        flag,
                        description,
                        government,
                    ),
                )

            conn.commit()


    except psycopg.errors.UniqueViolation:

        await query.edit_message_text(
            "❌ این کشور قبلاً وجود دارد."
        )

        context.user_data.clear()

        return


    context.user_data.clear()


    await query.edit_message_text(
        "✅ کشور ساخته شد.\n\n"
        + flag
        + " "
        + name
        + "\n"
        + "🏛️ حکومت: "
        + government
        + "\n\n"
        "🔴 کشور هنوز فعال نیست.\n"
        "ابتدا باید برای آن حاکم تعیین شود."
    )


async def country_list(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    query = update.callback_query

    await query.answer()


    if not is_owner(query.from_user.id):

        await query.edit_message_text(
            "⛔ دسترسی غیرمجاز."
        )

        return


    with db() as conn:

        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT
                    id,
                    name,
                    flag,
                    government_type,
                    ruler_telegram_id,
                    active,
                    treasury,
                    daily_income,
                    public_satisfaction,
                    stability
                FROM countries
                ORDER BY name
                """
            )

            countries = cur.fetchall()


    if not countries:

        text = (
            "📋 هنوز هیچ کشوری ساخته نشده است."
        )

    else:

        text = "📋 کشورهای Nexora\n\n"


        for row in countries:

            (
                country_id,
                name,
                flag,
                government,
                ruler_id,
                active,
                treasury,
                daily_income,
                satisfaction,
                stability,
            ) = row


            status = (
                "🟢 فعال"
                if active
                else "🔴 غیرفعال"
            )


            ruler = (
                "👑 دارای حاکم"
                if ruler_id
                else "⚠️ بدون حاکم"
            )


            text += (
                flag
                + " "
                + name
                + "\n"
                + "🏛️ "
                + str(government or "نامشخص")
                + "\n"
                + status
                + " | "
                + ruler
                + "\n"
                + "💰 خزانه: "
                + str(treasury or 0)
                + "\n"
                + "📈 درآمد روزانه: "
                + str(daily_income or 0)
                + "\n"
                + "❤️ رضایت: "
                + str(satisfaction or 0)
                + "%\n"
                + "🛡️ ثبات: "
                + str(stability or 0)
                + "%\n\n"
            )


    keyboard = [
        [
            InlineKeyboardButton(
                "➕ ساخت کشور",
                callback_data="add_country",
            )
        ],
        [
            InlineKeyboardButton(
                "👑 تعیین حاکم",
                callback_data="assign_ruler",
            )
        ],
        [
            InlineKeyboardButton(
                "🔙 بازگشت",
                callback_data="country_admin",
            )
        ],
    ]


    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        )
    # ---------------- ASSIGN RULER ----------------


async def assign_ruler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    query = update.callback_query
    await query.answer()

    if not is_owner(query.from_user.id):

        await query.edit_message_text(
            "⛔ دسترسی غیرمجاز."
        )

        return


    with db() as conn:

        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT id, name, flag
                FROM countries
                WHERE ruler_telegram_id IS NULL
                ORDER BY name
                """
            )

            countries = cur.fetchall()


    if not countries:

        await query.edit_message_text(
            "❌ هیچ کشور بدون حاکمی وجود ندارد."
        )

        return


    keyboard = []


    for country_id, name, flag in countries:

        keyboard.append(
            [
                InlineKeyboardButton(
                    flag
                    + " "
                    + name,
                    callback_data=(
                        "choose_ruler_country:"
                        + str(country_id)
                    ),
                )
            ]
        )


    keyboard.append(
        [
            InlineKeyboardButton(
                "🔙 بازگشت",
                callback_data="country_admin",
            )
        ]
    )


    await query.edit_message_text(
        "👑 تعیین حاکم\n\n"
        "ابتدا کشور موردنظر را انتخاب کنید:",
        reply_markup=InlineKeyboardMarkup(
            keyboard
        ),
    )


async def choose_ruler_country(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    query = update.callback_query
    await query.answer()


    if not is_owner(query.from_user.id):

        await query.edit_message_text(
            "⛔ دسترسی غیرمجاز."
        )

        return


    try:

        country_id = int(
            query.data.split(
                ":",
                1,
            )[1]
        )

    except (ValueError, IndexError):

        await query.edit_message_text(
            "❌ کشور نامعتبر است."
        )

        return


    context.user_data[
        "ruler_country_id"
    ] = country_id


    with db() as conn:

        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT name, flag, government_type
                FROM countries
                WHERE id = %s
                """,
                (country_id,),
            )

            country = cur.fetchone()


            cur.execute(
                """
                SELECT
                    telegram_id,
                    first_name,
                    username
                FROM players
                WHERE country_id IS NULL
                ORDER BY created_at
                LIMIT 50
                """
            )

            players = cur.fetchall()


    if not country:

        await query.edit_message_text(
            "❌ کشور پیدا نشد."
        )

        return


    if not players:

        await query.edit_message_text(
            "❌ هیچ بازیکنی بدون کشور وجود ندارد.\n\n"
            "ابتدا بازیکن موردنظر باید /start را زده باشد."
        )

        return


    (
        country_name,
        country_flag,
        government,
    ) = country


    keyboard = []


    for telegram_id, first_name, username in players:

        display_name = (
            first_name
            or username
            or str(telegram_id)
        )


        keyboard.append(
            [
                InlineKeyboardButton(
                    "👤 "
                    + display_name,
                    callback_data=(
                        "set_ruler:"
                        + str(telegram_id)
                    ),
                )
            ]
        )


    keyboard.append(
        [
            InlineKeyboardButton(
                "🔙 بازگشت",
                callback_data="assign_ruler",
            )
        ]
    )


    await query.edit_message_text(
        "👑 انتخاب حاکم\n\n"
        + country_flag
        + " "
        + country_name
        + "\n"
        + "🏛️ حکومت: "
        + str(government or "-")
        + "\n\n"
        "بازیکن موردنظر را انتخاب کنید:",
        reply_markup=InlineKeyboardMarkup(
            keyboard
        ),
    )


async def set_ruler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    query = update.callback_query
    await query.answer()


    if not is_owner(query.from_user.id):

        await query.edit_message_text(
            "⛔ دسترسی غیرمجاز."
        )

        return


    try:

        ruler_id = int(
            query.data.split(
                ":",
                1,
            )[1]
        )

    except (ValueError, IndexError):

        await query.edit_message_text(
            "❌ بازیکن نامعتبر است."
        )

        return


    country_id = context.user_data.get(
        "ruler_country_id"
    )


    if not country_id:

        await query.edit_message_text(
            "❌ کشور انتخاب نشده است."
        )

        return


    with db() as conn:

        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT
                    name,
                    flag,
                    government_type,
                    ruler_telegram_id
                FROM countries
                WHERE id = %s
                """,
                (country_id,),
            )

            country = cur.fetchone()


            if not country:

                await query.edit_message_text(
                    "❌ کشور پیدا نشد."
                )

                return


            if country[3] is not None:

                await query.edit_message_text(
                    "❌ این کشور قبلاً حاکم دارد."
                )

                return


            cur.execute(
                """
                SELECT
                    first_name,
                    username,
                    country_id
                FROM players
                WHERE telegram_id = %s
                """,
                (ruler_id,),
            )

            player = cur.fetchone()


            if not player:

                await query.edit_message_text(
                    "❌ بازیکن پیدا نشد."
                )

                return


            if player[2] is not None:

                await query.edit_message_text(
                    "❌ این بازیکن قبلاً عضو یک کشور است."
                )

                return


            cur.execute(
                """
                UPDATE players
                SET
                    country_id = %s,
                    role = %s,
                    government_type = %s
                WHERE telegram_id = %s
                """,
                (
                    country_id,
                    "ruler",
                    country[2],
                    ruler_id,
                ),
            )


            cur.execute(
                """
                UPDATE countries
                SET
                    ruler_telegram_id = %s,
                    active = TRUE
                WHERE id = %s
                """,
                (
                    ruler_id,
                    country_id,
                ),
            )


        conn.commit()


    context.user_data.pop(
        "ruler_country_id",
        None,
    )


    ruler_name = (
        player[0]
        or player[1]
        or str(ruler_id)
    )


    await query.edit_message_text(
        "✅ حاکم با موفقیت تعیین شد.\n\n"
        + country[1]
        + " "
        + country[0]
        + "\n\n"
        "👑 حاکم: "
        + ruler_name
        + "\n"
        "🏛️ حکومت: "
        + str(country[2])
        + "\n"
        "🟢 کشور اکنون فعال است."
    )


# ---------------- PLAYER PROFILE ----------------


async def my_profile(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    query = update.callback_query
    await query.answer()


    user_id = query.from_user.id


    with db() as conn:

        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT
                    first_name,
                    username,
                    country_id,
                    role,
                    money,
                    bank_money,
                    quiz_passed
                FROM players
                WHERE telegram_id = %s
                """,
                (user_id,),
            )

            player = cur.fetchone()


    if not player:

        await query.edit_message_text(
            "❌ پروفایل شما پیدا نشد.\n"
            "دوباره /start را بزنید."
        )

        return


    (
        first_name,
        username,
        country_id,
        role,
        money,
        bank_money,
        quiz_passed,
    ) = player


    country_name = "بدون کشور"


    if country_id:

        with db() as conn:

            with conn.cursor() as cur:

                cur.execute(
                    """
                    SELECT name, flag
                    FROM countries
                    WHERE id = %s
                    """,
                    (country_id,),
                )

                country = cur.fetchone()


                if country:

                    country_name = (
                        country[1]
                        + " "
                        + country[0]
                    )


    keyboard = [
        [
            InlineKeyboardButton(
                "🔙 بازگشت",
                callback_data="player_home",
            )
        ]
    ]


    await query.edit_message_text(
        "👤 پروفایل بازیکن\n\n"
        "👤 نام: "
        + str(first_name or "-")
        + "\n"
        "🆔 شناسه: "
        + str(user_id)
        + "\n"
        "🌍 کشور: "
        + country_name
        + "\n"
        "🎖️ نقش: "
        + str(role or "player")
        + "\n"
        "💰 پول: "
        + str(money or 0)
        + "\n"
        "🏦 بانک: "
        + str(bank_money or 0)
        + "\n"
        "📝 آزمون: "
        + (
            "قبول شده ✅"
            if quiz_passed
            else "قبول نشده ❌"
        ),
        reply_markup=InlineKeyboardMarkup(
            keyboard
        ),
    )


# ---------------- COUNTRY MENU ----------------


async def country_menu(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    query = update.callback_query
    await query.answer()


    with db() as conn:

        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT
                    id,
                    name,
                    flag,
                    government_type
                FROM countries
                WHERE active = TRUE
                ORDER BY name
                """
            )

            countries = cur.fetchall()


    if not countries:

        await query.edit_message_text(
            "🌍 هنوز هیچ کشور فعالی وجود ندارد."
        )

        return


    keyboard = []


    for country_id, name, flag, government in countries:

        keyboard.append(
            [
                InlineKeyboardButton(
                    flag
                    + " "
                    + name,
                    callback_data=(
                        "country_info:"
                        + str(country_id)
                    ),
                )
            ]
        )


    keyboard.append(
        [
            InlineKeyboardButton(
                "🔙 بازگشت",
                callback_data="player_home",
            )
        ]
    )


    await query.edit_message_text(
        "🌍 کشورهای فعال Nexora\n\n"
        "کشور موردنظر را انتخاب کنید:",
        reply_markup=InlineKeyboardMarkup(
            keyboard
        ),
    )


# ---------------- COUNTRY INFO ----------------


async def country_info(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    query = update.callback_query
    await query.answer()


    try:

        country_id = int(
            query.data.split(
                ":",
                1,
            )[1]
        )

    except (ValueError, IndexError):

        await query.edit_message_text(
            "❌ کشور نامعتبر است."
        )

        return


    with db() as conn:

        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT
                    name,
                    flag,
                    description,
                    government_type,
                    ruler_telegram_id,
                    treasury,
                    daily_income,
                    public_satisfaction,
                    stability,
                    active
                FROM countries
                WHERE id = %s
                """,
                (country_id,),
            )

            country = cur.fetchone()


    if not country:

        await query.edit_message_text(
            "❌ کشور پیدا نشد."
        )

        return


    (
        name,
        flag,
        description,
        government,
        ruler_id,
        treasury,
        daily_income,
        satisfaction,
        stability,
        active,
    ) = country


    if not active:

        await query.edit_message_text(
            "🔴 این کشور هنوز فعال نشده است."
        )

        return


    ruler_name = "تعیین نشده"


    if ruler_id:

        with db() as conn:

            with conn.cursor() as cur:

                cur.execute(
                    """
                    SELECT first_name, username
                    FROM players
                    WHERE telegram_id = %s
                    """,
                    (ruler_id,),
                )

                ruler = cur.fetchone()


                if ruler:

                    ruler_name = (
                        ruler[0]
                        or ruler[1]
                        or str(ruler_id)
                    )


    text = (
        flag
        + " "
        + name
        + "\n\n"
        + (
            description
            if description
            else "توضیحی ثبت نشده است."
        )
        + "\n\n"
        + "🏛️ حکومت: "
        + str(government or "-")
        + "\n"
        + "👑 حاکم: "
        + str(ruler_name)
        + "\n"
        + "💰 خزانه: "
        + str(treasury or 0)
        + "\n"
        + "📈 درآمد روزانه: "
        + str(daily_income or 0)
        + "\n"
        + "❤️ رضایت مردمی: "
        + str(satisfaction or 0)
        + "%"
        + "\n"
        + "🛡️ ثبات کشور: "
        + str(stability or 0)
        + "%"
    )


    keyboard = [
        [
            InlineKeyboardButton(
                "🔙 بازگشت",
                callback_data="country_menu",
            )
        ]
    ]


    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(
            keyboard
        ),
    )
# ---------------- BACK TO PLAYER MENU ----------------


async def player_home_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    query = update.callback_query

    await query.answer()

    await player_home(
        update,
        context,
    )


# ---------------- LINKS ADMIN ----------------


async def links_admin(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    query = update.callback_query

    await query.answer()

    if not is_owner(query.from_user.id):

        await query.edit_message_text(
            "⛔ دسترسی غیرمجاز."
        )

        return


    with db() as conn:

        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT key, title, url
                FROM official_links
                ORDER BY key
                """
            )

            links = cur.fetchall()


    if not links:

        text = "🔗 هنوز هیچ لینکی ثبت نشده است."

    else:

        text = "🔗 لینک‌های رسمی Nexora\n\n"

        for key, title, url in links:

            text += (
                title
                + "\n"
                + (
                    url
                    if url
                    else "❌ تنظیم نشده"
                )
                + "\n\n"
            )


    keyboard = [
        [
            InlineKeyboardButton(
                "🔙 بازگشت",
                callback_data="owner_panel",
            )
        ]
    ]


    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(
            keyboard
        ),
    )


# ---------------- MAIN ----------------


def main():

    init_database()


    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )


    # START

    application.add_handler(
        CommandHandler(
            "start",
            start,
        )
    )


    # OWNER

    application.add_handler(
        CallbackQueryHandler(
            claim_owner,
            pattern=r"^claim_owner$",
        )
    )

    application.add_handler(
        CallbackQueryHandler(
            cancel_owner,
            pattern=r"^cancel_owner$",
        )
    )

    application.add_handler(
        CallbackQueryHandler(
            owner_panel,
            pattern=r"^owner_panel$",
        )
    )


    # COUNTRY ADMIN

    application.add_handler(
        CallbackQueryHandler(
            country_admin,
            pattern=r"^country_admin$",
        )
    )

    application.add_handler(
        CallbackQueryHandler(
            add_country,
            pattern=r"^add_country$",
        )
    )

    application.add_handler(
        CallbackQueryHandler(
            country_list,
            pattern=r"^country_list$",
        )
    )

    application.add_handler(
        CallbackQueryHandler(
            assign_ruler,
            pattern=r"^assign_ruler$",
        )
    )

    application.add_handler(
        CallbackQueryHandler(
            choose_ruler_country,
            pattern=r"^choose_ruler_country:",
        )
    )

    application.add_handler(
        CallbackQueryHandler(
            set_ruler,
            pattern=r"^set_ruler:",
        )
    )

    application.add_handler(
        CallbackQueryHandler(
            select_government,
            pattern=r"^gov:",
        )
    )


    # PLAYER

    application.add_handler(
        CallbackQueryHandler(
            country_menu,
            pattern=r"^country_menu$",
        )
    )

    application.add_handler(
        CallbackQueryHandler(
            country_info,
            pattern=r"^country_info:",
        )
    )

    application.add_handler(
        CallbackQueryHandler(
            my_profile,
            pattern=r"^my_profile$",
        )
    )

    application.add_handler(
        CallbackQueryHandler(
            player_home_callback,
            pattern=r"^player_home$",
        )
    )


    # LINKS

    application.add_handler(
        CallbackQueryHandler(
            links_admin,
            pattern=r"^links_admin$",
        )
    )


    # TEXT INPUT

    application.add_handler(
        MessageHandler(
            filters.TEXT
            & ~filters.COMMAND,
            receive_country,
        )
    )


    # WEB SERVER

    Thread(
        target=run_web,
        daemon=True,
    ).start()


    print(
        "Nexora bot started successfully."
    )


    application.run_polling()


if __name__ == "__main__":

    main()
