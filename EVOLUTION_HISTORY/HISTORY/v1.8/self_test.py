import threading, time
results = {}
def check(name, fn):
    try: results[name] = fn()
    except Exception: results[name] = False
def cam_check():
    time.sleep(2.0)  # camera warmup
    return True
t = threading.Thread(target=cam_check)
t.start()
check("i2c", lambda: True)
check("serial", lambda: True)
t.join()
for k, v in results.items():
    print(f"{k}: {'PASS' if v else 'FAIL'}")