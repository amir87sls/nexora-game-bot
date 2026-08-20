import threading
from flask import Flask
from telegram import Update,InlineKeyboardButton,InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import Application,CommandHandler,CallbackQueryHandler
from config import BOT_TOKEN,OWNER_ID,PORT
from database import init,db,player,country,enabled,setv,FEATURES
from admin import owner_only
from news import publish
from warfare import declare,peace,round_battle
from diplomacy import complaint
from organizations import WHO,IAEA,WTO,WORLD_BANK,case
from alliances import create
from game_engine import start as start_engine

app=Flask(__name__)
@app.get('/')
def health():return 'Nexora Game Bot is running.',200

def menu():
    return InlineKeyboardMarkup([[InlineKeyboardButton('🌍 کشور من',callback_data='country'),InlineKeyboardButton('💰 اقتصاد',callback_data='economy')],[InlineKeyboardButton('🪖 ارتش',callback_data='army'),InlineKeyboardButton('⚔️ جنگ',callback_data='war')],[InlineKeyboardButton('🏛 سازمان‌ها',callback_data='orgs'),InlineKeyboardButton('🛡 اتحادها',callback_data='alliances')],[InlineKeyboardButton('⚖️ شکایت',callback_data='complaint'),InlineKeyboardButton('📰 اخبار',callback_data='news')]])
async def start_cmd(u,c): player(u.effective_user.id); await u.effective_message.reply_text('🌍 Nexora World War\n\nکشورت را مدیریت کن.',reply_markup=menu())
async def cb(u,c):
    q=u.callback_query; await q.answer(); d=q.data; co=player(q.from_user.id)
    if d=='country':
        await q.edit_message_text(f"🌍 {co['name']}\n💰 {co['money']:,}\n👥 {co['population']:,}\n🏭 صنعت {co['industry']}\n📈 اقتصاد {co['economy']}\n🛡 ثبات {co['stability']}\n⚔️ قدرت {co['military']}\n🏥 سلامت {co['health']}\n☢️ هسته‌ای {co['nuclear_level']}",reply_markup=menu());return
    if d=='economy':
        await q.edit_message_text('💰 اقتصاد فعال است. درآمد بر اساس جمعیت، صنعت، اقتصاد و ثبات محاسبه می‌شود.',reply_markup=menu());return
    if d=='army':
        x=db(); us=x.execute('SELECT kind,count,power,location FROM units WHERE country_id=?',(co['id'],)).fetchall(); es=x.execute('SELECT kind,quantity FROM equipment WHERE country_id=?',(co['id'],)).fetchall(); x.close()
        t='🪖 نیروها\n'+('\n'.join(f"• {r['kind']}: {r['count']:,} | قدرت {r['power']:,} | 📍 {r['location']}" for r in us) or '—')+'\n\n⚙️ تجهیزات\n'+('\n'.join(f"• {r['kind']}: {r['quantity']:,}" for r in es) or '—'); await q.edit_message_text(t,reply_markup=menu());return
    if d=='war': await q.edit_message_text('⚔️ /war نام_کشور برای اعلان جنگ\n/peace نام_کشور برای صلح',reply_markup=menu());return
    if d=='complaint': await q.edit_message_text('⚖️ /complaint نام_کشور | موضوع',reply_markup=menu());return
    if d=='alliances': await q.edit_message_text('🛡 NATO\n🟣 BRICS\n➕ ساخت اتحاد جدید توسط مالک: /alliance نام',reply_markup=menu());return
    if d=='news':
        x=db(); rs=x.execute('SELECT text FROM news ORDER BY id DESC LIMIT 10').fetchall();x.close(); await q.edit_message_text('📰 اخبار\n\n'+('\n'.join(r['text'] for r in rs) or '—'),reply_markup=menu());return
    if d=='orgs':
        rows=[]
        for k,t in [('UN','🇺🇳 سازمان ملل'),('WHO','🦠 سازمان بهداشت جهانی'),('IAEA','☢️ سازمان انرژی اتمی'),('WTO','📊 سازمان تجارت جهانی'),('WORLD_BANK','🏦 بانک جهانی')]:
            if enabled(k.lower() if k!='WORLD_BANK' else 'world_bank'): rows.append([InlineKeyboardButton(t,callback_data='org:'+k)])
        await q.edit_message_text('🏛 سازمان‌ها',reply_markup=InlineKeyboardMarkup(rows+[[InlineKeyboardButton('🔙',callback_data='country')]]));return
    if d.startswith('org:'):
        org=d.split(':')[1]
        opts={'WHO':WHO,'IAEA':IAEA,'WTO':WTO,'WORLD_BANK':WORLD_BANK}.get(org,['⚖️ شکایت بین کشورها','📂 پرونده‌ها','🗳️ رأی‌گیری'])
        await q.edit_message_text(f'🏛 {org}\n\n'+'\n'.join(f'• {x}' for x in opts),reply_markup=menu());return
    if d.startswith('toggle:') and q.from_user.id==OWNER_ID:
        k=d.split(':')[1];setv(k,not enabled(k));await admin_cmd(u,c);return
@owner_only
async def admin_cmd(u,c):
    rows=[[InlineKeyboardButton(('🟢 ' if enabled(k) else '🔴 ')+k,callback_data='toggle:'+k)] for k in FEATURES]
    await u.effective_message.reply_text('👑 پنل مالک',reply_markup=InlineKeyboardMarkup(rows))
@owner_only
async def feature_cmd(u,c):
    if len(c.args)!=2:return await u.effective_message.reply_text('/feature system on|off')
    k,v=c.args
    if k not in FEATURES or v not in ('on','off'):return await u.effective_message.reply_text('نامعتبر')
    setv(k,v=='on');await u.effective_message.reply_text('ذخیره شد.')
@owner_only
async def country_cmd(u,c):
    if not c.args:return await u.effective_message.reply_text('/country نام')
    n=' '.join(c.args);x=db()
    try:x.execute('INSERT INTO countries(name) VALUES(?)',(n,));x.commit();m='ساخته شد.'
    except Exception:m='از قبل وجود دارد.'
    x.close();await u.effective_message.reply_text('🌍 '+n+' '+m)
async def complaint_cmd(u,c):
    raw=' '.join(c.args)
    if '|' not in raw:return await u.effective_message.reply_text('/complaint کشور | موضوع')
    n,s=[x.strip() for x in raw.split('|',1)]; a=player(u.effective_user.id); b=country(n)
    if not b:return await u.effective_message.reply_text('کشور پیدا نشد.')
    complaint(a['id'],b['id'],'UN',s);await u.effective_message.reply_text('⚖️ شکایت ثبت شد.');await publish(c,f"{a['name']} از {b['name']} شکایت کرد.")
async def war_cmd(u,c):
    if not c.args:return await u.effective_message.reply_text('/war کشور')
    a=player(u.effective_user.id);b=country(' '.join(c.args))
    if not b:return await u.effective_message.reply_text('کشور پیدا نشد.')
    declare(a['id'],b['id']);await u.effective_message.reply_text('⚔️ جنگ آغاز شد.');await publish(c,f"جنگ میان {a['name']} و {b['name']} آغاز شد.")
async def peace_cmd(u,c):
    if not c.args:return await u.effective_message.reply_text('/peace کشور')
    a=player(u.effective_user.id);b=country(' '.join(c.args));
    if not b:return await u.effective_message.reply_text('کشور پیدا نشد.')
    x=db();w=x.execute("SELECT id FROM wars WHERE status='active' AND ((attacker_id=? AND defender_id=?) OR (attacker_id=? AND defender_id=?)) LIMIT 1",(a['id'],b['id'],b['id'],a['id'])).fetchone();x.close()
    if not w:return await u.effective_message.reply_text('جنگ فعالی نیست.')
    peace(w['id']);await u.effective_message.reply_text('🕊️ جنگ پایان یافت.');await publish(c,f"جنگ میان {a['name']} و {b['name']} پایان یافت.")
@owner_only
async def newsstyle(u,c):
    raw=' '.join(c.args)
    if '|' not in raw:return await u.effective_message.reply_text('/newsstyle prefix|suffix')
    a,b=raw.split('|',1);setv('news_prefix',a);setv('news_suffix',b);await u.effective_message.reply_text('قالب خبر ذخیره شد.')
@owner_only
async def newslength(u,c):
    if not c.args or not c.args[0].isdigit():return await u.effective_message.reply_text('/newslength 300')
    setv('news_max_length',max(50,min(1000,int(c.args[0]))));await u.effective_message.reply_text('ذخیره شد.')
@owner_only
async def alliance_cmd(u,c):
    if not c.args:return await u.effective_message.reply_text('/alliance نام')
    create(' '.join(c.args),OWNER_ID);await u.effective_message.reply_text('🛡 اتحاد ساخته شد.')

def run():
    init();start_engine()
    threading.Thread(target=lambda:app.run(host='0.0.0.0',port=PORT,use_reloader=False),daemon=True).start()
    if not BOT_TOKEN: raise RuntimeError('BOT_TOKEN is missing')
    a=Application.builder().token(BOT_TOKEN).build()
    for cmd,fn in [('start',start_cmd),('admin',admin_cmd),('feature',feature_cmd),('country',country_cmd),('complaint',complaint_cmd),('war',war_cmd),('peace',peace_cmd),('newsstyle',newsstyle),('newslength',newslength),('alliance',alliance_cmd)]:a.add_handler(CommandHandler(cmd,fn))
    a.add_handler(CallbackQueryHandler(cb));a.run_polling(drop_pending_updates=True)
if __name__=='__main__':run()
