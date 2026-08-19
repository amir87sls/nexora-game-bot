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
                    country TEXT,
                    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                )
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

            default_links = [
                ("news", "📰 کانال اخبار", ""),
                ("chat", "💬 گپ بازیکنان", ""),
                ("rules", "📚 قوانین و آموزش", ""),
                ("bot", "🤖 ربات Nexora", ""),
                ("owner", "👑 پیوی مالک", ""),
            ]

            for key, title, url in default_links:
                cur.execute("""
                    INSERT INTO official_links (key, title, url)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (key) DO NOTHING
                """, (key, title, url))

        conn.commit()


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


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO players (telegram_id, username, first_name)
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
            "هنوز مالک بازی تعیین نشده است.\n"
            "اگر شما سازنده بازی هستید، می‌توانید مالکیت Nexora را بر عهده بگیرید.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif owner[0] == user.id:
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

    else:
        await update.message.reply_text(
            "🌍 به Nexora خوش آمدید!\n\n"
            "حساب شما در سیستم ثبت شد. 🔥"
        )


async def owner_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not is_owner(query.from_user.id):
        await query.edit_message_text("⛔ دسترسی غیرمجاز.")
        return

    keyboard = [
        [InlineKeyboardButton("🌍 مدیریت کشورها", callback_data="countries")],
        [InlineKeyboardButton("👤 بازیکنان", callback_data="players")],
        [InlineKeyboardButton("🛒 شاپ", callback_data="shop")],
        [InlineKeyboardButton("💳 پرداخت‌ها", callback_data="payments")],
        [InlineKeyboardButton("🔗 لینک‌های رسمی", callback_data="official_links")],
        [InlineKeyboardButton("⚙️ تنظیمات بازی", callback_data="settings")],
        [InlineKeyboardButton("🏁 مدیریت سیزن", callback_data="seasons")],
    ]

    await query.edit_message_text(
        "👑 پنل مدیریت Nexora\n\n"
        "یک بخش را انتخاب کنید:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


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

    keyboard = []

    for key, title, url in links:
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

    text = "🔗 مدیریت لینک‌های رسمی\n\n"

    for key, title, url in links:
        text += f"{title}\n"
        text += f"{url if url else '❌ تنظیم نشده'}\n\n"

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
        await query.edit_message_text("❌ این لینک پیدا نشد.")
        return

    title = result[0]

    context.user_data["editing_link"] = key

    keyboard = [[
        InlineKeyboardButton(
            "❌ لغو",
            callback_data="cancel_edit_link"
        )
    ]]

    await query.edit_message_text(
        f"✏️ ویرایش {title}\n\n"
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
        with conn.cursor() as cur:
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


async def cancel_edit_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    context.user_data.pop("editing_link", None)

    await official_links(update, context)


async def claim_owner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = query.from_user

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:

            cur.execute("""
                SELECT telegram_id
                FROM owner
                WHERE id = 1
            """)

            existing_owner = cur.fetchone()

            if existing_owner is not None:
                await query.edit_message_text(
                    "🔒 مالک Nexora قبلاً تعیین شده است."
                )
                return

            cur.execute("""
                INSERT INTO owner (
                    id,
                    telegram_id,
                    username,
                    first_name
                )
                VALUES (1, %s, %s, %s)
            """, (
                user.id,
                user.username,
                user.first_name
            ))

        conn.commit()

    await query.edit_message_text(
        "👑 تبریک!\n\n"
        "شما با موفقیت به‌عنوان مالک Nexora ثبت شدید. 🔒"
    )


async def cancel_owner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    await query.edit_message_text(
        "❌ درخواست مالکیت لغو شد."
    )


def run_web():
    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", 10000))
    )


async def run_bot():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is not configured.")

    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not configured.")

    init_database()

    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))

    application.add_handler(
        CallbackQueryHandler(
            claim_owner,
            pattern="^claim_owner$"
        )
    )

    application.add_handler(
        CallbackQueryHandler(
            cancel_owner,
            pattern="^cancel_owner$"
        )
    )

    application.add_handler(
        CallbackQueryHandler(
            owner_panel,
            pattern="^owner_panel$"
        )
    )

    application.add_handler(
        CallbackQueryHandler(
            official_links,
            pattern="^official_links$"
        )
    )

    application.add_handler(
        CallbackQueryHandler(
            edit_link,
            pattern="^edit_link:"
        )
    )

    application.add_handler(
        CallbackQueryHandler(
            cancel_edit_link,
            pattern="^cancel_edit_link$"
        )
    )

    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            save_link
        )
    )

    await application.initialize()
    await application.start()
    await application.updater.start_polling()

    await asyncio.Event().wait()


def main():
    Thread(target=run_web, daemon=True).start()
    asyncio.run(run_bot())


if __name__ == "__main__":
    main()
