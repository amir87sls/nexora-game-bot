from database import db,now,enabled
def complaint(a,d,org,subject):
    if not enabled('complaints'): return False
    c=db(); c.execute('INSERT INTO complaints(from_country,to_country,organization,subject,created_at) VALUES(?,?,?,?,?)',(a,d,org,subject,now())); c.commit(); c.close(); return True
