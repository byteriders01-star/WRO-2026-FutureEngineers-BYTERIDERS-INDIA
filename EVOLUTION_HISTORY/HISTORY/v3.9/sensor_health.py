import logging, time
class Health:
    def __init__(self):
        self.flags = {"front_ok": False, "left_ok": False,
                      "right_ok": False, "mpu_ok": False}
        self._last_log = 0.0
    def update(self, new_flags):
        changed = self.flags != new_flags
        self.flags = new_flags
        if changed and time.time() - self._last_log > 2.0:
            self._last_log = time.time()
            bad = [k for k, v in new_flags.items() if not v]
            if bad: logging.warning(f"Sensor fault: {bad} -> LED2 OFF")
            else: logging.info("Sensors OK -> LED2 ON")
        return not all(new_flags.values())