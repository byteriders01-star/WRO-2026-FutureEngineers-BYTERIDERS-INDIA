import time
import logging
import threading

try:
    import board
    import busio
    from digitalio import DigitalInOut, Direction
    import adafruit_vl53l1x
    import adafruit_vl53l0x
    from mpu6050 import mpu6050
    HARDWARE_AVAILABLE = True
except (ImportError, NotImplementedError):
    HARDWARE_AVAILABLE = False
    logging.warning("[LAYER 1] Hardware libraries not loaded.")

OFFSET_LR_MM = 50.0

class ThreadedSensorManager:
    """
    Layer 1: Non-Blocking Multi-Threaded Sensor Manager
    Dedicated background thread continuously polls VL53 and MPU6050 sensors.
    Uses atomic flags (front_ready, left_ready, right_ready) so the main 100 Hz
    control loop NEVER freezes waiting for I2C ranging!
    """
    def __init__(self, config: dict):
        self.config = config
        self.hardware_active = HARDWARE_AVAILABLE

        # Thread Safety & Atomic State Flags
        self.lock = threading.Lock()
        self.running = False
        self.worker_thread = None

        # Live Sensor Data Storage
        self.data = {
            "front_mm": 850.0,
            "left_mm": 230.0,
            "right_mm": 240.0,
            "accel": {'x': 0.0, 'y': 0.0, 'z': 9.81},
            "gyro": {'x': 0.0, 'y': 0.0, 'z': 0.0},
            "timestamp": time.time()
        }

        # Status Flags (Flags mark whether each sensor is responsive or timed out)
        self.flags = {
            "front_ok": False,
            "left_ok": False,
            "right_ok": False,
            "mpu_ok": False,
            "bus_active": False
        }

        self.i2c = None
        self.front_pin = None
        self.left_pin  = None
        self.right_pin = None
        self.mpu = None

        if self.hardware_active:
            self._init_hardware()
            self.start_thread()

    def _init_hardware(self):
        try:
            logging.info("[LAYER 1] Initializing I2C Bus & Async Pins...")
            self.i2c = busio.I2C(board.SCL, board.SDA)

            self.front_pin = DigitalInOut(board.D22)
            self.left_pin  = DigitalInOut(board.D17)
            self.right_pin = DigitalInOut(board.D27)

            for p in (self.front_pin, self.left_pin, self.right_pin):
                p.direction = Direction.OUTPUT
                p.value = False

            time.sleep(0.1)

            try:
                self.mpu = mpu6050(0x68)
                self.flags["mpu_ok"] = True
            except Exception as e:
                logging.warning(f"[LAYER 1] MPU6050 init warning: {e}")

            self.flags["bus_active"] = True
        except Exception as e:
            logging.error(f"[LAYER 1] Hardware Init Error: {e}")

    def start_thread(self):
        """Spawns dedicated background worker thread for non-blocking I2C polling."""
        self.running = True
        self.worker_thread = threading.Thread(target=self._async_poll_loop, daemon=True)
        self.worker_thread.start()
        logging.info("[LAYER 1] Async Sensor Polling Thread Spawned.")

    def _async_poll_loop(self):
        """Background Thread: Polling loop runs independently from main controller."""
        while self.running:
            if not self.flags["bus_active"]:
                time.sleep(0.05)
                continue

            # 1. Read Front Sensor
            f_val, f_ok = self._safe_read_front()
            
            # 2. Read Left Sensor
            l_val, l_ok = self._safe_read_left()

            # 3. Read Right Sensor
            r_val, r_ok = self._safe_read_right()

            # 4. Read IMU
            accel, gyro, mpu_ok = self._safe_read_mpu()

            # Atomic Thread-Safe Update
            with self.lock:
                if f_ok and f_val > 0:
                    self.data["front_mm"] = f_val
                if l_ok and l_val > 0:
                    self.data["left_mm"] = l_val
                if r_ok and r_val > 0:
                    self.data["right_mm"] = r_val

                self.data["accel"] = accel
                self.data["gyro"]  = gyro
                self.data["timestamp"] = time.time()

                self.flags["front_ok"] = f_ok
                self.flags["left_ok"]  = l_ok
                self.flags["right_ok"] = r_ok
                self.flags["mpu_ok"]   = mpu_ok

            time.sleep(0.01) # Poll at ~100 Hz in background

    def _safe_read_front(self):
        """Non-blocking read for Front VL53L1X with timeout protection."""
        if not self.front_pin:
            return -1.0, False

        self.front_pin.value = True
        self.left_pin.value = False
        self.right_pin.value = False
        time.sleep(0.02)

        dist = -1.0
        success = False

        try:
            sensor = adafruit_vl53l1x.VL53L1X(self.i2c)
            sensor.timing_budget = 33 # 33ms budget for fast 30FPS ranging
            sensor.start_ranging()
            time.sleep(0.035)

            if sensor.data_ready:
                raw_cm = sensor.distance
                sensor.clear_interrupt()
                if raw_cm is not None and raw_cm > 0:
                    dist = float(raw_cm * 10.0)
                    success = True
            sensor.stop_ranging()
        except Exception:
            success = False

        self.front_pin.value = False
        return dist, success

    def _safe_read_left(self):
        """Non-blocking read for Left VL53L0X with -50mm offset correction."""
        if not self.left_pin:
            return -1.0, False

        self.front_pin.value = False
        self.left_pin.value = True
        self.right_pin.value = False
        time.sleep(0.02)

        dist = -1.0
        success = False

        try:
            sensor = adafruit_vl53l0x.VL53L0X(self.i2c)
            raw_mm = sensor.range
            if raw_mm is not None and raw_mm > 0:
                dist = max(0.0, float(raw_mm) - OFFSET_LR_MM)
                success = True
        except Exception:
            success = False

        self.left_pin.value = False
        return dist, success

    def _safe_read_right(self):
        """Non-blocking read for Right VL53L0X with -50mm offset correction."""
        if not self.right_pin:
            return -1.0, False

        self.front_pin.value = False
        self.left_pin.value = False
        self.right_pin.value = True
        time.sleep(0.02)

        dist = -1.0
        success = False

        try:
            sensor = adafruit_vl53l0x.VL53L0X(self.i2c)
            raw_mm = sensor.range
            if raw_mm is not None and raw_mm > 0:
                dist = max(0.0, float(raw_mm) - OFFSET_LR_MM)
                success = True
        except Exception:
            success = False

        self.right_pin.value = False
        return dist, success

    def _safe_read_mpu(self):
        accel = {'x': 0.0, 'y': 0.0, 'z': 9.81}
        gyro  = {'x': 0.0, 'y': 0.0, 'z': 0.0}
        success = False

        if self.mpu:
            try:
                accel = self.mpu.get_accel_data()
                gyro  = self.mpu.get_gyro_data()
                success = True
            except Exception:
                success = False

        return accel, gyro, success

    def read_sensors(self) -> dict:
        """Instant non-blocking fetch of latest background sensor state & status flags."""
        with self.lock:
            sensor_snapshot = dict(self.data)
            sensor_snapshot["flags"] = dict(self.flags)
            return sensor_snapshot

    def stop(self):
        self.running = False


class SensorLayer(ThreadedSensorManager):
    """Layer 1 Interface backwards compatibility alias."""
    pass
