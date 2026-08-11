import threading, time
class BackgroundLoop:
    def __init__(self, fn, hz):
        self.fn = fn; self.period = 1.0 / hz
        self.running = False; self.thread = None
    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
    def _run(self):
        while self.running:
            t0 = time.time(); self.fn()
            time.sleep(max(0.0, self.period - (time.time() - t0)))