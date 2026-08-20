import threading,time
from database import get
from economy import tick

def loop():
    while True:
        try: tick()
        except Exception: pass
        time.sleep(max(10,int(get('tick_seconds',60))))
def start(): threading.Thread(target=loop,daemon=True).start()
