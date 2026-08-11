# Snapshot: threaded multi-ToF manager (early form)
import threading, time
class ThreadedSensorManager:
    def __init__(self, config):
        self.data = {"front_mm": 850.0, "left_mm": 230.0, "right_mm": 240.0}
        self.flags = {"front_ok": False, "left_ok": False, "right_ok": False, "mpu_ok": False}
        self.lock = threading.Lock()
        self.running = True
        threading.Thread(target=self._poll, daemon=True).start()
    def _poll(self):
        while self.running:
            f, fo = self._read_front()
            l, lo = self._read_left()
            r, ro = self._read_right()
            with self.lock:
                if fo and f > 0: self.data["front_mm"] = f
                if lo and l > 0: self.data["left_mm"] = l
                if ro and r > 0: self.data["right_mm"] = r
                self.flags.update(front_ok=fo, left_ok=lo, right_ok=ro)
            time.sleep(0.01)
    def read_sensors(self):
        with self.lock:
            return dict(self.data, flags=dict(self.flags))