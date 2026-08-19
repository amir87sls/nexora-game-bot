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
        keyboard = [
            [
                InlineKeyboardButton(
                    "👑 قبول مالکیت",
                    callback_data="claim_owner"
                ),
                InlineKeyboardButton(
                    "❌ انصراف",
                    callback_data="cancel_owner"
                )
            ]
        ]

        await update.message.reply_text(
            "🌍 به Nexora خوش آمدید!\n\n"
            "هنوز مالک بازی تعیین نشده است.\n"
            "اگر شما سازنده بازی هستید، می‌توانید مالکیت Nexora را بر عهده بگیرید.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif owner[0] == user.id:
        await update.message.reply_text(
            "👑 خوش آمدید مالک Nexora!\n\n"
            "پنل مدیریت به‌زودی در اینجا فعال می‌شود."
        )

    else:
        await update.message.reply_text(
            "🌍 به Nexora خوش آمدید!\n\n"
            "حساب شما در سیستم ثبت شد. 🔥"
        )


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
        "شما با موفقیت به‌عنوان مالک Nexora ثبت شدید. 🔒\n\n"
        "مالکیت به‌صورت دائمی در دیتابیس ذخیره شد."
    )


async def cancel_owner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    await query.edit_message_text(
        "❌ درخواست مالکیت لغو شد.\n\n"
        "برای دریافت دوباره گزینه مالکیت، /start را بزنید."
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

    await application.initialize()
    await application.start()
    await application.updater.start_polling()

    await asyncio.Event().wait()


def main():
    Thread(target=run_web, daemon=True).start()
    asyncio.run(run_bot())


if __name__ == "__main__":
    main()
