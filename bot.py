import os
import asyncio
import psycopg
from flask import Flask
from threading import Thread
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
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


# =========================
# DATABASE
# =========================

def init_database():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not configured.")

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:

            cur.execute("""
                CREATE TABLE IF NOT EXISTS players (
                    id BIGSERIAL PRIMARY KEY,
                    telegram_id BIGINT UNIQUE NOT NULL,
                    username TEXT,
                    first_name TEXT,
                    country_id BIGINT,
                    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cur.execute("""
                ALTER TABLE players
                ADD COLUMN IF NOT EXISTS country_id BIGINT
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS seasons (
                    id BIGSERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    status TEXT DEFAULT 'active',
                    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS game_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
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
                    url TEXT
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

            default_links = [
                ("bot", "🤖 ربات Nexora", ""),
                ("chat", "💬 گپ بازیکنان", ""),
                ("news", "📰 کانال اخبار", ""),
                ("owner", "👑 پیوی مالک", ""),
                ("rules", "📚 قوانین و آموزش", ""),
            ]

            for key, title, url in default_links:
                cur.execute("""
                    INSERT INTO official_links (key, title, url)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (key) DO NOTHING
                """, (key, title, url))

        conn.commit()


# =========================
# OWNER
# =========================

def get_owner():
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT telegram_id
                FROM owner
                WHERE id = 1
            """)
            return cur.fetchone()


def is_owner(user_id):
    owner = get_owner()
    return owner is not None and owner[0] == user_id


# =========================
# START
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user = update.effective_user

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:

            cur.execute("""
                INSERT INTO players (
                    telegram_id,
                    username,
                    first_name
                )
                VALUES (%s, %s, %s)

                ON CONFLICT (telegram_id)
                DO UPDATE SET
                    username = EXCLUDED.username,
                    first_name = EXCLUDED.first_name
            """, (
                user.id,
                user.username,
                user.first_name
            ))

        conn.commit()

    owner = get_owner()

    # اگر هنوز مالک وجود ندارد
    if owner is None:

        keyboard = [[
            InlineKeyboardButton(
                "👑 قبول مالکیت",
                callback_data="claim_owner"
            ),
            InlineKeyboardButton(
                "❌ انصراف",
                callback_data="cancel_owner"
            )
        ]]

        await update.message.reply_text(
            "🌍 به Nexora خوش آمدید!\n\n"
            "هنوز مالک بازی تعیین نشده است.\n\n"
            "اگر شما سازنده بازی هستید، می‌توانید مالکیت Nexora را بر عهده بگیرید.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        return

    # اگر خود مالک است
    if owner[0] == user.id:

        keyboard = [[
            InlineKeyboardButton(
                "👑 پنل مالک",
                callback_data="owner_panel"
            )
        ]]

        await update.message.reply_text(
            "👑 خوش آمدید مالک Nexora!",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        return

    # بازیکن عادی
    keyboard = [[
        InlineKeyboardButton(
            "🌍 انتخاب کشور",
            callback_data="choose_country"
        )
    ]]

    await update.message.reply_text(
        "🌍 به Nexora خوش آمدید!\n\n"
        "حساب شما در سیستم ثبت شد. 🔥\n\n"
        "برای شروع کشور خود را انتخاب کنید:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# =========================
# OWNER PANEL
# =========================

async def owner_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    if not is_owner(query.from_user.id):
        await query.edit_message_text("⛔ دسترسی غیرمجاز.")
        return

    keyboard = [
        [
            InlineKeyboardButton(
                "🌍 مدیریت کشورها",
                callback_data="countries"
            )
        ],
        [
            InlineKeyboardButton(
                "👤 بازیکنان",
                callback_data="players"
            )
        ],
        [
            InlineKeyboardButton(
                "🛒 شاپ",
                callback_data="shop"
            )
        ],
        [
            InlineKeyboardButton(
                "💳 پرداخت‌ها",
                callback_data="payments"
            )
        ],
        [
            InlineKeyboardButton(
                "🔗 لینک‌های رسمی",
                callback_data="official_links"
            )
        ],
        [
            InlineKeyboardButton(
                "⚙️ تنظیمات بازی",
                callback_data="settings"
            )
        ],
        [
            InlineKeyboardButton(
                "🏁 مدیریت سیزن",
                callback_data="seasons"
            )
        ],
    ]

    await query.edit_message_text(
        "👑 پنل مدیریت Nexora\n\n"
        "یک بخش را انتخاب کنید:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# =========================
# OFFICIAL LINKS
# =========================

async def official_links(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    if not is_owner(query.from_user.id):
        await query.edit_message_text("⛔ دسترسی غیرمجاز.")
        return

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:

            cur.execute("""
                SELECT key, title, url
                FROM official_links
                ORDER BY
                    CASE key
                        WHEN 'bot' THEN 1
                        WHEN 'chat' THEN 2
                        WHEN 'news' THEN 3
                        WHEN 'owner' THEN 4
                        WHEN 'rules' THEN 5
                    END
            """)

            links = cur.fetchall()

    text = "🔗 مدیریت لینک‌های رسمی\n\n"

    keyboard = []

    for key, title, url in links:

        text += f"{title}\n"
        text += f"{url if url else '❌ تنظیم نشده'}\n\n"

        keyboard.append([
            InlineKeyboardButton(
                f"✏️ {title}",
                callback_data=f"edit_link:{key}"
            )
        ])

    keyboard.append([
        InlineKeyboardButton(
            "🔙 بازگشت به پنل",
            callback_data="owner_panel"
        )
    ])

    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def edit_link(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    if not is_owner(query.from_user.id):
        await query.edit_message_text("⛔ دسترسی غیرمجاز.")
        return

    key = query.data.split(":", 1)[1]

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:

            cur.execute("""
                SELECT title
                FROM official_links
                WHERE key = %s
            """, (key,))

            result = cur.fetchone()

    if not result:
        await query.edit_message_text(
            "❌ این لینک پیدا نشد."
        )
        return

    context.user_data["editing_link"] = key

    keyboard = [[
        InlineKeyboardButton(
            "❌ لغو",
            callback_data="cancel_edit_link"
        )
    ]]

    await query.edit_message_text(
        f"✏️ ویرایش {result[0]}\n\n"
        "لینک جدید را در یک پیام ارسال کنید.\n\n"
        "مثال:\n"
        "https://t.me/example",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def save_link(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not is_owner(update.effective_user.id):
        return

    key = context.user_data.get("editing_link")

    if not key:
        return

    url = update.message.text.strip()

    if not (
        url.startswith("https://")
        or url.startswith("http://")
        or url.startswith("tg://")
    ):

        await update.message.reply_text(
            "❌ لینک معتبر نیست.\n\n"
            "لطفاً لینک را با https:// یا http:// ارسال کنید."
        )

        return

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor():

            cur.execute("""
                UPDATE official_links
                SET url = %s
                WHERE key = %s
            """, (url, key))

        conn.commit()

    context.user_data.pop("editing_link", None)

    await update.message.reply_text(
        "✅ لینک با موفقیت ذخیره شد."
    )


async def cancel_edit_link(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query
    await query.answer()

    context.user_data.pop("editing_link", None)

    await official_links(update, context)


# =========================
# COUNTRIES OWNER MENU
# =========================

async def countries_menu(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
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
                "➕ افزودن کشور",
                callback_data="add_country"
            )
        ],
        [
            InlineKeyboardButton(
                "📋 لیست کشورها",
                callback_data="country_list"
            )
        ],
        [
            InlineKeyboardButton(
                "🔙 بازگشت",
                callback_data="owner_panel"
            )
        ]
    ]

    await query.edit_message_text(
        "🌍 مدیریت کشورها\n\n"
        "کشورها را از این بخش مدیریت کنید.",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def country_list(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query
    await query.answer()

    if not is_owner(query.from_user.id):
        await query.edit_message_text(
            "⛔ دسترسی غیرمجاز."
        )
        return

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor():

            cur.execute("""
                SELECT id, name, flag, active
                FROM countries
                ORDER BY id
            """)

            countries = cur.fetchall()

    if not countries:

        text = "📋 هنوز هیچ کشوری اضافه نشده است."

    else:

        text = "📋 لیست کشورها\n\n"

        for country_id, name, flag, active in countries:

            status = (
                "🟢 فعال"
                if active
                else
                "🔴 غیرفعال"
            )

            text += (
                f"{flag} {name} — {status}\n"
            )

    keyboard = []

    for country_id, name, flag, active in countries:

        keyboard.append([
            InlineKeyboardButton(
                f"⚙️ {flag} {name}",
                callback_data=f"manage_country:{country_id}"
            )
        ])

    keyboard.append([
        InlineKeyboardButton(
            "➕ افزودن کشور",
            callback_data="add_country"
        )
    ])

    keyboard.append([
        InlineKeyboardButton(
            "🔙 بازگشت",
            callback_data="countries"
        )
    ])

    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# =========================
# ADD COUNTRY
# =========================

async def add_country(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query
    await query.answer()

    if not is_owner(query.from_user.id):
        await query.edit_message_text(
            "⛔ دسترسی غیرمجاز."
        )
        return

    context.user_data["adding_country"] = "name"

    await query.edit_message_text(
        "➕ افزودن کشور\n\n"
        "نام کشور را ارسال کنید.\n\n"
        "مثال:\n"
        "ایران"
    )


async def receive_country_name(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not is_owner(update.effective_user.id):
        return

    if context.user_data.get("adding_country") != "name":
        return

    context.user_data["new_country_name"] = (
        update.message.text.strip()
    )

    context.user_data["adding_country"] = "flag"

    await update.message.reply_text(
        "🇮🇷 پرچم یا ایموجی کشور را ارسال کنید.\n\n"
        "مثال:\n"
        "🇮🇷"
    )


async def receive_country_flag(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not is_owner(update.effective_user.id):
        return

    if context.user_data.get("adding_country") != "flag":
        return

    context.user_data["new_country_flag"] = (
        update.message.text.strip()
    )

    context.user_data["adding_country"] = "description"

    await update.message.reply_text(
        "📝 توضیح کشور را ارسال کنید.\n\n"
        "اگر توضیح نمی‌خواهید، بنویسید:\n"
        "ندارد"
    )


async def receive_country_description(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not is_owner(update.effective_user.id):
        return

    if context.user_data.get("adding_country") != "description":
        return

    name = context.user_data.get(
        "new_country_name"
    )

    flag = context.user_data.get(
        "new_country_flag"
    )

    description = update.message.text.strip()

    if description == "ندارد":
        description = ""

    try:

        with psycopg.connect(DATABASE_URL) as conn:
            with conn.cursor():

                cur.execute("""
                    INSERT INTO countries (
                        name,
                        flag,
                        description,
                        active
                    )
                    VALUES (%s, %s, %s, TRUE)
                """, (
                    name,
                    flag,
                    description
                ))

            conn.commit()

        message = (
            "✅ کشور با موفقیت اضافه شد!\n\n"
            f"{flag} {name}\n\n"
            f"{description if description else 'بدون توضیح'}"
        )

    except psycopg.errors.UniqueViolation:

        message = (
            "❌ این کشور قبلاً وجود دارد."
        )

    context.user_data.pop(
        "adding_country",
        None
    )

    context.user_data.pop(
        "new_country_name",
        None
    )

    context.user_data.pop(
        "new_country_flag",
        None
    )

    await update.message.reply_text(
        message
    )


# =========================
# PLAYER COUNTRY SELECTION
# =========================

async def choose_country(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query
    await query.answer()

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor():

            cur.execute("""
                SELECT id, name, flag
                FROM countries
                WHERE active = TRUE
                ORDER BY name
            """)

            countries = cur.fetchall()

    if not countries:

        await query.edit_message_text(
            "🌍 در حال حاضر هیچ کشور فعالی برای انتخاب وجود ندارد."
        )

        return

    keyboard = []

    for country_id, name, flag in countries:

        keyboard.append([
            InlineKeyboardButton(
                f"{flag} {name}",
                callback_data=f"select_country:{country_id}"
            )
        ])

    await query.edit_message_text(
        "🌍 انتخاب کشور\n\n"
        "کشور موردنظر خود را انتخاب کنید:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def select_country(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id

    country_id = int(
        query.data.split(":", 1)[1]
    )

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor():

            cur.execute("""
                SELECT name, flag, description
                FROM countries
                WHERE id = %s
                AND active = TRUE
            """, (country_id,))

            country = cur.fetchone()

            if not country:

                await query.edit_message_text(
                    "❌ این کشور دیگر فعال نیست."
                )

                return

            cur.execute("""
                UPDATE players
                SET country_id = %s
                WHERE telegram_id = %s
            """, (
                country_id,
                user_id
            ))

        conn.commit()

    name, flag, description = country

    await query.edit_message_text(
        f"✅ کشور شما با موفقیت انتخاب شد!\n\n"
        f"{flag} {name}\n\n"
        f"{description if description else 'توضیحی برای این کشور ثبت نشده است.'}"
    )


# =========================
# COUNTRY MANAGEMENT
# =========================

async def manage_country(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query
    await query.answer()

    if not is_owner(query.from_user.id):
        await query.edit_message_text(
            "⛔ دسترسی غیرمجاز."
        )
        return

    country_id = int(
        query.data.split(":", 1)[1]
    )

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor():

            cur.execute("""
                SELECT name, flag, des
