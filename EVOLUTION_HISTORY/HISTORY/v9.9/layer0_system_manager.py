"""
======================================================================================
  LAYER 0: SYSTEM MANAGER  ·  WRO Future Engineers 2026
  Raspberry Pi 4B  ·  Single Servo Mechanical 4WS
======================================================================================

5 × GREEN LED INDICATOR MAP (all green, OFF = problem)
─────────────────────────────────────────────────────
  LED1  GPIO 5   System ON        → ON as soon as main.py starts, OFF on shutdown
  LED2  GPIO 6   Sensors OK       → ON when all VL53 + MPU responding, OFF on fault
  LED3  GPIO 13  Camera OK        → ON when vision layer active, OFF on cam fault
  LED4  GPIO 19  ESP32 Serial OK  → ON when serial link alive, OFF on timeout
  LED5  GPIO 26  Race Active      → Blinks 2 Hz during race, OFF when not racing

Boot sequence visual:
  Power ON → LED1 ON (only)
  Sensors OK → LED2 ON
  Camera OK  → LED3 ON
  Serial OK  → LED4 ON
  Ready for Switch 2 → all 4 solid ON
  Switch 2 pressed → LED5 blinks 2 Hz
  Any fault mid-race → that LED goes OFF immediately
======================================================================================
"""
import time
import json
import logging
import threading
import os

try:
    import board
    import digitalio
    GPIO_AVAILABLE = True
except (ImportError, NotImplementedError):
    GPIO_AVAILABLE = False


# ─────────────────────────────────────────────────────────────────────────────
# INDIVIDUAL LED HELPER
# ─────────────────────────────────────────────────────────────────────────────
class StatusLED:
    """Controls a single GPIO output LED."""

    def __init__(self, pin_num: int, name: str):
        self.name    = name
        self.pin_num = pin_num
        self._pin    = None
        self._on     = False

        if GPIO_AVAILABLE:
            try:
                gpio = getattr(board, f"D{pin_num}", None)
                if gpio:
                    self._pin = digitalio.DigitalInOut(gpio)
                    self._pin.direction = digitalio.Direction.OUTPUT
                    self._pin.value = False
            except Exception as exc:
                logging.warning(f"[LED] {name} GPIO{pin_num} init warning: {exc}")

    def on(self):
        self._on = True
        if self._pin:
            self._pin.value = True
        else:
            logging.info(f"[LED SIM] {self.name} → ON")

    def off(self):
        self._on = False
        if self._pin:
            self._pin.value = False
        else:
            logging.info(f"[LED SIM] {self.name} → OFF")

    def set(self, value: bool):
        self.on() if value else self.off()

    def is_on(self) -> bool:
        return self._on


# ─────────────────────────────────────────────────────────────────────────────
# 5-LED MANAGER
# ─────────────────────────────────────────────────────────────────────────────
class HardwareLEDManager:
    """
    Manages 5 individual green status LEDs on Raspberry Pi GPIO.

    LED1 GPIO 5  → System ON        (ON = main running)
    LED2 GPIO 6  → Sensors OK       (ON = all VL53 + MPU healthy)
    LED3 GPIO 13 → Camera OK        (ON = vision layer active)
    LED4 GPIO 19 → ESP32 Serial OK  (ON = serial link alive)
    LED5 GPIO 26 → Race Active      (blinks 2 Hz during race, OFF = not racing)
    """

    RACE_BLINK_ON_S  = 0.25   # 2 Hz blink (250 ms ON)
    RACE_BLINK_OFF_S = 0.25   # 2 Hz blink (250 ms OFF)

    def __init__(self,
                 led1_pin: int = 5,
                 led2_pin: int = 6,
                 led3_pin: int = 13,
                 led4_pin: int = 19,
                 led5_pin: int = 26):

        self.led_system  = StatusLED(led1_pin, "LED1-System")
        self.led_sensors = StatusLED(led2_pin, "LED2-Sensors")
        self.led_camera  = StatusLED(led3_pin, "LED3-Camera")
        self.led_serial  = StatusLED(led4_pin, "LED4-Serial/ESP32")
        self.led_race    = StatusLED(led5_pin, "LED5-Race")

        self._blink_active = False
        self._blink_thread: threading.Thread | None = None

        logging.info(
            f"[LED MGR] 5-LED initialized: "
            f"System=GPIO{led1_pin}  Sensors=GPIO{led2_pin}  "
            f"Camera=GPIO{led3_pin}  Serial=GPIO{led4_pin}  Race=GPIO{led5_pin}"
        )

    # ── Individual LED controls (called by main.py / health events) ──────────
    def set_system(self, ok: bool):
        self.led_system.set(ok)

    def set_sensors(self, ok: bool):
        self.led_sensors.set(ok)

    def set_camera(self, ok: bool):
        self.led_camera.set(ok)

    def set_serial(self, ok: bool):
        self.led_serial.set(ok)

    # ── Race LED blink control ────────────────────────────────────────────────
    def start_race(self):
        """LED5 starts 2 Hz blink — robot is racing."""
        self._stop_blink()
        self._blink_active = True

        def _blink():
            while self._blink_active:
                self.led_race.on()
                time.sleep(self.RACE_BLINK_ON_S)
                if not self._blink_active:
                    break
                self.led_race.off()
                time.sleep(self.RACE_BLINK_OFF_S)

        self._blink_thread = threading.Thread(target=_blink, daemon=True)
        self._blink_thread.start()
        logging.info("[LED MGR] LED5 Race blink STARTED (2 Hz).")

    def stop_race(self):
        """LED5 stops blinking → OFF."""
        self._stop_blink()
        self.led_race.off()
        logging.info("[LED MGR] LED5 Race blink STOPPED.")

    def _stop_blink(self):
        self._blink_active = False
        if self._blink_thread and self._blink_thread.is_alive():
            self._blink_thread.join(timeout=0.6)
        self._blink_thread = None

    # ── Legacy compatibility used by main.py state strings ───────────────────
    def set_state(self, state: str):
        """
        Legacy state-string API — maps old state names to the 5-LED system.
        Prefer calling individual set_*() methods for precise control.
        """
        if state == "INIT_BOOTING":
            # Only LED1 on, rest off
            self.set_system(True)
            self.set_sensors(False)
            self.set_camera(False)
            self.set_serial(False)
            self.stop_race()

        elif state == "HARDWARE_FAULT":
            # The specific LED that faulted will already be OFF via set_*() calls
            # This call just ensures race LED is stopped
            self.stop_race()

        elif state == "READY_WAIT_SWITCH":
            # LED1–LED4 all ON, LED5 OFF (not racing yet)
            self.set_system(True)
            self.stop_race()

        elif state == "RACE_ACTIVE":
            self.set_system(True)
            self.start_race()

        elif state == "RACE_FAULT":
            self.stop_race()   # LED5 goes OFF on fault

    # ── Shutdown ──────────────────────────────────────────────────────────────
    def shutdown(self):
        self._stop_blink()
        for led in (self.led_system, self.led_sensors,
                    self.led_camera, self.led_serial, self.led_race):
            led.off()
        logging.info("[LED MGR] All 5 LEDs OFF — shutdown complete.")


# ─────────────────────────────────────────────────────────────────────────────
# START SWITCH POLLER (Switch 2 → GPIO 16)
# ─────────────────────────────────────────────────────────────────────────────
class StartSwitchPoller:
    """
    Polls the race-start momentary push-button (Switch 2) on GPIO 16.
    Active-LOW with internal pull-up resistor.
    """

    def __init__(self, switch_pin_num: int = 16):
        self.switch_pin = None
        if GPIO_AVAILABLE:
            try:
                gpio = getattr(board, f"D{switch_pin_num}", None)
                if gpio:
                    self.switch_pin = digitalio.DigitalInOut(gpio)
                    self.switch_pin.direction = digitalio.Direction.INPUT
                    self.switch_pin.pull = digitalio.Pull.UP
                    logging.info(
                        f"[SWITCH] Race Start Switch (Switch 2) on GPIO{switch_pin_num}"
                    )
            except Exception as exc:
                logging.warning(f"[SWITCH] Init warning: {exc}")

    def is_pressed(self) -> bool:
        """Returns True when switch is physically pressed (active-LOW)."""
        if GPIO_AVAILABLE and self.switch_pin:
            return not self.switch_pin.value
        return True   # Simulation mode → proceed immediately


# ─────────────────────────────────────────────────────────────────────────────
# SYSTEM MANAGER (Layer 0 Entry Point)
# ─────────────────────────────────────────────────────────────────────────────
class SystemManager:
    """
    Layer 0: Master orchestrator for the WRO 4WS robot.

    Instantiated first in main.py. Provides:
      • 5-LED hardware manager
      • Race-start switch poller
      • System health flags (sensors / serial / camera)
      • Performance counters (FPS, loop latency)
      • Logger & config loader
    """

    def __init__(self, config_path: str):
        self.config_path = config_path
        self.config = self._load_config()
        self._setup_logger()

        self.running = False
        self.lock    = threading.Lock()

        # ── GPIO sub-systems ──────────────────────────────────────────────
        gpio_cfg = self.config.get("gpio", {})

        self.led_mgr = HardwareLEDManager(
            led1_pin=gpio_cfg.get("led1_system_pin",  5),
            led2_pin=gpio_cfg.get("led2_sensors_pin", 6),
            led3_pin=gpio_cfg.get("led3_camera_pin",  13),
            led4_pin=gpio_cfg.get("led4_serial_pin",  19),
            led5_pin=gpio_cfg.get("led5_race_pin",    26),
        )
        self.switch_poller = StartSwitchPoller(
            switch_pin_num=gpio_cfg.get("start_switch_pin", 16),
        )

        # ── Health flags ──────────────────────────────────────────────────
        self.health_status = {
            "sensors_ok": False,
            "serial_ok":  False,
            "camera_ok":  False,
        }

        # ── Performance metrics ───────────────────────────────────────────
        self.loop_counts    = 0
        self.start_time     = time.time()
        self.last_loop_time = time.time()
        self.loop_latencies: list[float] = []

        logging.info("[LAYER 0] System Manager ready.")

    # ── Config & Logging ──────────────────────────────────────────────────────
    def _load_config(self) -> dict:
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"Config not found: {self.config_path}")
        with open(self.config_path, "r") as fh:
            return json.load(fh)

    def reload_config(self):
        with self.lock:
            self.config = self._load_config()
            logging.info("[LAYER 0] Config reloaded.")

    def _setup_logger(self):
        lvl_str = self.config.get("system", {}).get("log_level", "INFO")
        lvl     = getattr(logging, lvl_str.upper(), logging.INFO)
        logging.basicConfig(
            level=lvl,
            format="%(asctime)s [%(levelname)s] %(module)s: %(message)s",
            datefmt="%H:%M:%S",
        )
        logging.info("[LAYER 0] Logger initialized.")

    # ── Health setters (each one updates the matching LED) ───────────────────
    def set_sensor_health(self, ok: bool):
        with self.lock:
            self.health_status["sensors_ok"] = ok
        self.led_mgr.set_sensors(ok)   # LED2 ON/OFF instantly
        if not ok:
            logging.error("[LAYER 0] ⚠ SENSOR FAULT → LED2 OFF")

    def set_serial_health(self, ok: bool):
        with self.lock:
            self.health_status["serial_ok"] = ok
        self.led_mgr.set_serial(ok)    # LED4 ON/OFF instantly
        if not ok:
            logging.error("[LAYER 0] ⚠ SERIAL FAULT → LED4 OFF")

    def set_camera_health(self, ok: bool):
        with self.lock:
            self.health_status["camera_ok"] = ok
        self.led_mgr.set_camera(ok)    # LED3 ON/OFF instantly
        if not ok:
            logging.warning("[LAYER 0] ⚠ CAMERA FAULT → LED3 OFF")

    # Legacy alias
    def set_health_state(self, is_healthy: bool):
        self.set_sensor_health(is_healthy)

    def is_system_healthy(self) -> bool:
        with self.lock:
            return all(self.health_status.values())

    # ── Performance Metrics ───────────────────────────────────────────────────
    def update_performance(self):
        now     = time.time()
        latency = (now - self.last_loop_time) * 1000.0
        self.last_loop_time = now
        self.loop_counts   += 1
        self.loop_latencies.append(latency)
        if len(self.loop_latencies) > 200:
            self.loop_latencies.pop(0)

    def get_fps(self) -> float:
        elapsed = time.time() - self.start_time
        return self.loop_counts / elapsed if elapsed > 0 else 0.0

    def get_average_latency_ms(self) -> float:
        return (sum(self.loop_latencies) / len(self.loop_latencies)
                if self.loop_latencies else 0.0)

    # ── Shutdown ──────────────────────────────────────────────────────────────
    def shutdown(self):
        self.running = False
        self.led_mgr.shutdown()
        logging.info("[LAYER 0] System Manager shut down.")
