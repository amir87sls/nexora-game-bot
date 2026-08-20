
import os
import json
import logging
from threading import Thread
from contextlib import contextmanager
from datetime import datetime, timezone

import psycopg
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters,
)

# ============================================================
# NEXORA — FINAL V1
# Telegram-only transport. Game data lives in PostgreSQL.
# All major features can be enabled/disabled by the owner.
# Owner can edit system texts and manage game data.
# ============================================================

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("nexora")

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
PORT = int(os.getenv("PORT", "10000"))

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not configured")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not configured")

web = Flask(__name__)

@web.get("/")
def home():
    return "Nexora is running"

@web.get("/healthz")
def healthz():
    return "OK"

def run_web():
    web.run(host="0.0.0.0", port=PORT, use_reloader=False)

@contextmanager
def db():
    conn = psycopg.connect(DATABASE_URL)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

FEATURES = {
    "countries": True,
    "players": True,
    "economy": True,
    "assets": True,
    "equipment": True,
    "forces": True,
    "wars": True,
    "deployments": True,
    "reconstruction": True,
    "infrastructure": True,
    "statements": True,
    "laws": True,
    "inventions": True,
    "scenarios": True,
    "sanctions": True,
    "un": True,
    "world_bank": True,
    "wto": True,
    "who": True,
    "iaea": True,
    "news": True,
    "notifications": True,
}

FEATURE_NAMES = {
    "countries": "کشورها", "players": "بازیکنان", "economy": "اقتصاد",
    "assets": "دارایی‌ها", "equipment": "تجهیزات", "forces": "نیروها",
    "wars": "جنگ‌ها", "deployments": "استقرارها",
    "reconstruction": "بازسازی‌ها", "infrastructure": "زیرساخت",
    "statements": "بیانیه‌ها", "laws": "قوانین",
    "inventions": "اختراعات و فناوری", "scenarios": "سناریوها",
    "sanctions": "تحریم‌ها", "un": "سازمان ملل",
    "world_bank": "بانک جهانی", "wto": "سازمان تجارت جهانی",
    "who": "سازمان بهداشت جهانی", "iaea": "سازمان بین‌المللی انرژی اتمی",
    "news": "اخبار", "notifications": "اعلان‌ها",
}

TEXTS = {
    "welcome": "🌍 به Nexora خوش آمدید!",
    "owner_panel": "👑 پنل مالک Nexora\n\nیک بخش را انتخاب کنید:",
    "player_panel": "🌍 منوی اصلی Nexora\n\nیک بخش را انتخاب کنید:",
    "denied": "⛔ دسترسی غیرمجاز.",
    "off": "🔕 این قابلیت فعلاً توسط مالک غیرفعال شده است.",
    "back": "🔙 بازگشت",
    "no_country": "⚠️ هنوز کشوری برای شما تعیین نشده است.",
    "news_title": "📰 اخبار Nexora",
    "saved": "✅ ذخیره شد.",
    "cancelled": "❌ لغو شد.",
}

ORGS = {
    "un": "🌐 سازمان ملل متحد",
    "world_bank": "🏦 بانک جهانی",
    "wto": "🌎 سازمان تجارت جهانی",
    "who": "🏥 سازمان بهداشت جهانی",
    "iaea": "☢️ سازمان بین‌المللی انرژی اتمی",
}

# ---------------- DATABASE ----------------

SCHEMA = [
"""
CREATE TABLE IF NOT EXISTS owner (
    id INTEGER PRIMARY KEY CHECK (id=1),
    telegram_id BIGINT UNIQUE NOT NULL,
    username TEXT, first_name TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
)
""",
"""
CREATE TABLE IF NOT EXISTS players (
    id BIGSERIAL PRIMARY KEY,
    telegram_id BIGINT UNIQUE NOT NULL,
    username TEXT, first_name TEXT,
    role TEXT NOT NULL DEFAULT 'player',
    country_id BIGINT,
    government_type TEXT,
    money BIGINT NOT NULL DEFAULT 0,
    bank_money BIGINT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
)
""",
"""
CREATE TABLE IF NOT EXISTS countries (
    id BIGSERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    flag TEXT NOT NULL DEFAULT '🌍',
    description TEXT NOT NULL DEFAULT '',
    government_type TEXT NOT NULL DEFAULT '',
    ruler_telegram_id BIGINT UNIQUE,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    treasury BIGINT NOT NULL DEFAULT 0,
    daily_income BIGINT NOT NULL DEFAULT 0,
    population BIGINT NOT NULL DEFAULT 0,
    stability INTEGER NOT NULL DEFAULT 100,
    satisfaction INTEGER NOT NULL DEFAULT 100,
    infrastructure INTEGER NOT NULL DEFAULT 100,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
)
""",
"""
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
)
""",
"""
CREATE TABLE IF NOT EXISTS official_links (
    id BIGSERIAL PRIMARY KEY,
    key TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    url TEXT NOT NULL DEFAULT '',
    active BOOLEAN NOT NULL DEFAULT TRUE
)
""",
"""
CREATE TABLE IF NOT EXISTS wars (
    id BIGSERIAL PRIMARY KEY,
    attacker_country BIGINT NOT NULL,
    defender_country BIGINT NOT NULL,
    title TEXT NOT NULL DEFAULT 'جنگ',
    reason TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'فعال',
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at TIMESTAMPTZ
)
""",
"""
CREATE TABLE IF NOT EXISTS forces (
    id BIGSERIAL PRIMARY KEY,
    country_id BIGINT NOT NULL,
    force_type TEXT NOT NULL,
    amount BIGINT NOT NULL DEFAULT 0,
    location TEXT NOT NULL DEFAULT 'پایتخت',
    status TEXT NOT NULL DEFAULT 'مستقر'
)
""",
"""
CREATE TABLE IF NOT EXISTS assets (
    id BIGSERIAL PRIMARY KEY,
    country_id BIGINT NOT NULL,
    asset_type TEXT NOT NULL,
    amount BIGINT NOT NULL DEFAULT 0
)
""",
"""
CREATE TABLE IF NOT EXISTS deployments (
    id BIGSERIAL PRIMARY KEY,
    country_id BIGINT NOT NULL,
    force_type TEXT NOT NULL,
    amount BIGINT NOT NULL DEFAULT 0,
    location TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'در حال استقرار'
)
""",
"""
CREATE TABLE IF NOT EXISTS reconstruction (
    id BIGSERIAL PRIMARY KEY,
    country_id BIGINT NOT NULL,
    project TEXT NOT NULL,
    progress INTEGER NOT NULL DEFAULT 0,
    cost BIGINT NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'در حال اجرا'
)
""",
"""
CREATE TABLE IF NOT EXISTS infrastructure_repairs (
    id BIGSERIAL PRIMARY KEY,
    country_id BIGINT NOT NULL,
    project TEXT NOT NULL,
    progress INTEGER NOT NULL DEFAULT 0,
    cost BIGINT NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'در حال اجرا'
)
""",
"""
CREATE TABLE IF NOT EXISTS statements (
    id BIGSERIAL PRIMARY KEY,
    country_id BIGINT,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
)
""",
"""
CREATE TABLE IF NOT EXISTS laws (
    id BIGSERIAL PRIMARY KEY,
    country_id BIGINT,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE
)
""",
"""
CREATE TABLE IF NOT EXISTS inventions (
    id BIGSERIAL PRIMARY KEY,
    country_id BIGINT,
    title TEXT NOT NULL,
    body TEXT NOT NULL DEFAULT '',
    level INTEGER NOT NULL DEFAULT 1
)
""",
"""
CREATE TABLE IF NOT EXISTS scenarios (
    id BIGSERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    active BOOLEAN NOT NULL DEFAULT FALSE
)
""",
"""
CREATE TABLE IF NOT EXISTS sanctions (
    id BIGSERIAL PRIMARY KEY,
    issuer_country BIGINT,
    target_country BIGINT,
    reason TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'فعال',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
)
""",
"""
CREATE TABLE IF NOT EXISTS organization_actions (
    id BIGSERIAL PRIMARY KEY,
    organization TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'فعال',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
)
""",
"""
CREATE TABLE IF NOT EXISTS news (
    id BIGSERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    published BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
)
""",
"""
CREATE TABLE IF NOT EXISTS sessions (
    telegram_id BIGINT PRIMARY KEY,
    state TEXT NOT NULL,
    payload TEXT NOT NULL DEFAULT '{}'
)
""",
]

def init_db():
    with db() as conn:
        with conn.cursor() as cur:
            for sql in SCHEMA:
                cur.execute(sql)
            for key, val in FEATURES.items():
                cur.execute(
                    "INSERT INTO settings(key,value) VALUES(%s,%s) "
                    "ON CONFLICT(key) DO NOTHING",
                    (f"feature:{key}", json.dumps(val)),
                )
            for key, val in TEXTS.items():
                cur.execute(
                    "INSERT INTO settings(key,value) VALUES(%s,%s) "
                    "ON CONFLICT(key) DO NOTHING",
                    (f"text:{key}", json.dumps(val, ensure_ascii=False)),
                )
            defaults = [
                ("news", "📰 کانال اخبار", ""),
                ("rules", "📚 قوانین", ""),
                ("chat", "💬 گپ بازیکنان", ""),
            ]
            for key, title, url in defaults:
                cur.execute(
                    "INSERT INTO official_links(key,title,url) VALUES(%s,%s,%s) "
                    "ON CONFLICT(key) DO NOTHING", (key,title,url)
                )

def get_setting(key, default=None):
    with db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT value FROM settings WHERE key=%s", (key,))
            row = cur.fetchone()
    if not row:
        return default
    try:
        return json.loads(row[0])
    except Exception:
        return default

def set_setting(key, value):
    with db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO settings(key,value) VALUES(%s,%s) "
                "ON CONFLICT(key) DO UPDATE SET value=EXCLUDED.value",
                (key, json.dumps(value, ensure_ascii=False)),
            )

def feature_on(key):
    return bool(get_setting(f"feature:{key}", FEATURES.get(key, False)))

def txt(key):
    return str(get_setting(f"text:{key}", TEXTS.get(key, "")))

def owner_id():
    with db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT telegram_id FROM owner WHERE id=1")
            row = cur.fetchone()
    return row[0] if row else None

def is_owner(uid):
    return owner_id() == uid

def ensure_player(user):
    with db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO players(telegram_id,username,first_name,role)
                VALUES(%s,%s,%s,%s)
                ON CONFLICT(telegram_id) DO UPDATE SET
                  username=EXCLUDED.username,
                  first_name=EXCLUDED.first_name
                """,
                (user.id,user.username,user.first_name,
                 "owner" if is_owner(user.id) else "player"),
            )

def get_player(uid):
    with db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT id,telegram_id,username,first_name,role,
                          country_id,government_type,money,bank_money
                   FROM players WHERE telegram_id=%s""", (uid,)
            )
            return cur.fetchone()

def get_country(cid):
    if not cid:
        return None
    with db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT id,name,flag,description,government_type,
                          ruler_telegram_id,active,treasury,daily_income,
                          population,stability,satisfaction,infrastructure
                   FROM countries WHERE id=%s""", (cid,)
            )
            return cur.fetchone()

def user_country(uid):
    p = get_player(uid)
    return get_country(p[5]) if p and p[5] else None

def all_active_countries():
    with db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id,flag,name FROM countries WHERE active=TRUE ORDER BY name"
            )
            return cur.fetchall()

# ---------------- UI ----------------

def markup(rows):
    return InlineKeyboardMarkup(rows)

def back(target):
    return [InlineKeyboardButton(txt("back"), callback_data=target)]

async def render(update, text_value, rows=None):
    m = markup(rows or [])
    if update.callback_query:
        await update.callback_query.edit_message_text(text_value, reply_markup=m)
    else:
        await update.message.reply_text(text_value, reply_markup=m)

async def fail(update, message):
    if update.callback_query:
        await update.callback_query.answer(message, show_alert=True)
    else:
        await update.message.reply_text(message)

async def guard_owner(update):
    if is_owner(update.effective_user.id):
        return True
    await fail(update, txt("denied"))
    return False

async def guard_feature(update, key):
    if feature_on(key):
        return True
    await fail(update, txt("off"))
    return False

# ---------------- SESSION ----------------

def clear_flow(context):
    context.user_data.pop("flow", None)
    context.user_data.pop("step", None)
    context.user_data.pop("data", None)

def set_flow(context, name, step, data=None):
    context.user_data["flow"] = name
    context.user_data["step"] = step
    context.user_data["data"] = data or {}

# ---------------- START ----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    ensure_player(user)
    if owner_id() is None:
        await render(
            update,
            f"{txt('welcome')}\n\nمالک بازی هنوز تعیین نشده است.",
            [[InlineKeyboardButton("👑 تعیین من به‌عنوان مالک", callback_data="claim")]],
        )
        return
    if is_owner(user.id):
        await owner_panel(update, context)
    else:
        await player_panel(update, context)

async def claim(update, context):
    q = update.callback_query
    uid = q.from_user.id
    with db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT telegram_id FROM owner WHERE id=1")
            if cur.fetchone():
                await q.answer("مالک قبلاً تعیین شده است.", show_alert=True)
                return
            cur.execute(
                "INSERT INTO owner(id,telegram_id,username,first_name) VALUES(1,%s,%s,%s)",
                (uid,q.from_user.username,q.from_user.first_name),
            )
            cur.execute(
                "UPDATE players SET role='owner' WHERE telegram_id=%s", (uid,)
            )
    await q.answer()
    await render(update, "👑 شما مالک Nexora شدید.", [[
        InlineKeyboardButton("⚙️ پنل مالک", callback_data="owner:home")
    ]])

# ---------------- PLAYER ----------------

async def player_panel(update, context):
    if not await guard_feature(update, "players"):
        return
    rows = []
    if feature_on("countries"):
        rows.append([InlineKeyboardButton("🌍 کشورها", callback_data="p:countries")])
    rows.append([InlineKeyboardButton("👤 پروفایل", callback_data="p:profile")])
    for key, label, cb in [
        ("economy","💰 اقتصاد","p:economy"),
        ("assets","💼 دارایی‌ها","p:assets"),
        ("equipment","🔫 تجهیزات","p:equipment"),
        ("forces","🪖 نیروها","p:forces"),
        ("wars","⚔️ جنگ‌ها","p:wars"),
        ("deployments","📍 استقرار","p:deployments"),
        ("reconstruction","🏗️ بازسازی","p:reconstruction"),
        ("infrastructure","🔧 زیرساخت","p:infrastructure"),
        ("statements","📢 بیانیه‌ها","p:statements"),
        ("laws","📜 قوانین","p:laws"),
        ("inventions","💡 اختراعات","p:inventions"),
        ("scenarios","🎬 سناریوها","p:scenarios"),
        ("sanctions","🚫 تحریم‌ها","p:sanctions"),
        ("news","📰 اخبار","p:news"),
    ]:
        if feature_on(key):
            rows.append([InlineKeyboardButton(label, callback_data=cb)])
    if any(feature_on(x) for x in ORGS):
        rows.append([InlineKeyboardButton("🌐 سازمان‌ها", callback_data="p:orgs")])
    rows.append([InlineKeyboardButton("🔗 لینک‌های رسمی", callback_data="p:links")])
    await render(update, txt("player_panel"), rows)

async def player_profile(update, context):
    p = get_player(update.effective_user.id)
    c = get_country(p[5]) if p and p[5] else None
    country = f"{c[2]} {c[1]}" if c else "بدون کشور"
    body = (
        "👤 پروفایل\n\n"
        f"نام: {p[3] if p else '-'}\n"
        f"نام کاربری: @{p[2] if p and p[2] else '-'}\n"
        f"کشور: {country}\n"
        f"💰 پول: {p[7] if p else 0}\n"
        f"🏦 بانک: {p[8] if p else 0}"
    )
    await render(update, body, [back("p:home")])

async def player_countries(update, context):
    if not await guard_feature(update, "countries"):
        return
    rows = [[InlineKeyboardButton(f"{r[1]} {r[2]}", callback_data=f"cv:{r[0]}")]
            for r in all_active_countries()]
    rows.append(back("p:home"))
    await render(update, "🌍 کشورهای فعال:", rows)

async def country_view(update, context, cid):
    c = get_country(cid)
    if not c:
        await fail(update, "کشور پیدا نشد.")
        return
    body = (
        f"{c[2]} {c[1]}\n\n"
        f"🏛️ حکومت: {c[4] or '-'}\n"
        f"👥 جمعیت: {c[9]}\n"
        f"💰 خزانه: {c[7]}\n"
        f"📈 درآمد روزانه: {c[8]}\n"
        f"🛡️ ثبات: {c[10]}\n"
        f"😊 رضایت: {c[11]}\n"
        f"🏗️ زیرساخت: {c[12]}\n\n"
        f"{c[3] or ''}"
    )
    await render(update, body, [back("p:countries")])

async def player_data_page(update, title, feature, table, where=""):
    if not await guard_feature(update, feature):
        return
    c = user_country(update.effective_user.id)
    if not c:
        await render(update, f"{title}\n\n{txt('no_country')}", [back("p:home")])
        return
    with db() as conn:
        with conn.cursor() as cur:
            if table == "forces":
                cur.execute(
                    "SELECT force_type,amount,location,status FROM forces WHERE country_id=%s ORDER BY id DESC LIMIT 20",
                    (c[0],),
                )
                rows = cur.fetchall()
                lines = [title]
                for r in rows:
                    lines.append(f"\n🪖 {r[0]} | {r[1]} | {r[2]} | {r[3]}")
            elif table == "assets":
                cur.execute(
                    "SELECT asset_type,amount FROM assets WHERE country_id=%s ORDER BY id DESC LIMIT 20",
                    (c[0],),
                )
                rows = cur.fetchall()
                lines = [title]
                for r in rows:
                    lines.append(f"\n💼 {r[0]}: {r[1]}")
            elif table == "deployments":
                cur.execute(
                    "SELECT force_type,amount,location,status FROM deployments WHERE country_id=%s ORDER BY id DESC LIMIT 20",
                    (c[0],),
                )
                rows = cur.fetchall()
                lines = [title]
                for r in rows:
                    lines.append(f"\n📍 {r[0]} | {r[1]} | {r[2]} | {r[3]}")
            elif table == "reconstruction":
                cur.execute(
                    "SELECT project,progress,cost,status FROM reconstruction WHERE country_id=%s ORDER BY id DESC LIMIT 20",
                    (c[0],),
                )
                rows = cur.fetchall()
                lines = [title]
                for r in rows:
                    lines.append(f"\n🏗️ {r[0]} | {r[1]}% | هزینه {r[2]} | {r[3]}")
            elif table == "infrastructure_repairs":
                cur.execute(
                    "SELECT project,progress,cost,status FROM infrastructure_repairs WHERE country_id=%s ORDER BY id DESC LIMIT 20",
                    (c[0],),
                )
                rows = cur.fetchall()
                lines = [title]
                for r in rows:
                    lines.append(f"\n🔧 {r[0]} | {r[1]}% | هزینه {r[2]} | {r[3]}")
            elif table == "wars":
                cur.execute(
                    """SELECT a.name,b.name,w.title,w.status,w.reason
                       FROM wars w JOIN countries a ON a.id=w.attacker_country
                       JOIN countries b ON b.id=w.defender_country
                       WHERE w.attacker_country=%s OR w.defender_country=%s
                       ORDER BY w.id DESC LIMIT 20""",
                    (c[0],c[0]),
                )
                rows = cur.fetchall()
                lines = [title]
                for r in rows:
                    lines.append(f"\n⚔️ {r[0]} ↔ {r[1]}\n{r[2]} | {r[3]}\n{r[4]}")
            elif table == "statements":
                cur.execute(
                    "SELECT title,body FROM statements WHERE country_id=%s OR country_id IS NULL ORDER BY id DESC LIMIT 15",
                    (c[0],),
                )
                rows = cur.fetchall()
                lines = [title]
                for r in rows:
                    lines.append(f"\n📢 {r[0]}\n{r[1]}")
            elif table == "laws":
                cur.execute(
                    "SELECT title,body,active FROM laws WHERE country_id=%s OR country_id IS NULL ORDER BY id DESC LIMIT 15",
                    (c[0],),
                )
                rows = cur.fetchall()
                lines = [title]
                for r in rows:
                    lines.append(f"\n📜 {r[0]} | {'فعال' if r[2] else 'غیرفعال'}\n{r[1]}")
            elif table == "inventions":
                cur.execute(
                    "SELECT title,body,level FROM inventions WHERE country_id=%s OR country_id IS NULL ORDER BY id DESC LIMIT 15",
                    (c[0],),
                )
                rows = cur.fetchall()
                lines = [title]
                for r in rows:
                    lines.append(f"\n💡 {r[0]} | سطح {r[2]}\n{r[1]}")
            elif table == "scenarios":
                cur.execute(
                    "SELECT title,description,active FROM scenarios ORDER BY id DESC LIMIT 15"
                )
                rows = cur.fetchall()
                lines = [title]
                for r in rows:
                    lines.append(f"\n🎬 {r[0]} | {'فعال' if r[2] else 'غیرفعال'}\n{r[1]}")
            elif table == "sanctions":
                cur.execute(
                    """SELECT a.name,b.name,s.reason,s.status
                       FROM sanctions s
                       LEFT JOIN countries a ON a.id=s.issuer_country
                       LEFT JOIN countries b ON b.id=s.target_country
                       WHERE s.issuer_country=%s OR s.target_country=%s
                       ORDER BY s.id DESC LIMIT 20""",
                    (c[0],c[0]),
                )
                rows = cur.fetchall()
                lines = [title]
                for r in rows:
                    lines.append(f"\n🚫 {r[0] or '-'} → {r[1] or '-'} | {r[3]}\n{r[2]}")
            else:
                rows = []
                lines = [title]
    if len(lines) == 1:
        lines.append("\nهنوز داده‌ای ثبت نشده است.")
    await render(update, "\n".join(lines), [back("p:home")])

async def player_economy(update, context):
    if not await guard_feature(update, "economy"): return
    c = user_country(update.effective_user.id)
    if not c:
        await render(update, f"💰 اقتصاد\n\n{txt('no_country')}", [back("p:home")])
        return
    p = get_player(update.effective_user.id)
    body = (
        f"💰 اقتصاد {c[2]} {c[1]}\n\n"
        f"خزانه کشور: {c[7]}\n"
        f"درآمد روزانه: {c[8]}\n"
        f"پول شخصی: {p[7]}\n"
        f"بانک: {p[8]}\n"
        f"ثبات: {c[10]}\nرضایت: {c[11]}"
    )
    await render(update, body, [back("p:home")])

async def player_orgs(update, context):
    rows = [[InlineKeyboardButton(name, callback_data=f"org:{key}")]
            for key,name in ORGS.items() if feature_on(key)]
    rows.append(back("p:home"))
    await render(update, "🌐 سازمان‌های فعال:", rows)

async def player_org(update, context, key):
    if key not in ORGS or not await guard_feature(update, key): return
    with db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT title,body,status FROM organization_actions WHERE organization=%s ORDER BY id DESC LIMIT 20",
                (key,),
            )
            rows = cur.fetchall()
    lines = [ORGS[key]]
    if not rows:
        lines.append("\nهنوز اقدامی ثبت نشده است.")
    for r in rows:
        lines.append(f"\n• {r[0]}\n{r[1]}\nوضعیت: {r[2]}")
    await render(update, "\n".join(lines), [back("p:orgs")])

async def player_news(update, context):
    if not await guard_feature(update, "news"): return
    with db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT title,body FROM news WHERE published=TRUE ORDER BY id DESC LIMIT 30"
            )
            rows = cur.fetchall()
    lines = [txt("news_title")]
    if not rows: lines.append("\nهنوز خبری منتشر نشده است.")
    for r in rows: lines.append(f"\n📰 {r[0]}\n{r[1]}")
    await render(update, "\n".join(lines), [back("p:home")])

async def player_links(update, context):
    with db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT title,url FROM official_links WHERE active=TRUE ORDER BY id")
            rows = cur.fetchall()
    buttons = []
    for title,url in rows:
        if url.startswith(("http://","https://")):
            buttons.append([InlineKeyboardButton(title,url=url)])
        else:
            buttons.append([InlineKeyboardButton(title,callback_data="noop")])
    buttons.append(back("p:home"))
    await render(update, "🔗 لینک‌های رسمی Nexora", buttons)

# ---------------- OWNER ----------------

async def owner_panel(update, context):
    if not await guard_owner(update): return
    rows = [
        [InlineKeyboardButton("🌍 کشورها",callback_data="o:countries"),
         InlineKeyboardButton("👥 بازیکنان",callback_data="o:players")],
        [InlineKeyboardButton("⚔️ جنگ‌ها",callback_data="o:wars"),
         InlineKeyboardButton("🪖 نیرو/تجهیزات",callback_data="o:forces")],
        [InlineKeyboardButton("💰 دارایی/اقتصاد",callback_data="o:economy"),
         InlineKeyboardButton("🏗️ بازسازی/زیرساخت",callback_data="o:build")],
        [InlineKeyboardButton("📢 بیانیه/قوانین",callback_data="o:content"),
         InlineKeyboardButton("💡 فناوری/سناریو",callback_data="o:tech")],
        [InlineKeyboardButton("🚫 تحریم‌ها",callback_data="o:sanctions"),
         InlineKeyboardButton("🌐 سازمان‌ها",callback_data="o:orgs")],
        [InlineKeyboardButton("📰 اخبار",callback_data="o:news"),
         InlineKeyboardButton("🔗 لینک‌ها",callback_data="o:links")],
        [InlineKeyboardButton("⚙️ کنترل قابلیت‌ها",callback_data="o:settings")],
        [InlineKeyboardButton("✏️ متن‌های سیستم",callback_data="o:texts")],
    ]
    await render(update, txt("owner_panel"), rows)

async def owner_settings(update, context):
    if not await guard_owner(update): return
    rows = []
    for key,name in FEATURE_NAMES.items():
        rows.append([InlineKeyboardButton(
            f"{'🟢' if feature_on(key) else '🔴'} {name}",
            callback_data=f"toggle:{key}"
        )])
    rows.append(back("o:home"))
    await render(update, "⚙️ کنترل تمام قابلیت‌ها\n\n🟢 فعال | 🔴 غیرفعال", rows)

async def owner_texts(update, context):
    if not await guard_owner(update): return
    rows = [[InlineKeyboardButton(f"✏️ {k}",callback_data=f"edittext:{k}")]
            for k in TEXTS]
    rows.append(back("o:home"))
    await render(update, "✏️ متن‌های قابل تغییر مالک:", rows)

async def owner_countries(update, context):
    if not await guard_owner(update): return
    rows = [
        [InlineKeyboardButton("➕ ساخت کشور",callback_data="country:add")],
        [InlineKeyboardButton("📋 فهرست",callback_data="country:list")],
        [InlineKeyboardButton("👑 تعیین حاکم",callback_data="country:ruler")],
        [InlineKeyboardButton("🔄 فعال/غیرفعال",callback_data="country:toggle")],
        back("o:home"),
    ]
    await render(update, "🌍 مدیریت کشورها", rows)

async def owner_players(update, context):
    if not await guard_owner(update): return
    with db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT telegram_id,first_name,username,role,country_id,money
                   FROM players ORDER BY id DESC LIMIT 100"""
            )
            rows = cur.fetchall()
    lines = ["👥 بازیکنان"]
    if not rows: lines.append("\nهنوز بازیکنی ثبت نشده است.")
    for r in rows:
        lines.append(
            f"\n• {r[1] or '-'} | @{r[2] or '-'}\n"
            f"ID: {r[0]} | نقش: {r[3]} | کشور: {r[4] or '-'} | 💰 {r[5]}"
        )
    buttons = [
        [InlineKeyboardButton("👑 تعیین کشور بازیکن",callback_data="player:setcountry")],
        back("o:home"),
    ]
    await render(update, "\n".join(lines), buttons)

async def owner_toggle_section(update, title, keys):
    if not await guard_owner(update): return
    rows = [[InlineKeyboardButton(
        f"{'🟢' if feature_on(k) else '🔴'} {FEATURE_NAMES[k]}",
        callback_data=f"toggle:{k}"
    )] for k in keys]
    rows.append(back("o:home"))
    await render(update, title, rows)

# ---------------- OWNER DATA MANAGEMENT ----------------

async def owner_list_table(update, title, table):
    if not await guard_owner(update): return
    queries = {
        "wars": """SELECT id,attacker_country,defender_country,title,status FROM wars ORDER BY id DESC LIMIT 50""",
        "forces": """SELECT id,country_id,force_type,amount,location,status FROM forces ORDER BY id DESC LIMIT 50""",
        "assets": """SELECT id,country_id,asset_type,amount FROM assets ORDER BY id DESC LIMIT 50""",
        "reconstruction": """SELECT id,country_id,project,progress,cost,status FROM reconstruction ORDER BY id DESC LIMIT 50""",
        "infrastructure_repairs": """SELECT id,country_id,project,progress,cost,status FROM infrastructure_repairs ORDER BY id DESC LIMIT 50""",
        "statements": """SELECT id,title,body FROM statements ORDER BY id DESC LIMIT 50""",
        "laws": """SELECT id,title,active FROM laws ORDER BY id DESC LIMIT 50""",
        "inventions": """SELECT id,title,level FROM inventions ORDER BY id DESC LIMIT 50""",
        "scenarios": """SELECT id,title,active FROM scenarios ORDER BY id DESC LIMIT 50""",
        "sanctions": """SELECT id,issuer_country,target_country,status,reason FROM sanctions ORDER BY id DESC LIMIT 50""",
        "news": """SELECT id,title,published FROM news ORDER BY id DESC LIMIT 50""",
        "organization_actions": """SELECT id,organization,title,status FROM organization_actions ORDER BY id DESC LIMIT 50""",
    }
    with db() as conn:
        with conn.cursor() as cur:
            cur.execute(queries[table])
            rows = cur.fetchall()
    lines = [title]
    for r in rows:
        lines.append(" | ".join(str(x) for x in r))
    if len(lines) == 1: lines.append("\nهیچ داده‌ای وجود ندارد.")
    await render(update,"\n".join(lines),[back("o:home")])

async def owner_create_prompt(update, flow, prompt, step="1"):
    if not await guard_owner(update): return
    set_flow(update._effective_user if False else update, "", "")  # never executed; kept out of runtime
    # Actual flow is stored by caller.

# ---------------- COUNTRY FLOWS ----------------

async def country_add_start(update, context):
    if not await guard_owner(update): return
    set_flow(context,"country_add","name")
    await update.callback_query.answer()
    await update.callback_query.message.reply_text("➕ نام کشور را بفرستید:")

async def country_ruler_start(update, context):
    if not await guard_owner(update): return
    set_flow(context,"ruler","player_id")
    await update.callback_query.answer()
    await update.callback_query.message.reply_text(
        "👑 ابتدا Telegram ID بازیکن را بفرستید:"
    )

async def player_setcountry_start(update, context):
    if not await guard_owner(update): return
    set_flow(context,"setcountry","player_id")
    await update.callback_query.answer()
    await update.callback_query.message.reply_text("👤 Telegram ID بازیکن را بفرستید:")

async def country_list(update, context):
    if not await guard_owner(update): return
    with db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id,flag,name,active,ruler_telegram_id,treasury FROM countries ORDER BY id"
            )
            rows=cur.fetchall()
    lines=["🌍 کشورها"]
    for r in rows:
        lines.append(f"\n{r[0]}. {r[1]} {r[2]} | {'🟢' if r[3] else '🔴'} | حاکم {r[4] or '-'} | 💰 {r[5]}")
    await render(update,"\n".join(lines),[back("o:countries")])

async def country_toggle_start(update, context):
    if not await guard_owner(update): return
    with db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id,flag,name,active FROM countries ORDER BY id")
            rows=cur.fetchall()
    buttons=[[InlineKeyboardButton(
        f"{'🟢' if r[3] else '🔴'} {r[1]} {r[2]}",
        callback_data=f"ctoggle:{r[0]}"
    )] for r in rows]
    buttons.append(back("o:countries"))
    await render(update,"🔄 وضعیت کشور:",buttons)

# ---------------- TEXT FLOWS ----------------

async def handle_text(update, context):
    uid=update.effective_user.id
    if not is_owner(uid):
        return
    flow=context.user_data.get("flow")
    step=context.user_data.get("step")
    val=update.message.text.strip()
    data=context.user_data.get("data",{})

    if flow=="edittext":
        key=data.get("key")
        if key:
            set_setting(f"text:{key}",val)
            clear_flow(context)
            await update.message.reply_text(txt("saved"))
            await owner_texts(update,context)
        return

    if flow=="country_add":
        if step=="name":
            data["name"]=val; context.user_data["step"]="flag"
            await update.message.reply_text("🏳️ پرچم:")
        elif step=="flag":
            data["flag"]=val or "🌍"; context.user_data["step"]="government"
            await update.message.reply_text("🏛️ نوع حکومت:")
        elif step=="government":
            data["government"]=val; context.user_data["step"]="description"
            await update.message.reply_text("📝 توضیحات:")
        elif step=="description":
            with db() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO countries(name,flag,government_type,description) VALUES(%s,%s,%s,%s)",
                        (data["name"],data["flag"],data["government"],val)
                    )
            clear_flow(context)
            await update.message.reply_text("✅ کشور ساخته شد.")
            await owner_countries(update,context)
        return

    if flow=="ruler":
        if step=="player_id":
            try: pid=int(val)
            except ValueError:
                await update.message.reply_text("❌ Telegram ID عددی است."); return
            data["player_id"]=pid; context.user_data["step"]="country_id"
            await update.message.reply_text("🌍 ID کشور را بفرستید:")
        elif step=="country_id":
            try: cid=int(val)
            except ValueError:
                await update.message.reply_text("❌ ID کشور عددی است."); return
            with db() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT id FROM players WHERE telegram_id=%s",(data["player_id"],))
                    if not cur.fetchone():
                        await update.message.reply_text("❌ بازیکن پیدا نشد."); clear_flow(context); return
                    cur.execute("SELECT id FROM countries WHERE id=%s",(cid,))
                    if not cur.fetchone():
                        await update.message.reply_text("❌ کشور پیدا نشد."); clear_flow(context); return
                    cur.execute("UPDATE countries SET ruler_telegram_id=%s WHERE id=%s",(data["player_id"],cid))
                    cur.execute("UPDATE players SET country_id=%s WHERE telegram_id=%s",(cid,data["player_id"]))
            clear_flow(context)
            await update.message.reply_text("👑 حاکم تعیین شد.")
            await owner_countries(update,context)
        return

    if flow=="setcountry":
        if step=="player_id":
            try: pid=int(val)
            except ValueError:
                await update.message.reply_text("❌ Telegram ID عددی است."); return
            data["player_id"]=pid; context.user_data["step"]="country_id"
            await update.message.reply_text("🌍 ID کشور را بفرستید:")
        elif step=="country_id":
            try: cid=int(val)
            except ValueError:
                await update.message.reply_text("❌ ID کشور عددی است."); return
            with db() as conn:
                with conn.cursor() as cur:
                    cur.execute("UPDATE players SET country_id=%s WHERE telegram_id=%s",(cid,data["player_id"]))
                    if cur.rowcount==0:
                        await update.message.reply_text("❌ بازیکن پیدا نشد."); clear_flow(context); return
                    cur.execute("UPDATE countries SET ruler_telegram_id=%s WHERE id=%s",(data["player_id"],cid))
            clear_flow(context)
            await update.message.reply_text("✅ کشور بازیکن تعیین شد.")
            await owner_players(update,context)
        return

# ---------------- CALLBACK ROUTER ----------------

async def router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q=update.callback_query
    await q.answer()
    d=q.data or ""
    uid=q.from_user.id

    if d=="noop": return
    if d=="claim": await claim(update,context); return
    if d=="o:home": await owner_panel(update,context); return
    if d=="p:home": await player_panel(update,context); return

    if d.startswith("toggle:"):
        if not await guard_owner(update): return
        key=d.split(":",1)[1]
        if key not in FEATURES:
            await fail(update,"قابلیت نامعتبر است."); return
        set_setting(f"feature:{key}",not feature_on(key))
        await owner_settings(update,context); return

    if d.startswith("edittext:"):
        if not await guard_owner(update): return
        key=d.split(":",1)[1]
        if key not in TEXTS:
            await fail(update,"متن نامعتبر است."); return
        set_flow(context,"edittext","value",{"key":key})
        await q.message.reply_text(f"✏️ متن «{key}» را بفرستید:")
        return

    if d=="o:settings": await owner_settings(update,context); return
    if d=="o:texts": await owner_texts(update,context); return
    if d=="o:countries": await owner_countries(update,context); return
    if d=="o:players": await owner_players(update,context); return
    if d=="o:wars":
        await owner_toggle_section(update,"⚔️ جنگ‌ها",["wars"]); return
    if d=="o:forces":
        await owner_toggle_section(update,"🪖 نیرو و تجهیزات",["forces","equipment","deployments"]); return
    if d=="o:economy":
        await owner_toggle_section(update,"💰 اقتصاد و دارایی",["economy","assets"]); return
    if d=="o:build":
        await owner_toggle_section(update,"🏗️ ساخت و زیرساخت",["reconstruction","infrastructure"]); return
    if d=="o:content":
        await owner_toggle_section(update,"📢 محتوا",["statements","laws"]); return
    if d=="o:tech":
        await owner_toggle_section(update,"💡 فناوری و سناریو",["inventions","scenarios"]); return
    if d=="o:sanctions":
        await owner_toggle_section(update,"🚫 تحریم‌ها",["sanctions"]); return
    if d=="o:orgs":
        await owner_toggle_section(update,"🌐 سازمان‌ها",list(ORGS)); return
    if d=="o:news":
        await owner_toggle_section(update,"📰 اخبار",["news","notifications"]); return
    if d=="o:links":
        await render(update,"🔗 مدیریت لینک‌ها\n\nفعلاً لینک‌ها از دیتابیس خوانده می‌شوند.",[back("o:home")]); return

    if d=="country:add": await country_add_start(update,context); return
    if d=="country:list": await country_list(update,context); return
    if d=="country:toggle": await country_toggle_start(update,context); return
    if d=="country:ruler": await country_ruler_start(update,context); return
    if d=="player:setcountry": await player_setcountry_start(update,context); return

    if d.startswith("ctoggle:"):
        if not await guard_owner(update): return
        cid=int(d.split(":",1)[1])
        with db() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE countries SET active=NOT active WHERE id=%s",(cid,))
        await country_toggle_start(update,context); return

    # player pages
    if d=="p:countries": await player_countries(update,context); return
    if d.startswith("cv:"): await country_view(update,context,int(d.split(":")[1])); return
    if d=="p:profile": await player_profile(update,context); return
    page_map={
        "p:economy":("💰 اقتصاد","economy","economy"),
        "p:assets":("💼 دارایی‌ها","assets","assets"),
        "p:equipment":("🔫 تجهیزات","equipment","forces"),
        "p:forces":("🪖 نیروها","forces","forces"),
        "p:wars":("⚔️ جنگ‌ها","wars","wars"),
        "p:deployments":("📍 استقرار","deployments","deployments"),
        "p:reconstruction":("🏗️ بازسازی","reconstruction","reconstruction"),
        "p:infrastructure":("🔧 زیرساخت","infrastructure","infrastructure_repairs"),
        "p:statements":("📢 بیانیه‌ها","statements","statements"),
        "p:laws":("📜 قوانین","laws","laws"),
        "p:inventions":("💡 اختراعات","inventions","inventions"),
        "p:scenarios":("🎬 سناریوها","scenarios","scenarios"),
        "p:sanctions":("🚫 تحریم‌ها","sanctions","sanctions"),
    }
    if d in page_map:
        title,feature,table=page_map[d]
        await player_data_page(update,title,feature,table); return
    if d=="p:orgs": await player_orgs(update,context); return
    if d.startswith("org:"): await player_org(update,context,d.split(":",1)[1]); return
    if d=="p:news": await player_news(update,context); return
    if d=="p:links": await player_links(update,context); return

    await fail(update,"⚠️ گزینه نامعتبر است.")

# ---------------- ERROR / MAIN ----------------

async def error_handler(update, context):
    log.exception("Unhandled Telegram error", exc_info=context.error)

def main():
    init_db()
    Thread(target=run_web,daemon=True).start()
    application=Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start",start))
    application.add_handler(CallbackQueryHandler(router))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,handle_text))
    application.add_error_handler(error_handler)
    log.info("Nexora starting")
    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
    )

if __name__=="__main__":
    main()
