from database import db,get,enabled,now
from config import NEWS_CHAT_ID
from telegram.constants import ParseMode
async def publish(context,text):
    if not enabled('news'): return
    text=text.replace('\n',' ').strip()[:int(get('news_max_length',300))]
    msg=f"{get('news_prefix','**')}{text}{get('news_suffix','**')}"
    c=db(); c.execute('INSERT INTO news(text,created_at) VALUES(?,?)',(msg,now())); c.commit(); c.close()
    if NEWS_CHAT_ID:
        try: await context.bot.send_message(chat_id=NEWS_CHAT_ID,text=msg,parse_mode=ParseMode.MARKDOWN)
        except Exception:
            try: await context.bot.send_message(chat_id=NEWS_CHAT_ID,text=msg)
            except Exception: pass
