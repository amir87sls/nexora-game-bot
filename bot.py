import os, sqlite3, threading, time
from datetime import datetime, timedelta, timezone
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters

TOKEN=os.getenv('BOT_TOKEN','').strip()
PORT=int(os.getenv('PORT','10000'))
DB=os.getenv('DB_PATH','nexora.db')
app=Flask(__name__)
@app.get('/')
def health(): return 'Nexora Game Bot OK',200

def db():
    c=sqlite3.connect(DB,check_same_thread=False); c.row_factory=sqlite3.Row; return c
def now(): return datetime.now(timezone.utc)
def iso(t=None): return (t or now()).isoformat()
def setting(k,d=''):
    c=db(); r=c.execute('SELECT v FROM settings WHERE k=?',(k,)).fetchone(); c.close(); return r['v'] if r else d
def set_setting(k,v):
    c=db(); c.execute("INSERT INTO settings(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v",(k,str(v))); c.commit(); c.close()
def owner(uid): return int(setting('owner_id','0'))==uid and uid!=0
def admin(uid,role): return owner(uid) or int(setting('admin_'+role,'0'))==uid

def init():
    c=db(); c.executescript('''
    CREATE TABLE IF NOT EXISTS settings(k TEXT PRIMARY KEY,v TEXT);
    CREATE TABLE IF NOT EXISTS players(tg_id INTEGER PRIMARY KEY,nickname TEXT,exam_passed INTEGER DEFAULT 0,score INTEGER DEFAULT 0,country_id INTEGER);
    CREATE TABLE IF NOT EXISTS countries(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT UNIQUE,owner_id INTEGER UNIQUE,money INTEGER DEFAULT 1000000,equipment TEXT DEFAULT '',assets TEXT DEFAULT '',groups_here TEXT DEFAULT '',alive INTEGER DEFAULT 1);
    CREATE TABLE IF NOT EXISTS questions(id INTEGER PRIMARY KEY AUTOINCREMENT,q TEXT,a TEXT,active INTEGER DEFAULT 1);
    CREATE TABLE IF NOT EXISTS submissions(id INTEGER PRIMARY KEY AUTOINCREMENT,kind TEXT,country_id INTEGER,player_id INTEGER,text TEXT,admin_id INTEGER,status TEXT DEFAULT 'pending',result TEXT DEFAULT '',news INTEGER DEFAULT 0,created_at TEXT);
    CREATE TABLE IF NOT EXISTS agreements(id INTEGER PRIMARY KEY AUTOINCREMENT,from_country INTEGER,to_country INTEGER,text TEXT,status TEXT DEFAULT 'pending');
    CREATE TABLE IF NOT EXISTS helps(id INTEGER PRIMARY KEY AUTOINCREMENT,from_country INTEGER,to_country INTEGER,text TEXT,status TEXT DEFAULT 'pending');
    CREATE TABLE IF NOT EXISTS groups(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT UNIQUE,owner_id INTEGER,host_country INTEGER);
    CREATE TABLE IF NOT EXISTS deployments(id INTEGER PRIMARY KEY AUTOINCREMENT,country_id INTEGER,target_country INTEGER,text TEXT,finish_at TEXT,status TEXT DEFAULT 'pending');
    CREATE TABLE IF NOT EXISTS repairs(id INTEGER PRIMARY KEY AUTOINCREMENT,country_id INTEGER,text TEXT,finish_at TEXT,status TEXT DEFAULT 'pending');
    CREATE TABLE IF NOT EXISTS news(id INTEGER PRIMARY KEY AUTOINCREMENT,text TEXT,created_at TEXT);
    CREATE TABLE IF NOT EXISTS history(id INTEGER PRIMARY KEY AUTOINCREMENT,season INTEGER,winner_country TEXT,winner_player TEXT);
    CREATE TABLE IF NOT EXISTS seasons(id INTEGER PRIMARY KEY AUTOINCREMENT,number INTEGER,status TEXT,start_at TEXT,end_at TEXT);
    ''')
    defaults={'owner_id':0,'exam_pass':70,'training_url':'','chat_link':'','news_chat_id':'','news_prefix':'**','news_suffix':'**','transfer_hours':1,'repair_hours':12,'season_days':5,'season_enabled':1,'news_enabled':1,'statements_enabled':1}
    for k,v in defaults.items(): c.execute('INSERT OR IGNORE INTO settings VALUES(?,?)',(k,str(v)))
    for role in ['war','scenario','roll','invention','complaints','assets','organizations','statement']:
        c.execute('INSERT OR IGNORE INTO settings VALUES(?,?)',('admin_'+role,'0'))
    if not c.execute('SELECT 1 FROM questions').fetchone():
        c.executemany('INSERT INTO questions(q,a) VALUES(?,?)',[("آیا قبل از کشورگیری باید آزمون را قبول کرد؟","بله"),("آیا نتیجه رول قبل از تأیید ادمین اعمال می‌شود؟","خیر"),("زمان پیش‌فرض انتقال چند ساعت است؟","1"),("زمان پیش‌فرض تعمیر چند ساعت است؟","12"),("تفاهم‌نامه با قبول کدام طرف نهایی می‌شود؟","هدف")])
    c.commit(); c.close()
init()

def player(uid):
    c=db(); r=c.execute('SELECT * FROM players WHERE tg_id=?',(uid,)).fetchone(); c.close(); return r
def country(uid):
    p=player(uid)
    if not p or not p['country_id']: return None
    c=db(); r=c.execute('SELECT * FROM countries WHERE id=?',(p['country_id'],)).fetchone(); c.close(); return r
async def send_admin(context,role,text):
    aid=int(setting('admin_'+role,'0') or 0)
    if aid:
        try: await context.bot.send_message(aid,text)
        except Exception: pass
async def publish(context,text):
    if setting('news_enabled','1')!='1': return
    msg=f"{setting('news_prefix','**')}{text[:250]}{setting('news_suffix','**')}"
    c=db(); c.execute('INSERT INTO news(text,created_at) VALUES(?,?)',(msg,iso())); c.commit(); c.close()
    chat=setting('news_chat_id','')
    if chat:
        try: await context.bot.send_message(chat,msg,parse_mode='Markdown')
        except Exception: pass

def menu():
    return InlineKeyboardMarkup([
      [InlineKeyboardButton('🌍 کشور من',callback_data='country'),InlineKeyboardButton('💰 اقتصاد',callback_data='economy')],
      [InlineKeyboardButton('⚔️ جنگ',callback_data='war'),InlineKeyboardButton('🪖 ارتش',callback_data='army')],
      [InlineKeyboardButton('🏛 سازمان‌ها',callback_data='orgs'),InlineKeyboardButton('🤝 اتحادها',callback_data='alliances')],
      [InlineKeyboardButton('📝 رول',callback_data='roll'),InlineKeyboardButton('🧪 اختراع',callback_data='invention')],
      [InlineKeyboardButton('🎬 سناریو',callback_data='scenario'),InlineKeyboardButton('📜 تفاهم‌نامه',callback_data='agreement')],
      [InlineKeyboardButton('🆘 درخواست کمک',callback_data='help'),InlineKeyboardButton('📢 بیانیه',callback_data='statement')],
      [InlineKeyboardButton('🏴 گروهک',callback_data='group')]])

async def start(update,context):
    uid=update.effective_user.id
    if int(setting('owner_id','0'))==0:
        set_setting('owner_id',uid); await update.message.reply_text('👑 اولین کاربر به عنوان مالک دائمی ثبت شد.')
    c=db(); c.execute('INSERT OR IGNORE INTO players(tg_id) VALUES(?)',(uid,)); c.commit(); c.close()
    p=player(uid)
    if not p['exam_passed']:
        return await update.message.reply_text(f"📚 قوانین و آموزش را بخوان:\n{setting('training_url','')}\n\nقبولی: {setting('exam_pass','70')}٪\n/exam")
    if not p['country_id']: return await countries(update,context)
    await update.message.reply_text('🎮 Nexora',reply_markup=menu())

async def exam(update,context):
    c=db(); qs=c.execute('SELECT * FROM questions WHERE active=1 ORDER BY RANDOM() LIMIT 5').fetchall(); c.close()
    if not qs: return await update.message.reply_text('❌ سؤال فعالی وجود ندارد.')
    context.user_data['exam']=[dict(x) for x in qs]; context.user_data['i']=0; context.user_data['ok']=0
    await ask_exam(update,context)
async def ask_exam(update,context):
    d=context.user_data
    if d['i']>=len(d['exam']):
        score=round(100*d['ok']/len(d['exam'])); passed=score>=int(setting('exam_pass','70'))
        c=db(); c.execute('UPDATE players SET score=?,exam_passed=? WHERE tg_id=?',(score,int(passed),update.effective_user.id)); c.commit(); c.close()
        return await update.effective_message.reply_text(('🎉 آزمون قبول شد.' if passed else '❌ آزمون رد شد.')+f' نمره: {score}%'+('\n/countries' if passed else '\n/exam'))
    await update.effective_message.reply_text(f"❓ {d['i']+1}/{len(d['exam'])}\n{d['exam'][d['i']]['q']}")

async def countries(update,context):
    p=player(update.effective_user.id)
    if not p or not p['exam_passed']: return await update.effective_message.reply_text('❌ ابتدا آزمون را قبول کن.')
    allc=['ایران','آلمان','فرانسه','انگلیس','ایتالیا','اسپانیا','ترکیه','روسیه','چین','ژاپن','هند','برزیل','کانادا','استرالیا','مصر','مکزیک','عراق','آفریقای جنوبی']
    c=db(); taken={r['name'] for r in c.execute('SELECT name FROM countries WHERE alive=1')}; c.close()
    free=[x for x in allc if x not in taken]
    await update.effective_message.reply_text('🌍 کشورهای آزاد:\n'+'\n'.join('• '+x for x in free)+'\n\n/takecountry نام کشور')
async def takecountry(update,context):
    p=player(update.effective_user.id)
    if not p or not p['exam_passed']: return await update.message.reply_text('❌ ابتدا آزمون.')
    name=' '.join(context.args).strip()
    if not name: return await countries(update,context)
    c=db(); taken=c.execute('SELECT 1 FROM countries WHERE name=?',(name,)).fetchone()
    if taken: c.close(); return await update.message.reply_text('❌ این کشور قبلاً گرفته شده.')
    c.execute('INSERT INTO countries(name,owner_id) VALUES(?,?)',(name,update.effective_user.id)); cid=c.execute('SELECT last_insert_rowid()').fetchone()[0]
    c.execute('UPDATE players SET country_id=? WHERE tg_id=?',(cid,update.effective_user.id)); c.commit(); c.close()
    await update.message.reply_text(f'✅ {name} برای تو ثبت شد.\n💬 گپ: {setting("chat_link","")}\nکانال اخبار: {setting("news_chat_id","")}')
    await send_admin(context,'assets',f'ℹ️ کشور {name} توسط {update.effective_user.id} گرفته شد؛ لطفاً دسترسی ارسال پیام گپ را دستی باز کنید.')

async def submit(update,context,kind):
    co=country(update.effective_user.id)
    if not co: return await update.message.reply_text('❌ کشور نداری.')
    text=' '.join(context.args).strip()
    if not text: return await update.message.reply_text(f'/{kind} متن را بنویس.')
    role={'scenario':'scenario','roll':'roll','invention':'invention'}[kind]; aid=int(setting('admin_'+role,'0') or 0)
    if not aid: return await update.message.reply_text('❌ ادمین این بخش تعیین نشده.')
    c=db(); c.execute('INSERT INTO submissions(kind,country_id,player_id,text,admin_id) VALUES(?,?,?,?,?)',(kind,co['id'],update.effective_user.id,text,aid)); sid=c.execute('SELECT last_insert_rowid()').fetchone()[0]; c.commit(); c.close()
    await send_admin(context,role,f'📥 {kind} #{sid}\nکشور: {co["name"]}\n\n{text}\n\nپس از بررسی: /result {sid} متن نتیجه')
    await update.message.reply_text('✅ درخواست برای ادمین ارسال شد؛ قبل از نتیجه هیچ تغییری اعمال نمی‌شود.')
async def result(update,context):
    if len(context.args)<2: return await update.message.reply_text('/result شناسه نتیجه')
    c=db(); s=c.execute('SELECT * FROM submissions WHERE id=?',(int(context.args[0]),)).fetchone(); c.close()
    if not s or not (owner(update.effective_user.id) or update.effective_user.id==s['admin_id']): return await update.message.reply_text('⛔ دسترسی/درخواست نامعتبر.')
    result=' '.join(context.args[1:]); c=db(); c.execute("UPDATE submissions SET status='approved',result=? WHERE id=?",(result,s['id'])); c.execute('UPDATE countries SET assets=assets||? WHERE id=?',(f'\n{s["kind"]}: {result}',s['country_id'])); c.commit(); c.close()
    c=db(); co=c.execute('SELECT name FROM countries WHERE id=?',(s['country_id'],)).fetchone()['name']; c.close()
    await publish(context,f'{co}: نتیجه {s["kind"]} ثبت شد — {result}')
    await update.message.reply_text('✅ نتیجه ثبت و خبر منتشر شد.')

async def agreement(update,context):
    co=country(update.effective_user.id); raw=' '.join(context.args)
    if not co or '|' not in raw: return await update.message.reply_text('/agreement کشور هدف | متن')
    target,text=raw.split('|',1); c=db(); d=c.execute('SELECT * FROM countries WHERE name=?',(target.strip(),)).fetchone()
    if not d: c.close(); return await update.message.reply_text('❌ کشور هدف پیدا نشد.')
    c.execute('INSERT INTO agreements(from_country,to_country,text) VALUES(?,?,?)',(co['id'],d['id'],text.strip())); aid=c.execute('SELECT last_insert_rowid()').fetchone()[0]; c.commit(); c.close()
    try: await context.bot.send_message(d['owner_id'],f'📜 تفاهم‌نامه از {co["name"]}:\n{text.strip()}\n/accept_agreement {aid}\n/reject_agreement {aid}')
    except Exception: pass
    await update.message.reply_text('📜 ارسال شد.')
async def agreement_decision(update,context,yes):
    if not context.args:return
    aid=int(context.args[0]); c=db(); a=c.execute('SELECT * FROM agreements WHERE id=?',(aid,)).fetchone(); target=country(update.effective_user.id)
    if not a or not target or target['id']!=a['to_country']: c.close(); return await update.message.reply_text('⛔ نامعتبر.')
    c.execute('UPDATE agreements SET status=? WHERE id=?',('accepted' if yes else 'rejected',aid)); c.commit(); c.close()
    if yes:
        c=db(); f=c.execute('SELECT name FROM countries WHERE id=?',(a['from_country'],)).fetchone()['name']; c.close(); await publish(context,f'تفاهم‌نامه‌ای میان {f} و {target["name"]} امضا شد.')
    await update.message.reply_text('✅ قبول شد.' if yes else '❌ رد شد.')

async def help_request(update,context):
    co=country(update.effective_user.id); raw=' '.join(context.args)
    if not co or '|' not in raw:return await update.message.reply_text('/help کشور هدف | درخواست')
    target,text=raw.split('|',1); c=db(); d=c.execute('SELECT * FROM countries WHERE name=?',(target.strip(),)).fetchone()
    if not d:c.close();return await update.message.reply_text('❌ کشور پیدا نشد.')
    c.execute('INSERT INTO helps(from_country,to_country,text) VALUES(?,?,?)',(co['id'],d['id'],text.strip())); hid=c.execute('SELECT last_insert_rowid()').fetchone()[0];c.commit();c.close()
    try: await context.bot.send_message(d['owner_id'],f'🆘 {co["name"]} درخواست کمک دارد:\n{text}\n/accept_help {hid}\n/reject_help {hid}')
    except Exception:pass
    await send_admin(context,'assets',f'🆘 درخواست کمک {co["name"]} به {d["name"]} ارسال شد.')
    await update.message.reply_text('🆘 درخواست ارسال شد.')
async def help_decision(update,context,yes):
    if not context.args:return
    hid=int(context.args[0]);c=db();h=c.execute('SELECT * FROM helps WHERE id=?',(hid,)).fetchone();target=country(update.effective_user.id)
    if not h or not target or target['id']!=h['to_country']:c.close();return
    c.execute('UPDATE helps SET status=? WHERE id=?',('accepted' if yes else 'rejected',hid));c.commit();c.close()
    if yes: await send_admin(context,'scenario',f'🤝 {target["name"]} قبول کرد در عملیات/پروژه کمک کند: {h["text"]}')
    await update.message.reply_text('✅ قبول شد.' if yes else '❌ رد شد.')

async def statement(update,context):
    co=country(update.effective_user.id); text=' '.join(context.args).strip()
    if not co or not text:return await update.message.reply_text('/statement متن بیانیه')
    aid=int(setting('admin_statement','0') or 0)
    if aid:
        await send_admin(context,'statement',f'📢 بیانیه {co["name"]}:\n{text}'); return await update.message.reply_text('📢 برای ادمین بیانیه ارسال شد.')
    await publish(context,f'بیانیه {co["name"]}: {text}'); await update.message.reply_text('📢 منتشر شد.')

async def group(update,context):
    c=db(); rows=c.execute('SELECT * FROM groups WHERE owner_id=?',(update.effective_user.id,)).fetchall(); c.close()
    if not rows:return await update.message.reply_text('🏴 گروهکی برای این حساب ثبت نشده.')
    await update.message.reply_text('\n'.join(f'{r["name"]}: '+('مستقر' if r['host_country'] else 'مستقر نشده') for r in rows))
async def deploy(update,context):
    c=db();g=c.execute('SELECT * FROM groups WHERE owner_id=?',(update.effective_user.id,)).fetchone(); target=' '.join(context.args).strip(); d=c.execute('SELECT * FROM countries WHERE name=?',(target,)).fetchone()
    if not g or not d:c.close();return await update.message.reply_text('❌ گروهک/کشور پیدا نشد.')
    c.execute('UPDATE groups SET host_country=? WHERE id=?',(d['id'],g['id']));c.execute('UPDATE countries SET groups_here=groups_here||? WHERE id=?',(f'\n{g["name"]}',d['id']));c.commit();c.close()
    await publish(context,f'{g["name"]} در {d["name"]} مستقر شد.');await update.message.reply_text('✅ مستقر شد.')

async def war(update,context):
    co=country(update.effective_user.id); target=' '.join(context.args).strip()
    if not co:return await update.message.reply_text('❌ کشور نداری.')
    if not target:return await update.message.reply_text('/war کشور هدف')
    c=db();d=c.execute('SELECT * FROM countries WHERE name=? AND alive=1',(target,)).fetchone();c.close()
    if not d:return await update.message.reply_text('❌ کشور هدف پیدا نشد.')
    await update.message.reply_text('🎬 سناریوی حمله را با /scenario ارسال کن؛ سناریو برای ادمین سناریو می‌رود.')
    await send_admin(context,'war',f'⚔️ {co["name"]} هدف جنگ را {d["name"]} اعلام کرد.')

async def admin_panel(update,context):
    if not owner(update.effective_user.id):return await update.message.reply_text('⛔ فقط مالک.')
    await update.message.reply_text('👑 پنل مالک\n/set کلید مقدار\n/set admin_war ID\n/set admin_scenario ID\n/set admin_roll ID\n/set admin_invention ID\n/set admin_complaints ID\n/set admin_assets ID\n/set admin_organizations ID\n/set admin_statement ID\n/set exam_pass عدد\n/set training_url لینک\n/set chat_link لینک\n/set news_chat_id ID\n/set transfer_hours 1\n/set repair_hours 12\n/set season_days 5\nهمه تنظیمات از همین مسیر قابل تغییرند.')
async def setcmd(update,context):
    if not owner(update.effective_user.id):return await update.message.reply_text('⛔ فقط مالک.')
    if len(context.args)<2:return await update.message.reply_text('/set کلید مقدار')
    set_setting(context.args[0],' '.join(context.args[1:]));await update.message.reply_text('✅ ذخیره شد.')

async def cb(update,context):
    q=update.callback_query;await q.answer();d=q.data
    co=country(q.from_user.id)
    if d=='country':return await q.edit_message_text('❌ کشور نداری.' if not co else f'🌍 {co["name"]}\n💰 {co["money"]:,}\n📦 {co["equipment"] or "ثبت نشده"}\n🏴 گروهک‌های مستقر: {co["groups_here"] or "ندارد"}',reply_markup=menu())
    if d=='economy':return await q.edit_message_text('💰 اقتصاد\nدارایی: '+(f'{co["money"]:,}' if co else '—'),reply_markup=menu())
    if d=='army':return await q.edit_message_text('🪖 تجهیزات\n'+(co['equipment'] if co else '—'),reply_markup=menu())
    if d=='war':return await q.edit_message_text('⚔️ /war کشور هدف',reply_markup=menu())
    if d in ('roll','invention','scenario'):return await q.edit_message_text(f'/{d} متن درخواست',reply_markup=menu())
    if d=='agreement':return await q.edit_message_text('/agreement کشور هدف | متن',reply_markup=menu())
    if d=='help':return await q.edit_message_text('/help کشور هدف | درخواست',reply_markup=menu())
    if d=='statement':return await q.edit_message_text('/statement متن بیانیه',reply_markup=menu())
    if d=='group':return await q.edit_message_text('/group\n/deploy نام کشور',reply_markup=menu())
    if d=='orgs':return await q.edit_message_text('🏛 سازمان‌ها\n🇺🇳 سازمان ملل\n🦠 سازمان بهداشت جهانی\n☢️ سازمان انرژی اتمی\n📊 سازمان تجارت جهانی\n🏦 بانک جهانی',reply_markup=menu())
    if d=='alliances':return await q.edit_message_text('🤝 NATO\n🟣 BRICS',reply_markup=menu())

def ticker():
    while True:
        try:
            c=db(); nowv=now()
            for r in c.execute("SELECT * FROM deployments WHERE status='pending'").fetchall():
                if nowv>=datetime.fromisoformat(r['finish_at']):c.execute("UPDATE deployments SET status='completed' WHERE id=?",(r['id'],))
            for r in c.execute("SELECT * FROM repairs WHERE status='pending'").fetchall():
                if nowv>=datetime.fromisoformat(r['finish_at']):c.execute("UPDATE repairs SET status='completed' WHERE id=?",(r['id'],))
            c.commit();c.close()
        except Exception:pass
        time.sleep(20)

def main():
    if not TOKEN: raise RuntimeError('BOT_TOKEN is missing')
    threading.Thread(target=lambda:web.run(host='0.0.0.0',port=PORT,use_reloader=False),daemon=True).start()
    threading.Thread(target=ticker,daemon=True).start()
    a=Application.builder().token(TOKEN).build()
    a.add_handler(CommandHandler('start',start));a.add_handler(CommandHandler('exam',exam));a.add_handler(CommandHandler('countries',countries));a.add_handler(CommandHandler('takecountry',takecountry))
    for n in ['roll','invention','scenario']: a.add_handler(CommandHandler(n,lambda u,c,n=n:submit(u,c,n)))
    a.add_handler(CommandHandler('result',result));a.add_handler(CommandHandler('agreement',agreement));a.add_handler(CommandHandler('accept_agreement',lambda u,c:agreement_decision(u,c,True)));a.add_handler(CommandHandler('reject_agreement',lambda u,c:agreement_decision(u,c,False)))
    a.add_handler(CommandHandler('help',help_request));a.add_handler(CommandHandler('accept_help',lambda u,c:help_decision(u,c,True)));a.add_handler(CommandHandler('reject_help',lambda u,c:help_decision(u,c,False)))
    a.add_handler(CommandHandler('statement',statement));a.add_handler(CommandHandler('group',group));a.add_handler(CommandHandler('deploy',deploy));a.add_handler(CommandHandler('war',war));a.add_handler(CommandHandler('admin',admin_panel));a.add_handler(CommandHandler('set',setcmd))
    a.add_handler(CallbackQueryHandler(cb));a.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,text));a.run_polling(drop_pending_updates=True)
if __name__=='__main__':main()
