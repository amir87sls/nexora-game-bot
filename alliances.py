from database import db
def create(name,owner,description=''):
    c=db(); cur=c.execute('INSERT INTO alliances(name,description,owner_id) VALUES(?,?,?)',(name,description,owner)); c.commit(); x=cur.lastrowid; c.close(); return x
def add_member(aid,cid):
    c=db(); c.execute('INSERT OR IGNORE INTO alliance_members VALUES(?,?)',(aid,cid)); c.commit(); c.close()
