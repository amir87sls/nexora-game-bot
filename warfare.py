import random
from database import db,now,enabled
from military import power

def declare(a,d):
    if not enabled('war'): return None
    c=db(); cur=c.execute('INSERT INTO wars(attacker_id,defender_id,started_at) VALUES(?,?,?)',(a,d,now())); c.commit(); wid=cur.lastrowid; c.close(); return wid

def round_battle(wid):
    if not enabled('battle'): return None
    c=db(); w=c.execute('SELECT * FROM wars WHERE id=? AND status="active"',(wid,)).fetchone()
    if not w:c.close(); return None
    ap=max(1,power(w['attacker_id'])); dp=max(1,power(w['defender_id'])); ar=ap*random.uniform(.85,1.15); dr=dp*random.uniform(.85,1.15)
    al=int(max(0,dr/ap)*random.randint(1,20)); dl=int(max(0,ar/dp)*random.randint(1,20))
    c.execute('UPDATE wars SET rounds=rounds+1,attacker_losses=attacker_losses+?,defender_losses=defender_losses+? WHERE id=?',(al,dl,wid)); c.commit(); c.close(); return {'attacker_power':ap,'defender_power':dp,'attacker_losses':al,'defender_losses':dl,'winner':w['attacker_id'] if ar>dr else w['defender_id']}

def peace(wid):
    if not enabled('peace'): return False
    c=db(); cur=c.execute("UPDATE wars SET status='peace' WHERE id=? AND status='active'",(wid,)); c.commit(); c.close(); return cur.rowcount>0
