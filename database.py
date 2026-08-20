import sqlite3, json
from datetime import datetime, timezone
from config import DB_PATH
FEATURES=['economy','tick','units','equipment','deployment','battle','war','losses','peace','complaints','news','un','who','iaea','wto','world_bank','nato','brics']

def now(): return datetime.now(timezone.utc).isoformat()
def db():
    c=sqlite3.connect(DB_PATH,check_same_thread=False); c.row_factory=sqlite3.Row; return c

def init():
    c=db(); c.executescript('''
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS countries(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT UNIQUE NOT NULL,money INTEGER DEFAULT 1000000,population INTEGER DEFAULT 1000000,industry INTEGER DEFAULT 50,economy INTEGER DEFAULT 50,stability INTEGER DEFAULT 70,military INTEGER DEFAULT 50,health INTEGER DEFAULT 70,nuclear_level INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS units(id INTEGER PRIMARY KEY AUTOINCREMENT,country_id INTEGER,kind TEXT,count INTEGER DEFAULT 0,power INTEGER DEFAULT 0,location TEXT DEFAULT 'پایتخت',morale INTEGER DEFAULT 100);
CREATE TABLE IF NOT EXISTS equipment(id INTEGER PRIMARY KEY AUTOINCREMENT,country_id INTEGER,kind TEXT,quantity INTEGER DEFAULT 0,power INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS wars(id INTEGER PRIMARY KEY AUTOINCREMENT,attacker_id INTEGER,defender_id INTEGER,status TEXT DEFAULT 'active',started_at TEXT,rounds INTEGER DEFAULT 0,attacker_losses INTEGER DEFAULT 0,defender_losses INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS complaints(id INTEGER PRIMARY KEY AUTOINCREMENT,from_country INTEGER,to_country INTEGER,organization TEXT,subject TEXT,status TEXT DEFAULT 'pending',created_at TEXT);
CREATE TABLE IF NOT EXISTS org_cases(id INTEGER PRIMARY KEY AUTOINCREMENT,org TEXT,country_id INTEGER,kind TEXT,text TEXT,status TEXT DEFAULT 'open',created_at TEXT);
CREATE TABLE IF NOT EXISTS votes(id INTEGER PRIMARY KEY AUTOINCREMENT,org TEXT,case_id INTEGER,question TEXT,status TEXT DEFAULT 'open',created_at TEXT);
CREATE TABLE IF NOT EXISTS vote_choices(vote_id INTEGER,country_id INTEGER,choice TEXT,PRIMARY KEY(vote_id,country_id));
CREATE TABLE IF NOT EXISTS alliances(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT UNIQUE,kind TEXT DEFAULT 'custom',description TEXT DEFAULT '',owner_id INTEGER);
CREATE TABLE IF NOT EXISTS alliance_members(alliance_id INTEGER,country_id INTEGER,PRIMARY KEY(alliance_id,country_id));
CREATE TABLE IF NOT EXISTS news(id INTEGER PRIMARY KEY AUTOINCREMENT,text TEXT,created_at TEXT);
CREATE TABLE IF NOT EXISTS trade(id INTEGER PRIMARY KEY AUTOINCREMENT,from_country INTEGER,to_country INTEGER,resource TEXT,quantity INTEGER,price INTEGER,status TEXT DEFAULT 'active',created_at TEXT);
CREATE TABLE IF NOT EXISTS loans(id INTEGER PRIMARY KEY AUTOINCREMENT,country_id INTEGER,amount INTEGER,remaining INTEGER,rate REAL,status TEXT DEFAULT 'active',created_at TEXT);
''')
    for f in FEATURES: c.execute('INSERT OR IGNORE INTO settings VALUES(?,?)',(f,json.dumps(True)))
    for k,v in {'news_prefix':'**','news_suffix':'**','news_max_length':300,'tick_seconds':60}.items(): c.execute('INSERT OR IGNORE INTO settings VALUES(?,?)',(k,json.dumps(v,ensure_ascii=False)))
    c.execute("INSERT OR IGNORE INTO alliances(name,kind,description,owner_id) VALUES('NATO','system','اتحاد دفاعی',0)")
    c.execute("INSERT OR IGNORE INTO alliances(name,kind,description,owner_id) VALUES('BRICS','system','اتحاد اقتصادی',0)")
    c.commit(); c.close()

def get(k,d=None):
    c=db(); r=c.execute('SELECT value FROM settings WHERE key=?',(k,)).fetchone(); c.close()
    if not r:return d
    try:return json.loads(r['value'])
    except:return r['value']
def setv(k,v):
    c=db(); c.execute('INSERT INTO settings VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',(k,json.dumps(v,ensure_ascii=False))); c.commit(); c.close()
def enabled(k): return bool(get(k,True))
def country(name):
    c=db(); r=c.execute('SELECT * FROM countries WHERE name=?',(name,)).fetchone(); c.close(); return r
def player(uid):
    n=f'Player-{uid}'; r=country(n)
    if r:return r
    c=db(); c.execute('INSERT INTO countries(name) VALUES(?)',(n,)); c.commit(); r=c.execute('SELECT * FROM countries WHERE name=?',(n,)).fetchone(); c.close(); return r
