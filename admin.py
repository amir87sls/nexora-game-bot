from functools import wraps
from config import OWNER_ID
from database import FEATURES,enabled,setv,get

def owner_only(fn):
    @wraps(fn)
    async def w(update,context):
        if not update.effective_user or update.effective_user.id!=OWNER_ID:
            await update.effective_message.reply_text('⛔ فقط مالک.')
            return
        return await fn(update,context)
    return w

def toggle(k):
    if k not in FEATURES:return False
    setv(k,not enabled(k)); return True
