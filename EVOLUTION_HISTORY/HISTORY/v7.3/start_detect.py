import time
def poll_switch(sw_pin, debounce_ms=50):
    last = sw_pin.value; stable_since = time.time()
    while True:
        v = sw_pin.value
        if v != last:
            last = v; stable_since = time.time()
        elif not v and time.time() - stable_since > debounce_ms / 1000.0:
            return True
        time.sleep(0.01)