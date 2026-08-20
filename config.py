import os
BOT_TOKEN=os.getenv('BOT_TOKEN','').strip()
OWNER_ID=int(os.getenv('OWNER_ID','0') or 0)
NEWS_CHAT_ID=os.getenv('NEWS_CHAT_ID','').strip()
DB_PATH=os.getenv('DB_PATH','nexora.db')
PORT=int(os.getenv('PORT','10000'))
