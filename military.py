from database import db,enabled
UNIT_POWER={'پیاده':1,'تانک':8,'توپخانه':6,'هواپیما':15,'ناو':20,'زیردریایی':25,'موشک':30}
EQUIP_POWER={'تفنگ':1,'تانک':8,'توپخانه':6,'هواپیما':15,'ناو':20,'زیردریایی':25,'موشک':30}
def add_unit(cid,kind,count,location='پایتخت'):
    if not enabled('units'): return False
    p=UNIT_POWER.get(kind,1); c=db(); c.execute('INSERT INTO units(country_id,kind,count,power,location) VALUES(?,?,?,?,?)',(cid,kind,count,p*count,location)); c.commit(); c.close(); return True
def add_equipment(cid,kind,qty):
    if not enabled('equipment'): return False
    p=EQUIP_POWER.get(kind,1); c=db(); c.execute('INSERT INTO equipment(country_id,kind,quantity,power) VALUES(?,?,?,?)',(cid,kind,qty,p)); c.commit(); c.close(); return True
def power(cid,location=None):
    c=db(); q='SELECT COALESCE(SUM(power),0) p FROM units WHERE country_id=?'; args=[cid]
    if location:q+=' AND location=?'; args.append(location)
    u=c.execute(q,args).fetchone()['p']; e=c.execute('SELECT COALESCE(SUM(quantity*power),0) p FROM equipment WHERE country_id=?',(cid,)).fetchone()['p']; c.close(); return int(u+e)
