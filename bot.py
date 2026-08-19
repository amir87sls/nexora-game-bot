import os
from threading import Thread

import psycopg
from flask import Flask

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

# =========================================================
# CONFIG
# =========================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not configured.")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not configured.")


# =========================================================
# FLASK
# =========================================================

app = Flask(__name__)


@app.route("/")
def home():
    return "Nexora Bot is running!"


@app.route("/healthz")
def healthz():
    return "OK"


def run_web():
    port = int(os.getenv("PORT", "10000"))
    app.run(
        host="0.0.0.0",
        port=port,
    )


# =========================================================
# DATABASE
# =========================================================

def db():
    return psycopg.connect(DATABASE_URL)


def init_database():
    with db() as conn:
        with conn.cursor() as cur:

            # ---------------------------------------------
            # PLAYERS
            # ---------------------------------------------

            cur.execute("""
                CREATE TABLE IF NOT EXISTS players (
                    id BIGSERIAL PRIMARY KEY,
                    telegram_id BIGINT UNIQUE NOT NULL,
                    username TEXT,
                    first_name TEXT,
                    country_id BIGINT,
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

            # ---------------------------------------------
            # COUNTRIES
            # ---------------------------------------------

            cur.execute("""
                CREATE TABLE IF NOT EXISTS countries (
                    id BIGSERIAL PRIMARY KEY,
                    name TEXT UNIQUE NOT NULL,
                    flag TEXT DEFAULT '🌍',
                    description TEXT DEFAULT '',
                    active BOOLEAN DEFAULT TRUE,

                    ruler_telegram_id BIGINT UNIQUE,

                    treasury BIGINT DEFAULT 0,
                    daily_income BIGINT DEFAULT 0,

                    public_satisfaction INTEGER DEFAULT 100,
                    stability INTEGER DEFAULT 100,

                    military_power INTEGER DEFAULT 0,
                    missile_stock INTEGER DEFAULT 0,

                    technology_level INTEGER DEFAULT 1,
                    industrial_technology INTEGER DEFAULT 1,
                    military_technology INTEGER DEFAULT 1,
                    agricultural_technology INTEGER DEFAULT 1,
                    energy_technology INTEGER DEFAULT 1,
                    medical_technology INTEGER DEFAULT 1,
                    transport_technology INTEGER DEFAULT 1,

                    infrastructure_condition INTEGER DEFAULT 100,

                    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # ---------------------------------------------
            # COUNTRY SETTINGS
            # ---------------------------------------------

            cur.execute("""
                CREATE TABLE IF NOT EXISTS country_settings (
                    country_id BIGINT PRIMARY KEY,

                    infrastructure_decay_enabled BOOLEAN DEFAULT TRUE,

                    last_daily_income_date DATE,
                    last_decay_date DATE,

                    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # ---------------------------------------------
            # OWNER
            # ---------------------------------------------

            cur.execute("""
                CREATE TABLE IF NOT EXISTS owner (
                    id INTEGER PRIMARY KEY CHECK (id = 1),

                    telegram_id BIGINT UNIQUE NOT NULL,

                    username TEXT,
                    first_name TEXT,

                    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # ---------------------------------------------
            # OFFICIAL LINKS
            # ---------------------------------------------

            cur.execute("""
                CREATE TABLE IF NOT EXISTS official_links (
                    key TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    url TEXT DEFAULT ''
                )
            """)

            # ---------------------------------------------
            # QUIZ QUESTIONS
            # ---------------------------------------------

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

            # ---------------------------------------------
            # QUIZ ATTEMPTS
            # ---------------------------------------------

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

            # ---------------------------------------------
            # INFRASTRUCTURE
            # ---------------------------------------------

            cur.execute("""
                CREATE TABLE IF NOT EXISTS infrastructures (
                    id BIGSERIAL PRIMARY KEY,

                    country_id BIGINT NOT NULL,

                    name TEXT NOT NULL,
                    type TEXT NOT NULL,

                    level INTEGER DEFAULT 1,

                    condition INTEGER DEFAULT 100,

                    active BOOLEAN DEFAULT TRUE,

                    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # ---------------------------------------------
            # REBUILD PROJECTS
            # ---------------------------------------------

            cur.execute("""
                CREATE TABLE IF NOT EXISTS rebuild_projects (
                    id BIGSERIAL PRIMARY KEY,

                    country_id BIGINT NOT NULL,
                    infrastructure_id BIGINT,

                    name TEXT NOT NULL,

                    cost BIGINT DEFAULT 0,

                    duration_seconds BIGINT DEFAULT 0,

                    started_at TIMESTAMPTZ,
                    finishes_at TIMESTAMPTZ,

                    status TEXT DEFAULT 'pending',

                    approved_by BIGINT,

                    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # ---------------------------------------------
            # OFFICIAL DEFAULT LINKS
            # ---------------------------------------------

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


# =========================================================
# BASIC PLAYER REGISTRATION
# =========================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    user = update.effective_user

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

    await update.message.reply_text(
        "🌍 به Nexora خوش آمدید!\n\n"
        "✅ هسته بازی فعال است.\n"
        "👤 حساب شما در سیستم ثبت شد.\n\n"
        "مرحله ۱ با موفقیت اجرا شده است."
    )


# =========================================================
# APPLICATION
# =========================================================

def main():

    print("Initializing Nexora database...")

    init_database()

    print("Database initialized successfully.")

    # Start Flask server for Render
    web_thread = Thread(
        target=run_web,
        daemon=True,
    )

    web_thread.start()

    print("Web server started.")

    # Telegram bot
    application = (
        Application
        .builder()
        .token(BOT_TOKEN)
        .build()
    )

    application.add_handler(
        CommandHandler(
            "start",
            start,
        )
    )

    print("Nexora bot started.")

    application.run_polling(
        drop_pending_updates=True
    )


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":
    main()
