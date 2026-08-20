from database import db,enabled

def tick():
    if not enabled('tick') or not enabled('economy'): return
    c=db()
    for r in c.execute('SELECT id,population,industry,economy,stability FROM countries').fetchall():
        income=max(0,int((r['population']//100+r['industry']*1000+r['economy']*500)*(0.5+r['stability']/200)))
        c.execute('UPDATE countries SET money=money+? WHERE id=?',(income,r['id']))
    c.commit(); c.close()

def income(country): return max(0,int((country['population']//100+country['industry']*1000+country['economy']*500)*(0.5+country['stability']/200)))
