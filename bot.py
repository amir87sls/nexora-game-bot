import os
from threading import Thread

import psycopg
from flask import Flask

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
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
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not configured.")

    with db() as conn:
        with conn.cursor() as cur:

            cur.execute("""
                CREATE TABLE IF NOT EXISTS players (
                    id BIGSERIAL PRIMARY KEY,
                    telegram_id BIGINT UNIQUE NOT NULL,
                    username TEXT,
                    first_name TEXT,
                    country_id BIGINT,
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
                CREATE TABLE IF NOT EXISTS official_links (
                    key TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    url TEXT DEFAULT ''
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS countries (
                    id BIGSERIAL PRIMARY KEY,
                    name TEXT UNIQUE NOT NULL,
                    flag TEXT DEFAULT '🌍',
                    description TEXT DEFAULT '',
                    active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS quiz_questions (
                    id BIGSERIAL PRIMARY KEY,
                    question TEXT NOT NULL,
                    option_a TEXT NOT NULL,
                    option_b TEXT NOT NULL,
                    option_c TEXT NOT NULL,
                    option_d TEXT NOT NULL,
                    correct_option TEXT NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS quiz_attempts (
                    id BIGSERIAL PRIMARY KEY,
                    telegram_id BIGINT NOT NULL,
                    score INTEGER DEFAULT 0,
                    total INTEGER DEFAULT 0,
                    passed BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
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
                    INSERT INTO official_links (key, title)
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
                "SELECT telegram_id FROM owner WHERE id = 1"
            )
            return cur.fetchone()


def is_owner(user_id):
    owner = get_owner()
    return owner is not None and owner[0] == user_id


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    with db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO players
                (telegram_id, username, first_name)
                VALUES (%s, %s, %s)
                ON CONFLICT (telegram_id)
                DO UPDATE SET
                    username = EXCLUDED.username,
                    first_name = EXCLUDED.first_name
                """,
                (user.id, user.username, user.first_name),
            )
        conn.commit()

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
        await send_owner_panel(update, context)
        return

    await send_player_menu(update, context)


async def send_player_menu(update, context):
    keyboard = [
        [
            InlineKeyboardButton(
                "🌍 انتخاب کشور",
                callback_data="choose_country",
            )
        ],
        [
            InlineKeyboardButton(
                "🔗 لینک‌های رسمی",
                callback_data="player_links",
            )
        ],
    ]

    text = (
        "🌍 به Nexora خوش آمدید!\n\n"
        "حساب شما ثبت شده است. 🔥\n\n"
        "برای شروع کشور خود را انتخاب کنید."
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


async def claim_owner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = query.from_user

    with db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT telegram_id FROM owner WHERE id = 1"
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
                (id, telegram_id, username, first_name)
                VALUES (1, %s, %s, %s)
                """,
                (user.id, user.username, user.first_name),
            )

        conn.commit()

    await query.edit_message_text(
        "👑 تبریک!\n\n"
        "شما با موفقیت به عنوان مالک Nexora ثبت شدید. 🔒\n\n"
        "مالکیت دائمی است و بازیکنان دیگر نمی‌توانند آن را بگیرند."
    )


async def cancel_owner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    await query.edit_message_text(
        "❌ درخواست مالکیت لغو شد.\n\n"
        "برای تلاش دوباره /start را بزنید."
    )


async def send_owner_panel(update, context):
    keyboard = [
        [
            InlineKeyboardButton(
                "🔗 لینک‌های رسمی",
                callback_data="links",
            )
        ],
        [
            InlineKeyboardButton(
                "🌍 مدیریت کشورها",
                callback_data="countries",
            )
        ],
        [
            InlineKeyboardButton(
                "📝 مدیریت آزمون",
                callback_data="quiz_admin",
            )
        ],
        [
            InlineKeyboardButton(
                "👥 بازیکنان",
                callback_data="players",
            )
        ],
    ]

    text = "👑 پنل مالک Nexora\n\nیک بخش را انتخاب کنید:"

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


async def owner_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not is_owner(query.from_user.id):
        await query.edit_message_text("⛔ دسترسی غیرمجاز.")
        return

    await send_owner_panel(update, context)


# ---------------- LINKS ----------------


async def links_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not is_owner(query.from_user.id):
        await query.edit_message_text("⛔ دسترسی غیرمجاز.")
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

    text = "🔗 مدیریت لینک‌های رسمی\n\n"
    keyboard = []

    for key, title, url in links:
        text += title + "\n"
        text += (url if url else "❌ تنظیم نشده") + "\n\n"

        keyboard.append(
            [
                InlineKeyboardButton(
                    "✏️ ویرایش " + title,
                    callback_data="edit_link:" + key,
                )
            ]
        )

    keyboard.append(
        [
            InlineKeyboardButton(
                "🔙 بازگشت",
                callback_data="owner_panel",
            )
        ]
    )

    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def edit_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not is_owner(query.from_user.id):
        await query.edit_message_text("⛔ دسترسی غیرمجاز.")
        return

    key = query.data.split(":", 1)[1]

    with db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT title FROM official_links WHERE key = %s",
                (key,),
            )
            row = cur.fetchone()

    if not row:
        await query.edit_message_text("❌ لینک پیدا نشد.")
        return

    context.user_data["editing_link"] = key

    await query.edit_message_text(
        "✏️ ویرایش " + row[0] + "\n\n"
        "لینک جدید را در یک پیام ارسال کنید.\n\n"
        "مثال:\n"
        "https://t.me/example"
    )


async def save_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id):
        return

    key = context.user_data.get("editing_link")

    if not key:
        return

    url = update.message.text.strip()

    if not url.startswith(
        ("http://", "https://", "tg://")
    ):
        await update.message.reply_text(
            "❌ لینک معتبر نیست."
        )
        return

    with db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE official_links
                SET url = %s
                WHERE key = %s
                """,
                (url, key),
            )
        conn.commit()

    context.user_data.pop("editing_link", None)

    await update.message.reply_text(
        "✅ لینک با موفقیت ذخیره شد."
    )


async def player_links(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    with db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT title, url
                FROM official_links
                ORDER BY key
                """
            )
            links = cur.fetchall()

    text = "🔗 لینک‌های رسمی Nexora\n\n"
    keyboard = []

    for title, url in links:
        if url:
            keyboard.append(
                [
                    InlineKeyboardButton(
                        title,
                        url=url,
                    )
                ]
            )

    keyboard.append(
        [
            InlineKeyboardButton(
                "🔙 بازگشت",
                callback_data="player_menu",
            )
        ]
    )

    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


# ---------------- COUNTRIES ----------------


async def countries_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not is_owner(query.from_user.id):
        await query.edit_message_text("⛔ دسترسی غیرمجاز.")
        return

    keyboard = [
        [
            InlineKeyboardButton(
                "➕ افزودن کشور",
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
                "🔙 بازگشت",
                callback_data="owner_panel",
            )
        ],
    ]

    await query.edit_message_text(
        "🌍 مدیریت کشورها",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def add_country(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not is_owner(query.from_user.id):
        await query.edit_message_text("⛔ دسترسی غیرمجاز.")
        return

    context.user_data["country_step"] = "name"

    await query.edit_message_text(
        "➕ افزودن کشور\n\n"
        "نام کشور را ارسال کنید.\n\n"
        "مثال:\nایران"
    )


async def receive_country(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id):
        return

    step = context.user_data.get("country_step")

    if step == "name":
        context.user_data["country_name"] = (
            update.message.text.strip()
        )
        context.user_data["country_step"] = "flag"

        await update.message.reply_text(
            "🏳️ حالا پرچم کشور را ارسال کنید.\n\n"
            "مثال: 🇮🇷"
        )
        return

    if step == "flag":
        context.user_data["country_flag"] = (
            update.message.text.strip()
        )
        context.user_data["country_step"] = "description"

        await update.message.reply_text(
            "📝 توضیح کشور را ارسال کنید.\n\n"
            "اگر توضیح نمی‌خواهید بنویسید: ندارد"
        )
        return

    if step == "description":
        name = context.user_data.get("country_name")
        flag = context.user_data.get("country_flag")
        description = update.message.text.strip()

        if description == "ندارد":
            description = ""

        try:
            with db() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO countries
                        (name, flag, description)
                        VALUES (%s, %s, %s)
                        """,
                        (name, flag, description),
                    )
                conn.commit()

            await update.message.reply_text(
                "✅ کشور "
                + flag
                + " "
                + name
                + " با موفقیت اضافه شد."
            )

        except psycopg.errors.UniqueViolation:
            await update.message.reply_text(
                "❌ این کشور قبلاً اضافه شده است."
            )

        context.user_data.pop("country_step", None)
        context.user_data.pop("country_name", None)
        context.user_data.pop("country_flag", None)


async def country_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not is_owner(query.from_user.id):
        await query.edit_message_text("⛔ دسترسی غیرمجاز.")
        return

    with db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, name, flag, active
                FROM countries
                ORDER BY name
                """
            )
            countries = cur.fetchall()

    if not countries:
        text = "📋 هنوز هیچ کشوری اضافه نشده است."
    else:
        text = "📋 لیست کشورها\n\n"

        for country_id, name, flag, active in countries:
            status = "🟢 فعال" if active else "🔴 غیرفعال"

            text += (
                flag
                + " "
                + name
                + " — "
                + status
                + "\n"
            )

    keyboard = [
        [
            InlineKeyboardButton(
                "➕ افزودن کشور",
                callback_data="add_country",
            )
        ],
        [
            InlineKeyboardButton(
                "🔙 بازگشت",
                callback_data="countries",
            )
        ],
    ]

    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def choose_country(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    with db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, name, flag
                FROM countries
                WHERE active = TRUE
                ORDER BY name
                """
            )
            countries = cur.fetchall()

    if not countries:
        await query.edit_message_text(
            "🌍 هنوز هیچ کشور فعالی برای انتخاب وجود ندارد."
        )
        return

    keyboard = []

    for country_id, name, flag in countries:
        keyboard.append(
            [
                InlineKeyboardButton(
                    flag + " " + name,
                    callback_data=(
                        "select_country:"
                        + str(country_id)
                    ),
                )
            ]
        )

    await query.edit_message_text(
        "🌍 کشور خود را انتخاب کنید:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def select_country(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    country_id = int(
        query.data.split(":", 1)[1]
    )

    with db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT name, flag, description
                FROM countries
                WHERE id = %s
                AND active = TRUE
                """,
                (country_id,),
            )

            country = cur.fetchone()

            if not country:
                await query.edit_message_text(
                    "❌ این کشور پیدا نشد."
                )
                return

            cur.execute(
                """
                UPDATE players
                SET country_id = %s
                WHERE telegram_id = %s
                """,
     
